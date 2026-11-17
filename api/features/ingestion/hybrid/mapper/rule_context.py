"""Enrich Phase 2 RuleDTOs with analyzer-graph context for Phase 3 matching.

Cross-DB: we query the analyzer DB (`analyzer_session()` — the project's own
analysis graph) separately and join in Python. The hybrid DB stays clean; we
don't shadow analyzer nodes.

읽는 계약은 지금 analyzer 의 product graph 다(robo-data-analyzer
`graph/product_graph.py`): 루틴은 `product_id`·`_owner='analyzer'`·`name`·`summary`
를 갖고, 소속 컨테이너는 `(container)-[:PARENT_OF]->(routine)` 이다. 옛
`HAS_FUNCTION`·`BELONGS_TO_PACKAGE`·`function_id` 는 생산자에 없다.
"""

from __future__ import annotations

from typing import Iterable

from api.features.ingestion.hybrid.contracts import RuleContext, RuleDTO
from api.platform.neo4j import analyzer_session

# source_function = 오퍼레이션 단위(루틴) 이름. 오너는 루틴 노드. 테이블 R/W 는
# 루틴 자신 또는 자식 구문에 붙으므로 PARENT_OF*0.. 로 하향수집(spec 044 C5/FR-014).
_FN_LOOKUP_QUERY = """
UNWIND $sources AS source
MATCH (f)
// ⚠ 루틴은 **`product_id`** 로 찾는다. `_id` 로 찾지 않는다 — 포스코 현장
// Ontological DB 는 `_id` 를 내부 정수 id 로 해석해 한 건도 맞지 않는다.
// id 가 없을 때만 이름으로 찾는다(같은 이름이 다른 프로젝트 루틴일 수 있다).
WHERE (
        (source.routine_id IS NOT NULL AND f.product_id = source.routine_id)
        OR
        (source.routine_id IS NULL AND f.name = source.function_name)
      )
  AND f._owner = 'analyzer'
  AND (f:FUNCTION OR f:PROCEDURE OR f:METHOD OR f:TRIGGER)
// ⚠ **여기엔 `OPTIONAL MATCH` 를 두지 않는다** (2026-10-21 · ISS-62).
//
// OPTIONAL MATCH 는 **행을 곱한다** — 규칙 111개를 한 번에 넣으면
// reads × writes × callers × callees × container × parent 로 행이 터져 이 질의
// 하나가 **41초** 걸렸다. 그리고 `explore_task` 가 이것을 작업마다 부른다.
//
// 패턴 컴프리헨션은 행을 곱하지 않는다. 여기에 무엇을 더할 때도 **같은 모양**으로 더한다.
RETURN source.rule_id AS rule_id,
       f.summary AS summary,
       [] AS actors,
       [(f)-[:PARENT_OF*0..]->(_rn)-[:READS]->(rt:TABLE) | rt.name] AS reads_tables,
       [(f)-[:PARENT_OF*0..]->(_wn)-[:WRITES]->(wt:TABLE) | wt.name] AS writes_tables,
       // 한 다리 건너 — SQL 은 DAO 에 있고 규칙은 서비스에 있다(ISS-61).
       // `build_rule_contexts` 가 이 조회를 DTO 보다 먼저 쓰므로 여기에 없으면
       // rule_extractor 를 고쳐도 출처 테이블이 0 으로 돌아간다.
       [(f)-[:CALLS]->(_cr)-[:PARENT_OF*0..]->(_crn)-[:READS]->(crt:TABLE) | crt.name]
          AS reads_tables_via_calls,
       [(f)-[:CALLS]->(_cw)-[:PARENT_OF*0..]->(_cwn)-[:WRITES]->(cwt:TABLE) | cwt.name]
          AS writes_tables_via_calls,
       [(f)<-[:CALLS]-(_cl) | _cl.name] AS callers,
       [(f)-[:CALLS]->(_ce) | _ce.name] AS callees,
       head([(f)<-[:PARENT_OF]-(_c) | _c.name]) AS parent_container,
       head([(f)<-[:PARENT_OF]-(_c2)<-[:PARENT_OF]-(_p) | _p.name]) AS container_parent
"""


def _names(values) -> list[str]:
    return sorted({str(v) for v in (values or []) if v})


def build_rule_contexts(rules: Iterable[RuleDTO]) -> list[RuleContext]:
    """For each rule, look up its routine in the analyzer graph and attach summary/tables."""
    rules = list(rules)
    sources = [
        {
            "rule_id": r.id,
            "function_name": r.source_function,
            # 루틴의 불변 id(`product_id`). 있으면 같은 이름의 다른 루틴
            # (다음 프로젝트 분석)으로 절대 떨어지지 않는다.
            "routine_id": r.source_function_id or r.source_module,
        }
        for r in rules if r.source_function or r.source_function_id or r.source_module
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
                        "reads_tables": _names(rec.get("reads_tables")),
                        "writes_tables": _names(rec.get("writes_tables")),
                        "reads_tables_via_calls": _names(rec.get("reads_tables_via_calls")),
                        "writes_tables_via_calls": _names(rec.get("writes_tables_via_calls")),
                        "callers": rec.get("callers") or [],
                        "callees": rec.get("callees") or [],
                        "parent_container": rec.get("parent_container"),
                        "container_parent": rec.get("container_parent"),
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
            source_container=r.source_container,
            # The Rule snapshot is the durable source. Live analyzer data may
            # enrich it, but an empty/moved analyzer graph must not erase it.
            function_summary=extra.get("summary") or r.source_summary,
            actors=extra.get("actors", []),
            reads_tables=extra.get("reads_tables") or r.reads_tables,
            writes_tables=extra.get("writes_tables") or r.writes_tables,
            # 한 다리 건너도 **위 두 줄과 같은 규칙**으로 고른다 (ISS-61) —
            # 살아 있는 analyzer 조회가 있으면 그쪽, 없으면 Rule 스냅샷.
            reads_tables_via_calls=(extra.get("reads_tables_via_calls")
                                    or r.reads_tables_via_calls),
            writes_tables_via_calls=(extra.get("writes_tables_via_calls")
                                     or r.writes_tables_via_calls),
            context_cluster=r.context_cluster,
            callers=extra.get("callers", []),
            callees=extra.get("callees", []),
            parent_container=extra.get("parent_container") or r.source_container,
            container_parent=extra.get("container_parent"),
        ))
    return contexts
