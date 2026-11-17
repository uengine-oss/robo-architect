"""Phase 2: Analyzer RULE nodes → Architect business-rule DTOs.

Analyzer already owns semantic extraction. Architect reads the published
product graph (robo-data-analyzer ``graph/product_graph.py`` ·
``pipeline/publication/product_graph.py``) without reparsing source code:

    (routine:FUNCTION|PROCEDURE|METHOD|TRIGGER {product_id, _owner:'analyzer',
        name, summary, file_path, start_line, end_line})
      -[:HAS_RULE {order}]->
    (rule:RULE {product_id, _owner:'analyzer', line, condition, effects,
        condition_description, effect_descriptions, code_text})
      -[:READS|WRITES {operations}]-> (table:TABLE {name})

Rules hang on the routine itself (``<routine id>::R-<line>``) — the old DBMS
"rules scattered over child statements" shape and EXAMPLE nodes are gone.

⚠ 노드 정체성은 **`product_id`** 다. `_id` 로 찾거나 읽지 않는다 — 포스코 현장
Ontological DB 는 `_id` 를 내부 정수 id 로 해석한다.

No LLM is required here — the semantic lift happened upstream in the analyzer.
"""

from __future__ import annotations

import hashlib
import json

from api.features.ingestion.hybrid.code_to_rules.rule_filters import (
    is_infra,
    is_meaningful_gwt,
)
from api.features.ingestion.hybrid.contracts import RuleDTO
from api.features.ingestion.hybrid.effect_provenance import merge_write_effects
from api.platform.neo4j import analyzer_session
from api.platform.observability.smart_logger import SmartLogger


# One row per (routine, rule). Routine-level table access (direct + one CALLS
# hop, ISS-61) is gathered with pattern comprehensions so rows don't fan out.
_QUERY = """
MATCH (routine)-[hr:HAS_RULE]->(rule:RULE)
WHERE rule._owner = 'analyzer'
  AND routine._owner = 'analyzer'
  AND (routine:FUNCTION OR routine:PROCEDURE OR routine:METHOD OR routine:TRIGGER)
OPTIONAL MATCH (container)-[:PARENT_OF]->(routine)
WHERE container._owner = 'analyzer'
OPTIONAL MATCH (rule)-[write:WRITES]->(table:TABLE)
WITH routine, hr, rule,
     head(collect(DISTINCT container.product_id)) AS source_container_id,
     collect(DISTINCT {
       table: table.name,
       access: 'WRITE',
       operations: write.operations,
       op_source: 'SCANNER'
     }) AS raw_writes
WITH routine, hr, rule, source_container_id, raw_writes,
     [(routine)-[:PARENT_OF*0..]->(_rn)-[:READS]->(rt:TABLE) | rt.name] AS reads_tables,
     [(routine)-[:PARENT_OF*0..]->(_wn)-[:WRITES]->(wt:TABLE) | wt.name] AS writes_tables,
     // ⚠ **한 다리 건너**도 모은다 (2026-10-21 · ISS-61).
     //
     // 위 두 줄은 `PARENT_OF` 만 탄다 = **이 루틴이 직접 치는 SQL**. 그런데
     // 이 코드베이스에서 SQL 은 전부 DAO 에 있고 **규칙은 서비스에 있다.**
     // ISS-59 로 서비스→DAO `CALLS` 가 생겼다. 그 한 다리를 탄다.
     // ⚠ **직접과 섞지 않는다** — 뜻이 다르다.
     [(routine)-[:CALLS]->(_cr)-[:PARENT_OF*0..]->(_crn)-[:READS]->(crt:TABLE) | crt.name]
        AS reads_tables_via_calls,
     [(routine)-[:CALLS]->(_cw)-[:PARENT_OF*0..]->(_cwn)-[:WRITES]->(cwt:TABLE) | cwt.name]
        AS writes_tables_via_calls
RETURN routine.product_id                      AS function_id,
       coalesce(routine.name, '')              AS function_name,
       coalesce(routine.summary, '')           AS function_summary,
       routine.file_path                       AS source_file_path,
       routine.start_line                      AS source_start_line,
       routine.end_line                        AS source_end_line,
       source_container_id,
       reads_tables, writes_tables,
       reads_tables_via_calls, writes_tables_via_calls,
       rule.product_id                         AS analyzer_rule_id,
       coalesce(hr.order, 0)                   AS rule_order,
       coalesce(rule.condition, '')            AS condition,
       coalesce(rule.effects, [])              AS effects,
       coalesce(rule.condition_description, '') AS condition_description,
       coalesce(rule.effect_descriptions, [])  AS effect_descriptions,
       raw_writes
ORDER BY function_id, rule_order, analyzer_rule_id
"""


def _as_id(value) -> str | None:
    """노드 id 를 문자열로. 게이트웨이가 정수로 주는 경우가 있다."""
    if value is None or value == "":
        return None
    return str(value)


