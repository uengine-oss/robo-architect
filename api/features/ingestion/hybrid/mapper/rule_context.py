"""Enrich converted Analyzer rules with nearby code and table context."""

from __future__ import annotations

from typing import Iterable

from api.features.ingestion.hybrid.contracts import RuleContext, RuleDTO
from api.platform.neo4j import ANALYZER_NEO4J_DATABASE, get_session


_FUNCTION_QUERY = """
UNWIND $functions AS requested
MATCH (routine {_owner: 'analyzer'})
WHERE (routine:FUNCTION OR routine:PROCEDURE OR routine:METHOD OR routine:TRIGGER)
  AND ((requested.id IS NOT NULL AND routine._id = requested.id)
       OR (requested.id IS NULL AND routine.name = requested.name))
OPTIONAL MATCH (routine)-[:PARENT_OF*0..]->(_read)-[:READS]->(read_table:TABLE)
OPTIONAL MATCH (routine)-[:PARENT_OF*0..]->(_write)-[:WRITES]->(write_table:TABLE)
OPTIONAL MATCH (caller)-[:CALLS]->(routine)
OPTIONAL MATCH (routine)-[:CALLS]->(callee)
OPTIONAL MATCH (container)-[:PARENT_OF]->(routine)
OPTIONAL MATCH (parent)-[:PARENT_OF]->(container)
WITH requested, routine,
     collect(DISTINCT read_table.name) AS reads,
     collect(DISTINCT write_table.name) AS writes,
     collect(DISTINCT caller.name) AS callers,
     collect(DISTINCT callee.name) AS callees,
     collect(DISTINCT container.name) AS containers,
     collect(DISTINCT parent.name) AS parents
RETURN requested.id AS requested_id,
       requested.name AS requested_name,
       routine.summary AS summary,
       [value IN reads WHERE value IS NOT NULL] AS reads_tables,
       [value IN writes WHERE value IS NOT NULL] AS writes_tables,
       [value IN callers WHERE value IS NOT NULL] AS callers,
       [value IN callees WHERE value IS NOT NULL] AS callees,
       head([value IN containers WHERE value IS NOT NULL]) AS parent_container,
       head([value IN parents WHERE value IS NOT NULL]) AS container_parent
"""


def build_rule_contexts(rules: Iterable[RuleDTO]) -> list[RuleContext]:
    """Return one matching context for every input rule."""
    rules = list(rules)
    requested = {
        (rule.source_function_id or "", rule.source_function or "")
        for rule in rules
        if rule.source_function_id or rule.source_function
    }
    functions = [
        {"id": function_id or None, "name": name or None}
        for function_id, name in sorted(requested)
    ]
    lookup: dict[str, dict] = {}
    if functions:
        try:
            with get_session(database=ANALYZER_NEO4J_DATABASE) as session:
                for record in session.run(_FUNCTION_QUERY, functions=functions):
                    key = record.get("requested_id") or record.get("requested_name")
                    if not key:
                        continue
                    lookup[key] = {
                        "summary": record.get("summary"),
                        "reads_tables": record.get("reads_tables") or [],
                        "writes_tables": record.get("writes_tables") or [],
                        "callers": record.get("callers") or [],
                        "callees": record.get("callees") or [],
                        "parent_container": record.get("parent_container"),
                        "container_parent": record.get("container_parent"),
                    }
        except Exception:
            lookup = {}

    contexts: list[RuleContext] = []
    for rule in rules:
        key = rule.source_function_id or rule.source_function or ""
        extra = lookup.get(key, {})
        contexts.append(
            RuleContext(
                rule_id=rule.id,
                given=rule.given,
                when=rule.when,
                then=rule.then,
                source_function=rule.source_function,
                source_container=rule.source_container,
                function_summary=extra.get("summary"),
                reads_tables=extra.get("reads_tables", []),
                writes_tables=extra.get("writes_tables", []),
                context_cluster=rule.context_cluster,
                callers=extra.get("callers", []),
                callees=extra.get("callees", []),
                parent_container=extra.get("parent_container"),
                container_parent=extra.get("container_parent"),
            )
        )
    return contexts
