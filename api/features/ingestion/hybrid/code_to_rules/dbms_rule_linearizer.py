"""DBMS 그래프: 자식 구문에 흩어진 룰을 상위 루틴 오너로 귀속 (spec 044 C4).

framework(C/Java)는 룰이 루틴(FUNCTION) 노드에 직접 붙어 rule_extractor `_QUERY` 가
그대로 소비한다. dbms(PL/SQL)는 프로시저가 SELECT/IF/LOOP… 자식 구문 노드(이름 "")로
분해되고 룰이 그 자식들에 붙는다 → 룰의 논리적 오너는 그것을 감싸는 가장 가까운 루틴.

이 모듈은 dbms 그래프일 때만 동작하여, 각 루틴(PROCEDURE/FUNCTION/METHOD/TRIGGER)
서브트리의 HAS_RULE 을 루틴 오너에 귀속시킨 레코드로 방출한다 — rule_extractor `_QUERY`
와 동일한 레코드 키라 다운스트림 무수정. framework 그래프에는 관여하지 않는다.
"""
from __future__ import annotations

from typing import Any

# 루틴 서브트리 내 모든 HAS_RULE 을 루틴 오너(root)에 귀속시켜 수집.
# PARENT_OF*0.. 이므로 framework 처럼 룰이 루틴에 직접 붙은 경우(0칸)도 포함하나,
# 이 쿼리는 dbms 그래프에서만 호출된다(is_dbms_graph 게이트).
_RULE_QUERY = """
MATCH (root)
WHERE root:FUNCTION OR root:PROCEDURE OR root:METHOD OR root:TRIGGER
MATCH (root)-[:PARENT_OF*0..]->(o)-[hr:HAS_RULE]->(r:RULE)
RETURN root.id                        AS function_id,
       coalesce(root.name, '')        AS function_name,
       root.summary                   AS function_summary,
       r.statement                    AS statement,
       coalesce(hr.coupled_domains, []) AS coupled_domains,
       [(r)-[:HAS_EXAMPLE]->(e:EXAMPLE) |
          {example_id: e.id, given: e.given, when_: e.when_, then_: e.then_,
           writes: [(e)-[at:AFFECTS_TABLE]->(t:TABLE) | {table: t.name, op: at.op}]}
       ] AS examples
"""


def is_dbms_graph(session) -> bool:
    """그래프가 dbms 모양(룰이 비-루틴 구문 노드에 붙음)인지 감지.

    framework 그래프는 룰이 전부 루틴(FUNCTION 등)에 직접 → False.
    """
    rec = session.run(
        """
        MATCH (o)-[:HAS_RULE]->(:RULE)
        WHERE NOT (o:FUNCTION OR o:PROCEDURE OR o:METHOD OR o:TRIGGER)
        RETURN count(*) AS c
        """
    ).single()
    return bool(rec and rec["c"] > 0)


def linearize_dbms_rules(session) -> list[dict[str, Any]]:
    """dbms 루틴 서브트리의 룰을 rule_extractor `_QUERY` 와 동일 키 레코드로 방출.

    반환 레코드 키 = function_id, function_name, function_summary, statement,
    coupled_domains, examples. 한 루틴 아래 같은 (routine, statement) 중복은
    rule_extractor 의 rule_id dedup 이 흡수한다.
    """
    return [
        {
            "function_id": row["function_id"],
            "function_name": row["function_name"] or row["function_id"],
            "function_summary": row["function_summary"],
            "statement": row["statement"],
            "coupled_domains": list(row["coupled_domains"] or []),
            "examples": row["examples"] or [],
        }
        for row in session.run(_RULE_QUERY)
    ]
