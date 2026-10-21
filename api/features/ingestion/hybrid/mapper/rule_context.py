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
// ⚠ **여기엔 `OPTIONAL MATCH` 를 두지 않는다** (2026-10-21 · ISS-62).
//
// 예전에는 여섯 개가 줄줄이 있었다. OPTIONAL MATCH 는 **행을 곱한다** —
// 규칙 111개를 한 번에 넣으면 reads × writes × callers × callees × mod × pkg 로
// 행이 터져 이 질의 하나가 **41초**(고치기 전) 걸렸다. 그리고 `explore_task` 가
// 이것을 **작업마다 · 이벤트 루프 위에서 동기로** 부른다. 탐색을 누르면 백엔드가
// 통째로 멈추고 `/api/health` 조차 안 돌아온다 — 화면에는 "계속 대기중" 만 뜬다.
//
// 패턴 컴프리헨션은 행을 곱하지 않는다. 여섯 개를 전부 그 모양으로 바꿨다.
// 여기에 무엇을 더할 때도 **같은 모양**으로 더한다.
RETURN source.rule_id AS rule_id,
       f.summary AS summary,
       [] AS actors,
       // framework 는 루틴 자신, dbms 는 자식 구문에 테이블 접근이 붙는다(spec 044).
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
       head([(f)<-[:HAS_FUNCTION]-(_m) | _m.name]) AS parent_module,
       head([(f)<-[:HAS_FUNCTION]-(_mp)-[:BELONGS_TO_PACKAGE]->(_pk:PACKAGE) | _pk.name])
          AS parent_package
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
            # 한 다리 건너도 **위 두 줄과 같은 규칙**으로 고른다 (ISS-61) —
            # 살아 있는 analyzer 조회가 있으면 그쪽, 없으면 Rule 스냅샷.
            reads_tables_via_calls=(extra.get("reads_tables_via_calls")
                                    or r.reads_tables_via_calls),
            writes_tables_via_calls=(extra.get("writes_tables_via_calls")
                                     or r.writes_tables_via_calls),
            context_cluster=r.context_cluster,
            callers=extra.get("callers", []),
            callees=extra.get("callees", []),
            parent_module=extra.get("parent_module"),
            parent_package=extra.get("parent_package"),
        ))
    return contexts
