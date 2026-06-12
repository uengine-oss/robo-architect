#!/usr/bin/env python3
"""task=UI 검증 하니스 (spec 043 — T021/Q1·Q2·Q3·Q6).

재인제스천 전/후 그래프에서 task=UI 불변식 충족도를 측정해 JSON 출력.
  python check_task_ui.py > before.json   # 042 배포 전(기존 Command당 UI)
  python check_task_ui.py > after.json     # 042 배포+재인제스천 후
  diff before.json after.json

측정: 사람-트리거 task당 UI 분포, ReadModel UI(role 분포), Command/Event task 귀속,
신규 라벨/관계 0 확인용 라벨·관계 인벤토리.
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

    with get_session() as s:
        def scalar(q, **p):
            r = s.run(q, **p).single()
            return r[0] if r else None

        # task당 트리거 UI 분포 (task→US→Command←ATTACHED_TO←UI)
        dist = {}
        for r in s.run(
            """
            MATCH (t:BpmTask)
            OPTIONAL MATCH (t)-[:PROMOTED_TO]->(:UserStory)-[:IMPLEMENTS]->(:Command)<-[a:ATTACHED_TO]-(u:UI)
            WHERE a.role IS NULL OR a.role <> 'display'
            WITH t, count(DISTINCT u) AS uis
            RETURN uis AS k, count(*) AS n ORDER BY k
            """
        ):
            dist[str(r["k"])] = r["n"]

        readmodel = {
            "total": scalar("MATCH (rm:ReadModel) RETURN count(rm)"),
            "ui_screen": scalar(
                "MATCH (:UI)-[a:ATTACHED_TO]->(:ReadModel) WHERE a.role IS NULL OR a.role <> 'display' RETURN count(*)"
            ),
            "ui_display": scalar(
                "MATCH (:UI)-[a:ATTACHED_TO]->(:ReadModel) WHERE a.role = 'display' RETURN count(*)"
            ),
        }

        command_event = {
            "command_with_taskbridge": scalar(
                "MATCH (:BpmTask)-[:PROMOTED_TO]->(:UserStory)-[:IMPLEMENTS]->(c:Command) RETURN count(DISTINCT c)"
            ),
            "command_total": scalar("MATCH (c:Command) RETURN count(c)"),
            "event_total": scalar("MATCH (e:Event) RETURN count(e)"),
        }

        labels = sorted(r["label"] for r in s.run("CALL db.labels() YIELD label RETURN label"))
        rels = sorted(r["relationshipType"] for r in s.run("CALL db.relationshipTypes() YIELD relationshipType RETURN relationshipType"))

    out = {
        "task_trigger_ui_distribution": dist,  # 이상적: 대부분 "1", 시스템 task만 "0"
        "readmodel": readmodel,                # ui_screen=조회화면 승격분, ui_display=표시 부착
        "command_event": command_event,
        "labels": labels,
        "relationship_types": rels,            # 042 전후 동일해야(신규 0)
    }
    print(json.dumps(out, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
