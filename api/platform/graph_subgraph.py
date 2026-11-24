"""K-hop 부분 그래프를 **어느 그래프 저장소에서나** 같은 답으로 읽는다 (2026-11-24).

전에는 한 문장 안에서 경로를 모아(`p=(...)-[*1..k]-(...)` · `reduce(... nodes(p))` · `relationships(p)`)
`startNode(r)` · `endNode(r)` 로 방향을 꺼냈다. 그래프 저장소(Ontological)는 이 셋을 모두 못 한다 —
`startNode` 는 없는 함수, 경로 집계는 GROUP BY 오류, 관계 변수의 노드 속성 접근은 거절(2026-11-24 확인).
그래서 쓰던 API 세 개(노드 상세 · 채팅 영향 · 변경 계획 영향)가 늘 500 이었다.

두 단계로 나눈다 — 각 단계는 Neo4j · Ontological · AGE 가 모두 받는 모양이다.
  1) 노드:  MATCH (s)-[:T*1..k]-(n) WHERE s.id IN $ids  → 씨앗 + 닿는 노드
  2) 관계:  MATCH (a)-[r:T]->(b) WHERE a.id IN $ids AND b.id IN $ids  → 그 노드들 사이의 관계(방향 그대로)
2) 는 경로 위의 관계가 아니라 **모은 노드들 사이의 관계 전부**다. 영향 범위를 보는 용도에는 같거나 더 낫다
(경로 둘이 만나는 지름길 관계도 보인다).
"""

from __future__ import annotations

import json
from typing import Any, Iterable


def _rel_pattern(rel_types: Iterable[str]) -> str:
    types = [t for t in rel_types if t and t.replace("_", "").isalnum()]
    return "|".join(types)


def k_hop_nodes(session, seed_ids: list[str], rel_types: Iterable[str], k: int) -> list[dict[str, Any]]:
    """씨앗과 k 홉 안 노드 — 각 노드는 속성 전부 + `_labels`."""
    pattern = _rel_pattern(rel_types)
    seeds = list(session.run(
        "MATCH (s) WHERE s.id IN $ids RETURN s {.*, _labels: labels(s)} AS n", ids=seed_ids))
    out: dict[str, dict] = {str(r["n"].get("id")): dict(r["n"]) for r in seeds if r["n"].get("id")}
    if pattern and k >= 1:
        rows = session.run(
            f"MATCH (s)-[:{pattern}*1..{int(k)}]-(n) WHERE s.id IN $ids "
            "RETURN DISTINCT n {.*, _labels: labels(n)} AS n",
            ids=seed_ids,
        )
        for r in rows:
            n = dict(r["n"])
            if n.get("id"):
                out.setdefault(str(n["id"]), n)
    return list(out.values())


def relationships_among(session, node_ids: list[str], rel_types: Iterable[str] | None = None,
                        with_properties: bool = False) -> list[dict[str, Any]]:
    """주어진 노드들 사이의 관계 — `{source, target, type[, properties]}`, 방향 그대로."""
    if not node_ids:
        return []
    pattern = _rel_pattern(rel_types or [])
    rel = f"[r:{pattern}]" if pattern else "[r]"
    props = ", properties: r {.*}" if with_properties else ""
    rows = session.run(
        f"MATCH (a)-{rel}->(b) WHERE a.id IN $ids AND b.id IN $ids "
        f"RETURN {{source: a.id, target: b.id, type: type(r){props}}} AS rel",
        ids=node_ids,
    )
    return [dict(r["rel"]) for r in rows]


def relationships_touching(session, node_ids: list[str]) -> list[dict[str, Any]]:
    """주어진 노드에 닿는 관계 전부(이웃이 밖에 있어도) — 삭제 기록용.

    방향마다 따로 묻고 합친다. 양끝이 다 목록 안이면 두 번 나오므로 (type, 양끝, 속성) 으로 하나만 남긴다.
    """
    if not node_ids:
        return []
    q = (
        "MATCH (s)-[r]->(e) WHERE {side}.id IN $ids AND s.id IS NOT NULL AND e.id IS NOT NULL "
        "RETURN {{type: type(r), props: r {{.*}}, startId: s.id, endId: e.id, "
        "startLabels: labels(s), endLabels: labels(e)}} AS rel"
    )
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for side in ("s", "e"):
        for r in session.run(q.format(side=side), ids=node_ids):
            rel = dict(r["rel"])
            key = json.dumps([rel["type"], rel["startId"], rel["endId"], rel.get("props") or {}],
                             sort_keys=True, default=str)
            if key not in seen:
                seen.add(key)
                out.append(rel)
    return out
