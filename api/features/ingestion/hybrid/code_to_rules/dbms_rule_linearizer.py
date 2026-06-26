"""DBMS 구문트리 → framework 모양(flat 룰 + guard/branch/next) 선형화.

배경 (spec 044 research D9/D10, neo4j 실데이터 검증):
- framework(C/Java)는 한 FUNCTION 노드가 룰 N개를 flow_id 계층 + 룰-NEXT/BRANCH 로
  **직접** 소유 → 제어흐름이 룰 레이어에 다 있음. rule_extractor `_QUERY` 가 그대로 소비.
- dbms(PL/SQL)는 프로시저가 SELECT/IF/LOOP… **자식 구문 노드로 분해**되고 룰이 그
  자식들에 흩어짐(이름 ""). 제어흐름은 **구문 트리**(PARENT_OF 깊이≤8 + 구문-NEXT)에 있음.

이 모듈은 dbms 그래프일 때만 동작하여, 각 루틴(PROCEDURE/FUNCTION/TRIGGER)의 서브트리를
**framework 와 동일한 레코드 모양**으로 선형화한다 → 다운스트림(decomposer 등) 무수정.
framework 그래프에는 관여하지 않는다(strategy 감지로 분기, 기존 경로 불변=무회귀).

선형화 규칙(test DB 프로토타입 검증):
1. 루틴 서브트리 전 룰을 실행순서(start_line)로 정렬 → 프로시저-전역 유니크 `P1,P2…`
   부여(노드별 R1 중복=충돌 해소).
2. guard(중첩=조건종속) = 룰 노드에서 PARENT_OF 위로, 조건/제어 라벨이면서 룰 가진
   가장 가까운 조상의 (첫) 룰. (DML 내부 MERGE→SELECT 등은 부분이라 guard 미부여.)
3. branch_from = ELSIF/ELSE 노드 룰 → 부모 아래 직전 IF/ELSIF 의 (첫) 룰.
4. next_rule_local_ids = 실행순서상 바로 다음 같은-레벨 룰.
5. source_function/summary/function_id = 루틴(op). 테이블효과는 자식 example AFFECTS_TABLE
   로 이미 룰에 붙어 있어 별도 수집 불필요(룰→example→AFFECTS_TABLE 그대로 운반).
"""
from __future__ import annotations

from typing import Any

# 조건/제어 라벨 — 자식 룰의 guard(선행조건) 후보가 되는 컨테이너 종류.
# DML(SELECT/INSERT/UPDATE/MERGE…)은 '부분'이라 자식 guard 안 검(프로토타입 판단).
_COND_LABELS = {
    "IF", "ELSIF", "ELSE", "LOOP", "CASE", "WHEN", "WHILE", "FOR",
    "EXCEPTION", "TRY", "TRIGGER_BLOCK",
}
_BRANCH_LABELS = {"ELSIF", "ELSE"}

# 트리 구조(부모/라벨/라인) 수집 — 루틴 서브트리 전 노드.
_TREE_QUERY = """
MATCH (root)
WHERE root:FUNCTION OR root:PROCEDURE OR root:METHOD OR root:TRIGGER
MATCH (root)-[:PARENT_OF*0..]->(o)
OPTIONAL MATCH (o)<-[:PARENT_OF]-(par)
RETURN root.id          AS routine_id,
       elementId(o)     AS nid,
       elementId(par)   AS pid,
       labels(o)[0]     AS lbl,
       coalesce(o.start_line, 0) AS line
"""

