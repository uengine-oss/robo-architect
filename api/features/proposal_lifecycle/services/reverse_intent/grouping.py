"""테이블 앵커 그룹핑 — 모든 오퍼레이션을 "한 그룹에만" 배정(커버리지 100%·중복 0).

배정 규칙(각 op 정확히 1그룹):
  ① 쓰기 테이블 있으면 → 그중 허브(전역 쓰기 최다) 테이블 그룹   (데이터 소유 = Aggregate)
  ② 없으면 → 읽기 테이블 중 허브 그룹                            (조회형)
  ③ 테이블 상호작용 없으면(순수 로직) → "(로직)" 그룹

근거(실측): 호출그래프는 클러스터링에 무용(framework 헤어볼 / dbms 먼지). 테이블만 안정.
PoC(project/reverse-intent-poc) 이식. analyzer 그래프는 읽기 전용.
"""
from __future__ import annotations

from dataclasses import dataclass, field

LOGIC_GROUP = "(로직·검증)"

# 인프라/디버그 테이블 — 도메인 Aggregate 아님(그룹핑서 필터, research D7).
INFRA_TABLE_HINTS = ("DEBUG", "LOG", "TMP", "TEMP", "_BAK", "AUDIT")

# 오퍼레이션 전수 + 각 op 의 룰/예시/읽기·쓰기 테이블(자식 구문 rollup) + 라벨용 필드.
_ALL_OPS_QUERY = """
MATCH (op) WHERE op:FUNCTION OR op:PROCEDURE OR op:METHOD OR op:TRIGGER
OPTIONAL MATCH (op)-[:PARENT_OF*0..]->()-[:HAS_RULE]->(r:RULE)
OPTIONAL MATCH (r)-[:HAS_EXAMPLE]->(e:EXAMPLE)
OPTIONAL MATCH (op)-[:PARENT_OF*0..]->()-[:WRITES]->(wt:TABLE)
OPTIONAL MATCH (op)-[:PARENT_OF*0..]->()-[:READS]->(rt:TABLE)
RETURN op.name AS op, coalesce(op.summary,'') AS summary,
       op.logical_name AS logical_name, coalesce(op.stereotype,'') AS stereotype,
       collect(DISTINCT r.statement) AS rules,
       collect(DISTINCT {g:e.given, w:e.when_, t:e.then_}) AS examples,
       collect(DISTINCT wt.name) AS writes,
       collect(DISTINCT rt.name) AS reads
ORDER BY op
"""


@dataclass
class Operation:
    name: str
    summary: str
    logical_name: str | None = None
    stereotype: str = ""
    rules: list[str] = field(default_factory=list)
    examples: list[dict] = field(default_factory=list)
    writes: list[str] = field(default_factory=list)
    reads: list[str] = field(default_factory=list)


@dataclass
class AggregateGroup:
    table: str                       # 앵커 테이블(또는 LOGIC_GROUP)
    ops: list[Operation] = field(default_factory=list)
    kind: str = "write"              # write | read | logic

    @property
    def rule_count(self) -> int:
        return sum(len(o.rules) for o in self.ops)


def _is_infra(table: str) -> bool:
    up = (table or "").upper()
    return any(h in up for h in INFRA_TABLE_HINTS)


def _hub_pick(candidates: list[str], freq: dict[str, int], include_infra: bool) -> str | None:
    """후보 테이블 중 전역 빈도 최다(허브) 선택. 인프라 제외(옵션)."""
    pool = [t for t in candidates if t and (include_infra or not _is_infra(t))]
    if not pool:
        return None
    return max(pool, key=lambda t: (freq.get(t, 0), t))


def fetch_operations(session) -> list[Operation]:
    ops = []
    for row in session.run(_ALL_OPS_QUERY):
        ops.append(Operation(
            name=row["op"], summary=row["summary"] or "",
            logical_name=row.get("logical_name"), stereotype=row.get("stereotype") or "",
            rules=list(row["rules"] or []), examples=list(row["examples"] or []),
            writes=[t for t in (row["writes"] or []) if t],
            reads=[t for t in (row["reads"] or []) if t],
        ))
    return ops


def assign_groups(session, include_infra: bool = False) -> list[AggregateGroup]:
    """모든 op 을 한 그룹씩 배정. 쓰기허브 > 읽기허브 > (로직)."""
    ops = fetch_operations(session)
    wfreq: dict[str, int] = {}
    rfreq: dict[str, int] = {}
    for o in ops:
        for t in o.writes:
            wfreq[t] = wfreq.get(t, 0) + 1
        for t in o.reads:
            rfreq[t] = rfreq.get(t, 0) + 1

    groups: dict[str, AggregateGroup] = {}

    def _grp(key: str, kind: str) -> AggregateGroup:
        return groups.setdefault(key, AggregateGroup(table=key, kind=kind))

    for o in ops:
        anchor = _hub_pick(o.writes, wfreq, include_infra)
        kind = "write"
        if anchor is None:
            anchor = _hub_pick(o.reads, rfreq, include_infra)
            kind = "read"
        if anchor is None:
            anchor, kind = LOGIC_GROUP, "logic"
        _grp(anchor, kind).ops.append(o)

    return sorted(groups.values(), key=lambda g: (g.kind != "write", -g.rule_count))
