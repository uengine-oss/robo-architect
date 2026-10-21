"""Enrich Phase 2 RuleDTOs with analyzer-graph context for Phase 3 matching.

Cross-DB: we query the analyzer DB (`analyzer_database`) separately and
join in Python. The hybrid DB stays clean; we don't shadow analyzer nodes.
"""

from __future__ import annotations

from typing import Iterable

from api.features.ingestion.hybrid.contracts import RuleContext, RuleDTO
from api.platform.neo4j import analyzer_database, analyzer_session, get_session

# source_function = 오퍼레이션 단위(루틴) 이름 (rule_extractor/dbms 선형화가 루틴명으로 세팅).
# 그래서 오너는 루틴 노드. 테이블 R/W 는 framework=루틴 자신 / dbms=자식 구문에 붙으므로
# PARENT_OF*0.. 로 하향수집(spec 044 C5/FR-014). 옛 :Actor/:ROLE 는 생산자에 없어 제거.
_FN_LOOKUP_QUERY = """
UNWIND $sources AS source
MATCH (f)
// 이름은 `f.name` 이 있으면 그것, 없으면 `function_id` 다. analyzer 의 FUNCTION 에는
// name 필드가 없어서(`function_id` 가 "module_id.name"), 이름으로만 찾으면 한 건도
// 맞지 않는다 — 조회가 통째로 비어 function_summary 와 parent_module 이 매 룰마다
// 빈 값이 됐다. rule_extractor 가 같은 규칙으로 이름을 만든다.
WHERE (
        (source.routine_id IS NOT NULL AND f._id = source.routine_id)
        OR
        (source.routine_id IS NULL AND (f.name = source.function_name OR f.function_id = source.function_name))
      )
  AND (f:FUNCTION OR f:PROCEDURE OR f:METHOD OR f:TRIGGER)
// Tables the operation touches — framework: on f; dbms: on descendant statements.
OPTIONAL MATCH (f)-[:PARENT_OF*0..]->(_rn)-[:READS]->(rt:TABLE)
OPTIONAL MATCH (f)-[:PARENT_OF*0..]->(_wn)-[:WRITES]->(wt:TABLE)
// Parent traversal — callers (one hop up the CALLS chain) + callees
// (one hop down, used for orchestrator detection)
OPTIONAL MATCH (caller)-[:CALLS]->(f)
OPTIONAL MATCH (f)-[:CALLS]->(callee)
// Container membership and its package.
// HAS_MEMBER is DataType -> Variable and BELONGS_TO is Table -> Schema in the
// analyzer (shared/neo4j/rel_types.py); a module reaches its functions through
// HAS_FUNCTION and its package through BELONGS_TO_PACKAGE. Naming the wrong two
// cost nothing loudly — both clauses are OPTIONAL, so parent_module and
// parent_package simply came back empty for every rule.
OPTIONAL MATCH (mod)-[:HAS_FUNCTION]->(f)
OPTIONAL MATCH (mod)-[:BELONGS_TO_PACKAGE]->(pkg:PACKAGE)
WITH source, f,
     collect(DISTINCT rt.name) AS reads,
     collect(DISTINCT wt.name) AS writes,
     collect(DISTINCT caller.name) AS callers,
     collect(DISTINCT callee.name) AS callees,
     collect(DISTINCT mod.name) AS mod_names,
     collect(DISTINCT pkg.name) AS pkg_names
RETURN source.rule_id AS rule_id,
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
    sources = [
        {
            "rule_id": r.id,
            "function_name": r.source_function,
            # source_module is the analyzer routine node's immutable `_id`.
            # If it exists, never fall back to a same-named routine from the
            # analyzer's next (different-project) active workspace.
            "routine_id": r.source_module,
        }
        for r in rules if r.source_function or r.source_module
    ]
    lookup: dict[str, dict] = {}
    # 분석 짝이 없으면 아예 붙지 않는다 — 룰 문맥이 비는 것이 정상이다.
    sess = analyzer_session() if sources else None
    if sess is not None:
        try:
            with sess as s:
                for rec in s.run(_FN_LOOKUP_QUERY, sources=sources):
                    lookup[rec["rule_id"]] = {
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
        extra = lookup.get(r.id, {})
        contexts.append(RuleContext(
            rule_id=r.id,
            given=r.given,
            when=r.when,
            then=r.then,
            source_function=r.source_function,
            source_module=r.source_module,
            # The Rule snapshot is the durable source. Live analyzer data may
            # enrich it, but an empty/moved analyzer graph must not erase it.
            function_summary=extra.get("summary") or r.source_summary,
            actors=extra.get("actors", []),
            reads_tables=extra.get("reads_tables") or r.reads_tables,
            writes_tables=extra.get("writes_tables") or r.writes_tables,
            # 한 다리 건너는 **Rule 스냅샷만** 들고 간다 (ISS-61). 살아 있는
            # analyzer 조회(`extra`)는 이 둘을 안 싣는다 — 싣는 쪽이 생기면
            # 위 두 줄과 같은 모양으로 맞춘다.
            reads_tables_via_calls=r.reads_tables_via_calls,
            writes_tables_via_calls=r.writes_tables_via_calls,
            context_cluster=r.context_cluster,
            callers=extra.get("callers", []),
            callees=extra.get("callees", []),
            parent_module=extra.get("parent_module"),
            parent_package=extra.get("parent_package"),
        ))
    return contexts
