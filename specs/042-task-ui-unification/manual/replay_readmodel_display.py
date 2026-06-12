#!/usr/bin/env python3
"""ReadModel 3분류 + display 부착을 현재 세션에 재생(replay)해 검증 (spec 042 US3).

전체 재인제스천 없이, 이미 생성된 ReadModel들을 실 LLM으로 분류하고(cache 상태 따름)
'displayed'는 생산 command 화면에 role:'display'로 부착한다. ui_wireframes 단계의
ReadModel 처리부와 동일 로직.

    PYTHONPATH=. python replay_readmodel_display.py
"""

from __future__ import annotations

import asyncio
import json
import sys


async def main() -> int:
    from api.platform.neo4j import get_session
    from api.features.ingestion.workflow.phases.task_ui_helpers import (
        classify_readmodel,
        attach_display_readmodels,
    )

    with get_session() as s:
        rms = []
        for rec in s.run("MATCH (rm:ReadModel) RETURN rm {.*} AS rm"):
            d = dict(rec["rm"])
            rms.append({
                "id": d.get("id"),
                "name": d.get("name"),
                "description": d.get("description"),
                "query_keys": d.get("query_keys") or [],
            })

    breakdown = {"screen": [], "inline": [], "system": []}
    display_ids = []
    for rm in rms:
        v = await classify_readmodel(rm)
        breakdown.setdefault(v.kind, []).append(rm.get("name") or rm["id"])
        if v.kind == "inline":
            display_ids.append(rm["id"])

    with get_session() as s:
        attached = attach_display_readmodels(s, "", display_ids)

    print(json.dumps({
        "total": len(rms),
        "classification": {k: len(v) for k, v in breakdown.items()},
        "classification_names": breakdown,
        "displayed_attached": attached,
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