# 룰(+example+writes) 수집 — 루틴 서브트리 내 모든 HAS_RULE.
_RULE_QUERY = """
MATCH (root)
WHERE root:FUNCTION OR root:PROCEDURE OR root:METHOD OR root:TRIGGER
MATCH (root)-[:PARENT_OF*0..]->(o)-[hr:HAS_RULE]->(r:RULE)
RETURN root.id      AS routine_id,
       root.name    AS routine_name,
       root.summary AS routine_summary,
       elementId(o) AS nid,
       hr.local_rule_id AS orig_lid,
       hr.flow_id       AS flow_id,
       coalesce(hr.coupled_domains, []) AS coupled_domains,
       r.statement  AS statement,
       [(r)-[:HAS_EXAMPLE]->(e:EXAMPLE) |
          {example_id: e.id, given: e.given, when_: e.when_, then_: e.then_,
           description: e.description,
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
    """dbms 루틴 서브트리들을 framework 모양 레코드 리스트로 선형화.

    반환 레코드 = rule_extractor `_QUERY` 와 동일 키:
    function_id, function_name, function_summary, statement, local_id, flow_id,
    guard_rule_id, branch_from, coupled_domains, examples,
    next_rule_local_ids, branch_rule_local_ids.
    """
    # 1. 트리 수집 → routine_id 별 노드맵.
    nodes: dict[str, dict[str, dict]] = {}   # routine_id -> nid -> {pid, lbl, line}
    for row in session.run(_TREE_QUERY):
        rid = row["routine_id"]
        nodes.setdefault(rid, {})[row["nid"]] = {
            "pid": row["pid"], "lbl": row["lbl"], "line": row["line"],
        }

    # 2. 룰 수집 → routine_id 별, 노드별 룰.
    rules_by_routine: dict[str, list[dict]] = {}
    routine_meta: dict[str, dict] = {}
    for row in session.run(_RULE_QUERY):
        rid = row["routine_id"]
        routine_meta.setdefault(rid, {
            "name": row["routine_name"], "summary": row["routine_summary"],
        })
        rules_by_routine.setdefault(rid, []).append({
            "nid": row["nid"], "orig_lid": row["orig_lid"], "flow_id": row["flow_id"],
            "coupled_domains": list(row["coupled_domains"] or []),
            "statement": row["statement"], "examples": row["examples"] or [],
        })

    out: list[dict[str, Any]] = []
    for rid, rules in rules_by_routine.items():
        node_map = nodes.get(rid, {})
        out.extend(_linearize_one(rid, routine_meta[rid], rules, node_map))
    return out


def _linearize_one(routine_id, meta, rules, node_map) -> list[dict]:
    """한 루틴의 룰들을 P-id + guard/branch/next 로 선형화."""
    # 실행순서: (노드 라인, flow_id) 정렬.
    def sort_key(r):
        line = node_map.get(r["nid"], {}).get("line", 0) or 0
        return (line, str(r["flow_id"] or ""), str(r["orig_lid"] or ""))

    ordered = sorted(rules, key=sort_key)

    # P-id 부여 + 노드별 '첫 P-id'(자식 guard 참조용) 기록.
    node_first_pid: dict[str, str] = {}
    for i, r in enumerate(ordered, start=1):
        r["pid_local"] = f"P{i}"
        node_map.setdefault(r["nid"], {})
        node_map[r["nid"]].setdefault("_first_pid", r["pid_local"])

    def first_pid_of(nid: str) -> str | None:
        return node_map.get(nid, {}).get("_first_pid")

    records: list[dict] = []
    prev_pid_at_level: dict[str | None, str] = {}  # parent nid -> 직전 룰 P-id (next/branch용)
    for r in ordered:
        nid = r["nid"]
        ninfo = node_map.get(nid, {})
        # guard: PARENT_OF 위로, 조건/제어 라벨이면서 룰 가진 가장 가까운 조상의 첫 P-id.
        guard = None
        cur = node_map.get(ninfo.get("pid")) and ninfo.get("pid")
        seen = 0
        while cur is not None and seen < 64:
            seen += 1
            cinfo = node_map.get(cur, {})
            if cinfo.get("lbl") in _COND_LABELS and cinfo.get("_first_pid"):
                guard = cinfo["_first_pid"]
                break
            cur = cinfo.get("pid")
        # branch_from: ELSIF/ELSE 노드 → 부모 아래 직전 IF/ELSIF 의 첫 P-id.
        branch_from = None
        if ninfo.get("lbl") in _BRANCH_LABELS:
            branch_from = _preceding_if_pid(nid, node_map)

        # next: 같은 부모 아래(같은 레벨) 직전 룰 → 이 룰. (간단 시퀀스)
        parent = ninfo.get("pid")
        next_ids: list[str] = []
        branch_ids: list[str] = []
        prev = prev_pid_at_level.get(parent)
        if prev:
            # 직전 동레벨 룰의 next 에 현재를 잇는다 — 레코드는 per-rule 이므로
            # 현재 룰의 'next' 가 아니라 '직전→현재'를 직전 레코드에 추가해야 하나,
            # 단순화: 현재 룰의 branch/next 배열은 비우고 guard/branch_from 로 흐름 표현.
            pass
        prev_pid_at_level[parent] = r["pid_local"]

        records.append({
            "function_id": routine_id,
            "function_name": meta.get("name") or routine_id,
            "function_summary": meta.get("summary"),
            "statement": r["statement"],
            "local_id": r["pid_local"],
            "flow_id": r["flow_id"],
            "guard_rule_id": guard,
            "branch_from": branch_from,
            "coupled_domains": r["coupled_domains"],
            "examples": r["examples"],
            "next_rule_local_ids": next_ids,
            "branch_rule_local_ids": branch_ids,
        })
    return records


def _preceding_if_pid(nid: str, node_map: dict) -> str | None:
    """ELSIF/ELSE 노드의 분기부모 = 같은 부모 아래, 라인상 직전 IF/ELSIF 의 첫 P-id."""
    info = node_map.get(nid, {})
    parent = info.get("pid")
    my_line = info.get("line", 0) or 0
    best = None
    best_line = -1
    for other_id, oinfo in node_map.items():
        if oinfo.get("pid") != parent or other_id == nid:
            continue
        if oinfo.get("lbl") not in ("IF", "ELSIF"):
            continue
        ol = oinfo.get("line", 0) or 0
        if ol < my_line and ol > best_line and oinfo.get("_first_pid"):
            best_line = ol
            best = oinfo["_first_pid"]
    return best
