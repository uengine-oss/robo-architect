# -*- coding: utf-8 -*-
"""적재를 시작할 때 사람이 넣는 **서비스 ID** 를 받아들일지 정한다.

사용자 지시 넷을 한 자리에 모은다 — 입구가 셋(표준 업로드·Figma·하이브리드)이라
각자 같은 판단을 베껴 두면 한 곳만 고치는 날이 온다.

```
모양       `projects/service_id.py` 의 규칙 하나를 본다
누가       **프로젝트의 소유자만** — 편집자는 적재는 하지만 ID 는 못 붙인다
못 바꾼다  세션 id 는 만들 때 한 번 박히고 이후 쓰는 자리가 없다
유일       `runs.session_id_taken()` — 지난 적재까지 본다
```

## 왜 안 준 경우를 막지 않나

적재는 ID 없이도 돌아야 한다. 체계를 아직 못 받은 사람, 그리고 ID 를 붙일 권한이
없는 편집자가 일을 못 하게 되면 기능 하나 때문에 제품이 멈춘다. 안 주면 지금처럼
난수 id 를 쓴다.

## 왜 편집자가 넣으면 조용히 버리지 않고 막나

조용히 버리면 **화면에는 ID 를 넣었는데 기록에는 없다.** 나중에 그 적재를 기업
체계에서 찾을 수 없고, 왜 없는지도 알 수 없다. 거절은 그 자리에서 보인다.
"""

from __future__ import annotations

from fastapi import HTTPException, Request

from api.features.ingestion import runs
from api.features.projects import service_id as service_ids
from api.features.projects import store as projects_store
from api.features.projects.access import request_graph, request_uid

__all__ = ["resolve"]


def resolve(request: Request, raw: str | None) -> str | None:
    """받아도 되는 값이면 그 값을, 안 줬으면 `None`. 아니면 4xx 로 멈춘다."""
    try:
        wanted = service_ids.validate(raw)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if wanted is None:
        return None

    graph = request_graph(request)
    uid = request_uid(request)
    project = projects_store.get_project(graph) if graph else None
    if not project:
        # 프로젝트를 못 찾으면 소유자를 확인할 길이 없다. 확인 못 한 것을 통과시키지 않는다.
        raise HTTPException(
            status_code=403,
            detail="프로젝트를 확인할 수 없어 서비스 ID 를 붙일 수 없습니다.",
        )
    if (project.get("ownerUid") or "") != uid:
        raise HTTPException(
            status_code=403,
            detail="서비스 ID 는 프로젝트 소유자만 정할 수 있습니다.",
        )

    if runs.session_id_taken(wanted):
        raise HTTPException(
            status_code=409,
            detail=f"이미 쓰고 있는 서비스 ID 입니다: {wanted}",
        )
    return wanted
