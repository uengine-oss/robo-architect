#!/usr/bin/env python3
"""US3 회귀 하니스 — A2A 척추 + task별 추출 정렬 통계 (spec 039 T013/T014).

골든 세션이 적재된 Neo4j에 연결해, 각 `:BpmTask` 아래로 `PROMOTED_FROM`된
시스템 체인(Command/Event/UI/Policy/ReadModel) 귀속 통계와 빈 task 목록을
JSON으로 출력한다. 동일 문서 재인제스천 전/후로 두 번 실행해 diff 하면
멱등성(중복 0)을 확인할 수 있다(T014).

사용:
    python check_alignment.py                # 전체 BpmTask
    python check_alignment.py > before.json  # 재인제스천 전 스냅샷
    python check_alignment.py > after.json    # 재인제스천 후 → diff before.json after.json

환경변수: api.platform.neo4j 의 기존 연결 설정을 그대로 사용.
"""

from __future__ import annotations

import json
import sys


def main() -> int:
    try:
        from api.platform.neo4j import get_session
    except Exception as e:  # noqa: BLE001
        print(json.dumps({"error": f"neo4j import 실패: {e}"}, ensure_ascii=False))
        return 2

    with get_session() as session:
        tasks = [r["id"] for r in session.run("MATCH (t:BpmTask) RETURN t.id AS id ORDER BY t.id")]

        per_task = {}
        empties = []
        for tid in tasks:
            counts = session.run(
                """
                MATCH (t:BpmTask {id: $tid})
                OPTIONAL MATCH (c:Command)-[:PROMOTED_FROM]->(t)
                OPTIONAL MATCH (e:Event)-[:PROMOTED_FROM]->(t)
                OPTIONAL MATCH (us:UserStory)-[:PROMOTED_FROM]->(t)
                OPTIONAL MATCH (a:Aggregate)-[:PROMOTED_FROM]->(t)
                OPTIONAL MATCH (p:Policy)-[:PROMOTED_FROM]->(t)
                OPTIONAL MATCH (rm:ReadModel)-[:PROMOTED_FROM]->(t)
                RETURN count(DISTINCT c) AS commands,
                       count(DISTINCT e) AS events,
                       count(DISTINCT us) AS userStories,
                       count(DISTINCT a) AS aggregates,
                       count(DISTINCT p) AS policies,
                       count(DISTINCT rm) AS readModels
                """,
                tid=tid,
            ).single()
            d = dict(counts)
            per_task[tid] = d
            if d["commands"] == 0:
                empties.append(tid)

        summary = {
            "task_count": len(tasks),
            "empty_tasks": empties,
            "empty_task_count": len(empties),
            "totals": {
                k: sum(t[k] for t in per_task.values())
                for k in ("commands", "events", "userStories", "aggregates", "policies", "readModels")
            },
            "per_task": per_task,
        }

    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
