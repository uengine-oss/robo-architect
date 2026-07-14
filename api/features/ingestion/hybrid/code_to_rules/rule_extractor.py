"""Phase 2: legacy analyzer graph → GWT business Rules.

The analyzer stage produces `(FUNCTION)-[:HAS_RULE]->(Rule)-[:HAS_EXAMPLE]->(Example)`.
Phase 2 collapses each (function, rule) pair into one `RuleDTO`, picks a
representative Example for the canonical given/when/then narrative, and carries
the full Example set for downstream retrieval that wants boundary-case access.

No LLM is required here — the semantic lift happened upstream in the analyzer.
"""

from __future__ import annotations

import hashlib
import json

from api.features.ingestion.hybrid.code_to_rules.rule_filters import (
    is_infra,
    is_meaningful_gwt,
)
from api.features.ingestion.hybrid.code_to_rules.dbms_rule_linearizer import (
    is_dbms_graph,
    linearize_dbms_rules,
)
from api.features.ingestion.hybrid.contracts import ExampleDTO, RuleDTO
from api.platform.neo4j import ANALYZER_NEO4J_DATABASE, get_session
from api.platform.observability.smart_logger import SmartLogger

# One row per (function, rule) pair. Examples are collected as a list so a single
# rule with N examples (boundary + nominal) stays one RuleDTO. `coupled_domains`
# lives on the HAS_RULE relationship; per-Example AFFECTS_TABLE writes are gathered
# with a sub-pattern collect inside the example map so we don't fan out the row.
_QUERY = """
MATCH (f)-[hr:HAS_RULE]->(r:RULE)
WITH f, hr, r,
     [(r)-[:HAS_EXAMPLE]->(e:EXAMPLE) |
        {
          example_id:  e.id,
          given:       e.given,
          when_:       e.when_,
          then_:       e.then_,
          writes:      [(e)-[at:AFFECTS_TABLE]->(tbl:TABLE) | {table: tbl.name, op: at.op}]
        }
     ] AS examples
RETURN
    coalesce(f.id, f.name)            AS function_id,
    coalesce(f.name, '')              AS function_name,
    f.owner_id                        AS module_id,
    f.summary                         AS function_summary,
    r.statement                       AS statement,
    coalesce(hr.coupled_domains, [])  AS coupled_domains,
    examples                          AS examples
ORDER BY function_name, r.statement
"""
# ★ `f.owner_id` = 소속 모듈 id — analyzer 가 노드 속성으로 준다 (analyzer spec 047 FR-007).
#   종전엔 이 속성이 없어서 `function_id` 문자열을 잘라 모듈을 추측했다.
#   그 파싱이 analyzer 의 id 규칙을 붙들어 매서, 서로 다른 노드가 같은 id 를 갖는 버그를
#   못 고치게 만들었다. **id 는 불투명한 열쇠다 — 뜯지 않는다.**


def _rule_id(function_id: str, statement: str) -> str:
    raw = f"{function_id}|{statement or ''}"
    return "rule_" + hashlib.sha1(raw.encode("utf-8")).hexdigest()[:12]


# (옛 `_module_of(function_id)` 삭제 — id 문자열을 잘라 모듈을 추측하던 함수.
#  이제 analyzer 가 `owner_id` 노드 속성으로 소속 모듈을 알려준다(analyzer spec 047 FR-007)
#  → 쿼리에서 `f.owner_id AS module_id` 로 그냥 읽는다. id 는 뜯지 않는다.)


def _humanize(value: str | None) -> str:
    """Pull a human-readable string out of a possibly-JSON-encoded GWT field.

    Analyzer Examples encode `given` and `then_` as JSON when they carry
    structured data (writes[], inputs, exceptions). The `narrative` field inside
    is the prose summary; fall back to the raw string when not parseable.
    """
    if not value:
        return ""
    s = value.strip()
    if not s.startswith("{"):
        return s
    try:
        obj = json.loads(s)
    except Exception:
        return s
    if isinstance(obj, dict):
        narrative = obj.get("narrative")
        if isinstance(narrative, str) and narrative.strip():
            return narrative.strip()
    return s


def _pick_canonical(examples: list[dict]) -> dict | None:
    """Choose the example whose narrative best represents this rule.

    Preference: non-boundary first (the "happy path" demonstrates intent more
    cleanly than an edge case), then by example_id for stable ordering.
    """
    valid = [e for e in examples if isinstance(e, dict) and e.get("example_id")]
    if not valid:
        return None
    valid.sort(key=lambda e: (bool(e.get("is_boundary")), e.get("example_id") or ""))
    return valid[0]


