"""Enrich Phase 2 RuleDTOs with analyzer-graph context for Phase 3 matching.

Cross-DB: we query the analyzer DB (`ANALYZER_NEO4J_DATABASE`) separately and
join in Python. The hybrid DB stays clean; we don't shadow analyzer nodes.
"""

from __future__ import annotations

from typing import Iterable

from api.features.ingestion.hybrid.contracts import RuleContext, RuleDTO
from api.platform.neo4j import ANALYZER_NEO4J_DATABASE, get_session

# source_function = 오퍼레이션 단위(루틴) 이름 (rule_extractor/dbms 선형화가 루틴명으로 세팅).
# 그래서 오너는 루틴 노드. 테이블 R/W 는 framework=루틴 자신 / dbms=자식 구문에 붙으므로
# PARENT_OF*0.. 로 하향수집(spec 044 C5/FR-014). 옛 :Actor/:ROLE 는 생산자에 없어 제거.
_FN_LOOKUP_QUERY = """
UNWIND $fn_names AS fn
MATCH (f)
WHERE f.name = fn AND (f:FUNCTION OR f:PROCEDURE OR f:METHOD OR f:TRIGGER)
// Tables the operation touches — framework: on f; dbms: on descendant statements.
OPTIONAL MATCH (f)-[:PARENT_OF*0..]->(_rn)-[:READS]->(rt:TABLE)
OPTIONAL MATCH (f)-[:PARENT_OF*0..]->(_wn)-[:WRITES]->(wt:TABLE)
// Parent traversal — callers (one hop up the CALLS chain) + callees
// (one hop down, used for orchestrator detection)
OPTIONAL MATCH (caller)-[:CALLS]->(f)
OPTIONAL MATCH (f)-[:CALLS]->(callee)
// Container membership and its package
OPTIONAL MATCH (mod)-[:HAS_MEMBER]->(f)
OPTIONAL MATCH (mod)-[:BELONGS_TO]->(pkg:PACKAGE)
WITH fn, f,
     collect(DISTINCT rt.name) AS reads,
     collect(DISTINCT wt.name) AS writes,
     collect(DISTINCT caller.name) AS callers,
     collect(DISTINCT callee.name) AS callees,
     collect(DISTINCT mod.name) AS mod_names,
     collect(DISTINCT pkg.name) AS pkg_names
RETURN fn,
       f.summary AS summary,
       [] AS actors,
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