def _as_list(value) -> list:
    """목록 속성을 목록으로. 저장소에 따라 JSON 문자열로 돌아오기도 한다."""
    if value is None or value == "":
        return []
    if isinstance(value, str):
        text = value.strip()
        if text.startswith("["):
            try:
                parsed = json.loads(text)
            except ValueError:
                return [text]
            return list(parsed) if isinstance(parsed, list) else [parsed]
        return [text]
    if isinstance(value, (list, tuple)):
        return list(value)
    return [value]


def _rule_id(function_id: str, analyzer_rule_id: str) -> str:
    # 생산자(analyzer)의 RULE id 가 정체성이다. 같은 조건·효과라도 다른 RULE 이면 다른 룰.
    raw = f"{function_id}|{analyzer_rule_id or ''}"
    return "rule_" + hashlib.sha1(raw.encode("utf-8")).hexdigest()[:12]


def _texts(value) -> list[str]:
    return [str(x).strip() for x in _as_list(value) if str(x).strip()]


def _expand_writes(raw_writes) -> list[dict[str, str]]:
    expanded: list[dict[str, str]] = []
    for raw in raw_writes or []:
        if not isinstance(raw, dict):
            continue
        table = raw.get("table")
        if not table:
            continue
        operations = _texts(raw.get("operations")) or ["UNKNOWN"]
        for operation in operations:
            expanded.append(
                {
                    "table": str(table),
                    "access": "WRITE",
                    "op": operation.upper(),
                    "op_source": "SCANNER",
                }
            )
    return merge_write_effects(expanded)


def _sorted_names(value) -> list[str]:
    return sorted({str(x) for x in _as_list(value) if x})


def _structured_rule(rec) -> RuleDTO | None:
    """Adapt one analyzer RULE row (condition/effects schema) to ingestion GWT.

    Verified condition/effect descriptions are the semantic source of truth;
    fabricating a code interpretation with another LLM here would lose provenance.
    """
    effects = _texts(rec.get("effect_descriptions")) or _texts(rec.get("effects"))
    if not effects:
        return None
    function_id = _as_id(rec.get("function_id"))
    function_name = str(rec.get("function_name") or function_id or "").strip()
    condition = str(rec.get("condition_description") or rec.get("condition") or "").strip()
    if is_infra(" ".join(effects), function_name):
        return None
    given = condition or "해당 코드 경로의 조건이 충족됨"
    when = f"{function_name} 실행"
    then = "; ".join(effects)
    if not is_meaningful_gwt(given, when, then):
        return None
    analyzer_id = _as_id(rec.get("analyzer_rule_id"))
    if analyzer_id is None:
        return None
    fid = function_id or function_name
    return RuleDTO(
        id=_rule_id(fid, analyzer_id),
        given=given,
        when=when,
        then=then,
        source_function=function_name,
        # **문자열로 바꿔서 넣는다.** 게이트웨이가 id 를 정수로 돌려주면
        # 이 DTO 의 str 필드를 pydantic 이 전건 거부한다.
        source_function_id=function_id,
        source_rule_id=analyzer_id,
        source_container=_as_id(rec.get("source_container_id")),
        # posco-web 이름 — 루틴 id 와 같다(추적성이 이 속성으로 루틴을 찾는다).
        source_module=function_id,
        source_summary=(rec.get("function_summary") or None),
        source_file_path=rec.get("source_file_path"),
        source_start_line=rec.get("source_start_line"),
        source_end_line=rec.get("source_end_line"),
        reads_tables=_sorted_names(rec.get("reads_tables")),
        writes_tables=_sorted_names(rec.get("writes_tables")),
        reads_tables_via_calls=_sorted_names(rec.get("reads_tables_via_calls")),
        writes_tables_via_calls=_sorted_names(rec.get("writes_tables_via_calls")),
        confidence=1.0,
        title=f"{condition}: {then}" if condition else then,
        writes=_expand_writes(rec.get("raw_writes")),
    )


async def extract_rules_from_analyzer_graph(
    analyzer_graph_ref: str | None = None,
) -> list[RuleDTO]:
    """Read every meaningful analyzer RULE as a RuleDTO (one per routine × rule).

    The analyzer graph is the project's own (`analyzer_session()` — the
    project's `analyzerGraph`, else `.env`). `analyzer_graph_ref` is
    informational only.
    """
    try:
        sess = analyzer_session()
        if sess is None:
            return []
        with sess as s:
            records = list(s.run(_QUERY))
    except Exception as e:
        SmartLogger.log(
            "WARN", "Phase 2 query failed; returning empty rule list",
            category="ingestion.hybrid.code_rules",
            params={"error": str(e), "analyzer_graph_ref": analyzer_graph_ref},
        )
        return []

    rules: list[RuleDTO] = []
    seen: set[str] = set()
    for rec in records:
        rule = _structured_rule(rec)
        if rule is None or rule.id in seen:
            continue
        seen.add(rule.id)
        rules.append(rule)

    SmartLogger.log(
        "INFO", "Phase 2 rule extraction complete",
        category="ingestion.hybrid.code_rules",
        params={"rule_count": len(rules), "raw_records": len(records)},
    )
    return rules