def _writes_from_then_json(then_value: str | None) -> list[dict]:
    """Pull `writes[]` out of a JSON-encoded `then_` payload, if present.

    Analyzer Examples encode `then_` as JSON when they carry side effects:
    `{"narrative": "...", "writes": [{"table": "...", "op": "INSERT"}], ...}`.
    Plain-text `then_` returns []. Tolerant of malformed JSON — returns [] on
    any parse failure.
    """
    if not then_value:
        return []
    s = then_value.strip()
    if not s.startswith("{"):
        return []
    try:
        obj = json.loads(s)
    except Exception:
        return []
    if not isinstance(obj, dict):
        return []
    raw = obj.get("writes")
    if not isinstance(raw, list):
        return []
    out: list[dict] = []
    for w in raw:
        if not isinstance(w, dict):
            continue
        tbl = w.get("table")
        op = w.get("op")
        if isinstance(tbl, str) and isinstance(op, str):
            out.append({"table": tbl, "op": op.upper()})
    return out


def _merge_writes(*sources: list[dict]) -> list[dict]:
    """Union writes lists into a stable, deduplicated list of {table, op} dicts."""
    seen: set[tuple[str, str]] = set()
    out: list[dict] = []
    for src in sources:
        for w in src or []:
            if not isinstance(w, dict):
                continue
            tbl = w.get("table")
            op = w.get("op")
            if not (isinstance(tbl, str) and isinstance(op, str)):
                continue
            key = (tbl, op.upper())
            if key in seen:
                continue
            seen.add(key)
            out.append({"table": tbl, "op": op.upper()})
    return out


async def extract_rules_from_analyzer_graph(
    analyzer_graph_ref: str | None = None,
) -> list[RuleDTO]:
    """Pull every meaningful (function, rule) pair from the analyzer DB as a RuleDTO.

    Same Rule (rule_hash) shared across N functions becomes N RuleDTOs — one per
    host function — so downstream retrieval/embedding can keep its per-function
    semantics. `analyzer_graph_ref` is informational; the analyzer DB is a
    single global graph today.
    """
    rules: list[RuleDTO] = []
    seen: set[str] = set()

    try:
        with get_session(database=ANALYZER_NEO4J_DATABASE) as s:
            # framework: 룰이 루틴(FUNCTION)에 직접 붙음 → 기존 _QUERY 로 소비.
            # dbms: 룰이 자식 구문 노드에 흩어짐 → 상위 루틴 오너로 귀속(044 C4). 동일 레코드 키.
            if is_dbms_graph(s):
                records = linearize_dbms_rules(s)
            else:
                records = list(s.run(_QUERY))
    except Exception as e:
        SmartLogger.log(
            "WARN", "Phase 2 query failed; returning empty rule list",
            category="ingestion.hybrid.code_rules",
            params={"error": str(e), "analyzer_graph_ref": analyzer_graph_ref},
        )
        return []

    for rec in records:
        statement = rec.get("statement")
        fn_name = rec.get("function_name")
        if is_infra(statement, fn_name):
            continue

        canonical = _pick_canonical(rec.get("examples") or [])
        given_h = _humanize(canonical.get("given") if canonical else None)
        when_h = _humanize(canonical.get("when_") if canonical else None)
        then_h = _humanize(canonical.get("then_") if canonical else None)
        if not is_meaningful_gwt(given_h, when_h, then_h):
            continue

        fid = rec.get("function_id") or fn_name or "unknown"
        rid = _rule_id(fid, statement or "")
        if rid in seen:
            continue
        seen.add(rid)

        examples = [
            ExampleDTO(
                example_id=e.get("example_id"),
                given=_humanize(e.get("given")),
                when_=(e.get("when_") or "").strip(),
                then_=_humanize(e.get("then_")),
                is_boundary=bool(e.get("is_boundary")),
                # Union of analyzer-edge writes (AFFECTS_TABLE) and JSON-embedded
                # writes[] in the raw then_ — either alone is incomplete in some
                # function fixtures, so we merge both for robust §3.1 classification.
                writes=_merge_writes(
                    e.get("writes") or [],
                    _writes_from_then_json(e.get("then_")),
                ),
            )
            for e in (rec.get("examples") or [])
            if isinstance(e, dict) and e.get("example_id")
        ]

        rules.append(
            RuleDTO(
                id=rid,
                given=given_h,
                when=when_h,
                then=then_h,
                source_function=fn_name,
                # 소속 모듈 = analyzer 가 준 `owner_id` 속성 (id 를 뜯지 않는다).
                source_module=rec.get("module_id") or None,
                confidence=1.0,
                title=(statement or None),
                examples=examples,
                coupled_domains=list(rec.get("coupled_domains") or []),
            )
        )

    SmartLogger.log(
        "INFO", "Phase 2 rule extraction complete",
        category="ingestion.hybrid.code_rules",
        params={"rule_count": len(rules), "raw_records": len(records)},
    )
    return rules
