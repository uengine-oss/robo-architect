"""Rule-owner → operation-unit (routine) resolution for the analyzer graph.

Cross-strategy unification (spec 044, contract C4/C5):

- **framework**: the HAS_RULE owner node IS already a routine
  (METHOD/FUNCTION). 0-hop resolution → behaviour unchanged.
- **dbms**: a PROCEDURE is exploded into child statement nodes
  (SELECT/IF/LOOP/CALL…) by PARENT_OF, and rules/examples/questions attach to
  those *child statements* (which have ``name = ""``). The logical operation
  unit is the nearest enclosing routine, recovered by walking PARENT_OF up
  until a routine-labelled node.

This module produces **Cypher fragments only** (pure strings) so the various
analyzer-graph queries (rule_extractor, rule_context, traceability, …) share
one definition (DRY). No Neo4j access here.

Two distinct concerns are intentionally kept separate (see spec 044 research D4):

- **Addressing** (rule_id stability, NEXT/BRANCH cross-back, decomposer index):
  stays bound to the *immediate* HAS_RULE owner node, because the analyzer
  assigns ``local_rule_id`` (R1, R2…) per analyzed node — unique only within
  that node. Re-basing addressing to the routine would collide across sibling
  statements.
- **Grouping / identity / matching-summary**: uses the resolved *routine* so a
  procedure's scattered rules cluster into one operation, with the routine's
  real name + summary.
"""
from __future__ import annotations

# 호출 가능한 루틴 라벨 — 생산자 _ROUTINE_LABELS 와 동일(antlr type = 라벨).
# 이 집합에 드는 노드에서 룰 흐름이 "오퍼레이션 단위"로 묶인다.
ROUTINE_LABELS: tuple[str, ...] = ("FUNCTION", "PROCEDURE", "METHOD", "TRIGGER")


def _routine_label_predicate(var: str) -> str:
    """`var:FUNCTION OR var:PROCEDURE OR …` 형태의 라벨 술어."""
    return " OR ".join(f"{var}:{label}" for label in ROUTINE_LABELS)


def nearest_routine_match(owner_var: str, routine_var: str = "op") -> str:
    """가장 가까운 루틴 조상(자기자신 포함)을 ``routine_var`` 에 바인딩하는 OPTIONAL MATCH 절.

    ``PARENT_OF*0..`` 로 owner 자신(framework, 0-hop)부터 상위 루틴(dbms)까지 후보를
    모으고, 경로 길이 최소(=가장 가까운)인 하나를 고른다. owner 가 루틴이면 0-hop 으로
    owner 자신이 선택된다(framework 무변화). 루틴 조상이 없으면 ``routine_var`` 는 null.

    호출부는 이 절을 ``MATCH (f)-[hr:HAS_RULE]->(r:RULE)`` 뒤,
    ``WITH f, hr, r`` 컨텍스트에서 사용하고, 이어서
    ``WITH …, head(<this>.candidates) …`` 로 최근접을 취한다.

    반환 문자열은 ``routine_var`` 와 ``{routine_var}_hops`` 를 노출한다.
    """
    pred = _routine_label_predicate(routine_var)
    return (
        f"OPTIONAL MATCH p_{routine_var} = ({routine_var})-[:PARENT_OF*0..]->({owner_var})\n"
        f"WHERE {pred}\n"
    )


def nearest_routine_subquery(owner_var: str, out_var: str = "op") -> str:
    """최근접 루틴을 단일 값으로 돌려주는 CALL 서브쿼리(Neo4j 5+).

    여러 루틴 조상이 있을 때 경로 길이 최소를 보장. owner 가 루틴이면 자기자신.
    """
    pred = _routine_label_predicate("cand")
    return (
        f"CALL {{\n"
        f"  WITH {owner_var}\n"
        f"  OPTIONAL MATCH path = (cand)-[:PARENT_OF*0..]->({owner_var})\n"
        f"  WHERE {pred}\n"
        f"  RETURN cand AS {out_var}\n"
        f"  ORDER BY length(path) ASC\n"
        f"  LIMIT 1\n"
        f"}}\n"
    )


def routine_table_effects(routine_var: str, table_var: str = "t", rel_var: str = "rw") -> str:
    """루틴 + 그 PARENT_OF 자손 구문들의 READS/WRITES 를 하향 수집하는 패턴 절.

    dbms 는 DML 이 자식 구문에 부착되므로 루틴 own-body 만 보면 누락(spec 044 D5/R3).
    framework 는 자식이 없어 루틴 자신만 → 동작 불변.

    ``*0..`` 로 루틴 자신(직접 READS/WRITES 가진 경우)도 포함.
    """
    return (
        f"({routine_var})-[:PARENT_OF*0..]->(_d)-[{rel_var}:READS|WRITES]->({table_var}:TABLE)"
    )
