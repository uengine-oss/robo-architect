"""Enrich Phase 2 RuleDTOs with analyzer-graph context for Phase 3 matching.

Cross-DB: we query the analyzer DB (`ANALYZER_NEO4J_DATABASE`) separately and
join in Python. The hybrid DB stays clean; we don't shadow analyzer nodes.
"""

from __future__ import annotations

from typing import Iterable

from api.features.ingestion.hybrid.contracts import RuleContext, RuleDTO
from api.platform.neo4j import ANALYZER_NEO4J_DATABASE, get_session

_FN_LOOKUP_QUERY = """
UNWIND $fn_names AS fn
MATCH (f)
WHERE coalesce(f.procedure_name, f.name) = fn
// Tables the function touches directly
OPTIONAL MATCH (a:Actor)-[:ROLE]->(f)
OPTIONAL MATCH (f)-[:READS]->(rt:Table)
OPTIONAL MATCH (f)-[:WRITES]->(wt:Table)
// Parent traversal — callers (one hop up the CALLS chain) + callees
// (one hop down, used for orchestrator detection)
OPTIONAL MATCH (caller)-[:CALLS]->(f)
OPTIONAL MATCH (f)-[:CALLS]->(callee)
// Module/file containment and its package
OPTIONAL MATCH (mod)-[:HAS_FUNCTION]->(f)
OPTIONAL MATCH (mod)-[:BELONGS_TO_PACKAGE]->(pkg:PACKAGE)
WITH fn, f,
     collect(DISTINCT a.name) AS actors,
     collect(DISTINCT rt.name) AS reads,
     collect(DISTINCT wt.name) AS writes,
     collect(DISTINCT coalesce(caller.procedure_name, caller.name)) AS callers,
     collect(DISTINCT coalesce(callee.procedure_name, callee.name)) AS callees,
     collect(DISTINCT coalesce(mod.name, mod.procedure_name)) AS mod_names,
     collect(DISTINCT pkg.name) AS pkg_names
RETURN fn,
       f.summary AS summary,
       [a IN actors WHERE a IS NOT NULL] AS actors,
       [r IN reads  WHERE r IS NOT NULL] AS reads_tables,
       [w IN writes WHERE w IS NOT NULL] AS writes_tables,
       [c IN callers WHERE c IS NOT NULL] AS callers,
       [c IN callees WHERE c IS NOT NULL] AS callees,
       head([m IN mod_names WHERE m IS NOT NULL]) AS parent_module,
       head([p IN pkg_names WHERE p IS NOT NULL]) AS parent_package
"""


def build_rule_contexts(rules: Iterable[RuleDTO]) -> list[RuleContext]:
    """For each rule, look up its function in the analyzer graph and attach summary/actors/tables."""
    rules = list(rules)
    fn_names = sorted({r.source_function for r in rules if r.source_function})
    lookup: dict[str, dict] = {}
    if fn_names:
        try:
            with get_session(database=ANALYZER_NEO4J_DATABASE) as s:
                for rec in s.run(_FN_LOOKUP_QUERY, fn_names=fn_names):
                    lookup[rec["fn"]] = {
                        "summary": rec.get("summary"),
                        "actors": rec.get("actors") or [],
                        "reads_tables": rec.get("reads_tables") or [],
                        "writes_tables": rec.get("writes_tables") or [],
                        "callers": rec.get("callers") or [],
                        "callees": rec.get("callees") or [],
                        "parent_module": rec.get("parent_module"),
                        "parent_package": rec.get("parent_package"),
                    }
        except Exception:
            lookup = {}

    contexts: list[RuleContext] = []
    for r in rules:
        extra = lookup.get(r.source_function or "", {})
        contexts.append(RuleContext(
            rule_id=r.id,
            given=r.given,
            when=r.when,
            then=r.then,
            source_function=r.source_function,
            source_module=r.source_module,
            function_summary=extra.get("summary"),
            actors=extra.get("actors", []),
            reads_tables=extra.get("reads_tables", []),
            writes_tables=extra.get("writes_tables", []),
            context_cluster=r.context_cluster,
            callers=extra.get("callers", []),
            callees=extra.get("callees", []),
            parent_module=extra.get("parent_module"),
            parent_package=extra.get("parent_package"),
        ))
    return contexts
