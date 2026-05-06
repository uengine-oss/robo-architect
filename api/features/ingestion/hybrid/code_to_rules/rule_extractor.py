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
from typing import Any

from api.features.ingestion.hybrid.code_to_rules.rule_filters import (
    is_infra,
    is_meaningful_gwt,
)
from api.features.ingestion.hybrid.contracts import ExampleDTO, RuleDTO
from api.platform.neo4j import ANALYZER_NEO4J_DATABASE, get_session
from api.platform.observability.smart_logger import SmartLogger

# One row per (function, rule) pair. Examples are collected as a list so a single
# rule with N examples (boundary + nominal) stays one RuleDTO. `coupled_domains`
# lives on the HAS_RULE relationship per the new schema.
_QUERY = """
MATCH (f:FUNCTION)-[hr:HAS_RULE]->(r:Rule)
OPTIONAL MATCH (r)-[:HAS_EXAMPLE]->(e:Example)
WITH f, hr, r,
     collect(DISTINCT {
        example_id:  e.example_id,
        given:       e.given,
        when_:       e.when_,
        then_:       e.then_,
        is_boundary: coalesce(e.is_boundary, false),
        description: e.description
     }) AS examples
ORDER BY coalesce(f.procedure_name, f.name), hr.local_id
RETURN
    coalesce(f.function_id, f.procedure_name, f.name) AS function_id,
    coalesce(f.procedure_name, f.name)                AS function_name,
    f.procedure_name                                  AS procedure_name,
    f.summary                                         AS function_summary,
    r.statement                                       AS statement,
    hr.local_id                                       AS local_id,
    hr.flow_id                                        AS flow_id,
    coalesce(hr.coupled_domains, [])                  AS coupled_domains,
    examples                                          AS examples
"""


def _rule_id(function_id: str, local_id: Any, statement: str) -> str:
    raw = f"{function_id}|{local_id}|{statement or ''}"
    return "rule_" + hashlib.sha1(raw.encode("utf-8")).hexdigest()[:12]


def _module_of(function_id: str | None) -> str | None:
    fid = function_id or ""
    if "." in fid:
        return fid.rsplit(".", 1)[0]
    if "::" in fid:
        return fid.rsplit("::", 1)[0]
    return None


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
        rid = _rule_id(fid, rec.get("local_id"), statement or "")
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
                description=e.get("description") or None,
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
                source_module=_module_of(fid),
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
