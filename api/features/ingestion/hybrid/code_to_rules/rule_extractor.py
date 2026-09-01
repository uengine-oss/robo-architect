"""Convert Analyzer RULE nodes into Architect business-rule DTOs.

Analyzer already owns semantic extraction. Architect reads the final RULE
properties and direct table relationships without reparsing source code or
inventing Analyzer-side Example nodes.
"""

from __future__ import annotations

import hashlib

from api.features.ingestion.hybrid.code_to_rules.rule_filters import (
    is_infra,
    is_meaningful_gwt,
)
from api.features.ingestion.hybrid.contracts import RuleDTO
from api.features.ingestion.hybrid.effect_provenance import merge_write_effects
from api.platform.neo4j import ANALYZER_NEO4J_DATABASE, get_session
from api.platform.observability.smart_logger import SmartLogger


_QUERY = """
MATCH (routine)-[hr:HAS_RULE]->(rule:RULE {_owner: 'analyzer'})
WHERE routine._owner = 'analyzer'
  AND (routine:FUNCTION OR routine:PROCEDURE OR routine:METHOD OR routine:TRIGGER)
OPTIONAL MATCH (container {_owner: 'analyzer'})-[:PARENT_OF]->(routine)
OPTIONAL MATCH (rule)-[write:WRITES]->(table:TABLE {_owner: 'analyzer'})
WITH routine, hr, rule, head(collect(DISTINCT container._id)) AS source_container_id,
     collect(DISTINCT {
       table: table.name,
       access: 'WRITE',
       operations: coalesce(write.operations, []),
       op_source: 'SCANNER'
     }) AS raw_writes
RETURN routine._id AS function_id,
       coalesce(routine.name, '') AS function_name,
       coalesce(routine.summary, '') AS function_summary,
       source_container_id,
       rule._id AS analyzer_rule_id,
       coalesce(hr.order, 0) AS rule_order,
       coalesce(rule.condition, '') AS condition,
       coalesce(rule.effects, []) AS effects,
       coalesce(rule.condition_description, '') AS condition_description,
       coalesce(rule.effect_descriptions, []) AS effect_descriptions,
       raw_writes
ORDER BY function_id, rule_order, analyzer_rule_id
"""


def _rule_id(analyzer_rule_id: str, function_id: str, condition: str) -> str:
    source = analyzer_rule_id or f"{function_id}|{condition}"
    return "rule_" + hashlib.sha1(source.encode("utf-8")).hexdigest()[:12]


def _first_text(primary: str | None, fallback: str | None) -> str:
    return (primary or fallback or "").strip()


def _effect_text(descriptions: list[str], effects: list[str]) -> str:
    values = descriptions or effects or []
    return "\n".join(str(value).strip() for value in values if str(value).strip())


def _expand_writes(raw_writes: list[dict]) -> list[dict[str, str]]:
    expanded: list[dict[str, str]] = []
    for raw in raw_writes or []:
        table = raw.get("table")
        if not table:
            continue
        operations = raw.get("operations") or ["UNKNOWN"]
        for operation in operations:
            expanded.append(
                {
                    "table": table,
                    "access": "WRITE",
                    "op": str(operation).upper(),
                    "op_source": "SCANNER",
                }
            )
    return merge_write_effects(expanded)


async def extract_rules_from_analyzer_graph(
    analyzer_graph_ref: str | None = None,
) -> list[RuleDTO]:
    """Read meaningful Analyzer rules and derive one Architect GWT per rule."""
    try:
        with get_session(database=ANALYZER_NEO4J_DATABASE) as session:
            records = list(session.run(_QUERY))
    except Exception as exc:
        SmartLogger.log(
            "WARN",
            "Analyzer rule query failed; returning no rules",
            category="ingestion.hybrid.code_rules",
            params={"error": str(exc), "analyzer_graph_ref": analyzer_graph_ref},
        )
        return []

    rules: list[RuleDTO] = []
    seen: set[str] = set()
    for record in records:
        function_name = _first_text(record.get("function_name"), record.get("function_id"))
        condition = _first_text(
            record.get("condition_description"),
            record.get("condition"),
        )
        outcome = _effect_text(
            list(record.get("effect_descriptions") or []),
            list(record.get("effects") or []),
        )
        summary = _first_text(record.get("function_summary"), function_name)
        title = condition or outcome

        if is_infra(title, function_name):
            continue
        if not is_meaningful_gwt(summary, condition, outcome):
            continue

        rule_id = _rule_id(
            str(record.get("analyzer_rule_id") or ""),
            str(record.get("function_id") or ""),
            condition,
        )
        if rule_id in seen:
            continue
        seen.add(rule_id)

        rules.append(
            RuleDTO(
                id=rule_id,
                given=summary,
                when=condition,
                then=outcome,
                source_function=function_name,
                source_function_id=record.get("function_id") or None,
                source_rule_id=record.get("analyzer_rule_id") or None,
                source_container=record.get("source_container_id") or None,
                confidence=1.0,
                title=title or None,
                writes=_expand_writes(list(record.get("raw_writes") or [])),
            )
        )

    SmartLogger.log(
        "INFO",
        "Analyzer rule conversion complete",
        category="ingestion.hybrid.code_rules",
        params={"rule_count": len(rules), "raw_records": len(records)},
    )
    return rules
