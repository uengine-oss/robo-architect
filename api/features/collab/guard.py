"""쓰기가 남의 잠금을 넘지 못하게 막는다.

**선점 잠금이 화면에만 있으면 약속이지 보장이 아니다.** Inspector 는 잠긴
요소의 입력칸을 막지만, 같은 요소를 API 로 그냥 덮어쓸 수 있었다. 동시편집의
목적이 "서로 덮어쓰지 않는다"인데 그 보장이 서버에 없었다.

## 무엇을 막고 무엇을 안 막는가

```
남이 잡고 있다            막는다        409
내가 잡고 있다            안 막는다
아무도 안 잡고 있다        안 막는다     ← 잠금을 안 거치는 쓰기가 있다
잠금이 만료됐다            안 막는다     ← 브라우저를 강제 종료한 사람
```

세 번째가 중요하다. 인제스천·일괄 작업·스크립트는 잠금을 잡지 않는다. 그것까지
막으면 잠금이 기능을 세우는 게 아니라 무너뜨린다. **막는 것은 "둘이 같은 것을
동시에 고치는" 경우 하나다.**

## 왜 403 이 아니라 409 인가

권한 문제가 아니다. 이 사람은 이 프로젝트를 고칠 자격이 있고, **지금 이 순간만**
안 되는 것이다. 403 으로 주면 화면이 "권한이 없습니다"로 읽고, 그건 틀린 안내다.

## 신원을 모르면 막지 않는다

인증이 꺼진 환경에서도 앱은 돈다. 거기서 막으면 **아무도 아무것도 못 고친다.**
잠금은 여러 사람이 있을 때의 장치이지, 사람이 하나일 때 걸림돌이 아니다.
"""

from __future__ import annotations

from typing import Iterable

from fastapi import HTTPException
from starlette.requests import Request

from api.features.collab import store
from api.platform.neo4j_context import get_override


def _who(request: Request) -> str | None:
    claims = getattr(request.state, "auth_claims", None) or {}
    uid = claims.get("sub")
    return str(uid) if uid else None


def _graph_of(request: Request) -> str | None:
    """이 요청이 쓰는 프로젝트. **연결이 정한 것이 이긴다** — 헤더로 고른 값이
    `.env` 폴백보다 먼저다. 다른 곳(`collab/notify.py`)과 같은 기준이다."""
    override = get_override()
    graph = getattr(override, "database", None) if override else None
    if graph:
        return graph
    return request.headers.get("x-project-graph") or None


def ensure_not_locked_by_other(request: Request, element_ids: Iterable[str]) -> None:
    """이 중 하나라도 남이 잡고 있으면 **아무것도 하기 전에** 409 로 멈춘다.

    여럿을 한 번에 고치는 경로(`/api/chat/confirm`)는 all-or-nothing 이라,
    한 건이 막히면 전부 막아야 한다. 일부만 적용하면 사용자는 무엇이 들어가고
    무엇이 빠졌는지 모른다.
    """
    uid = _who(request)
    if not uid:
        return  # 신원을 모르면 막지 않는다 — 위 설명 참고
    graph = _graph_of(request)
    if not graph:
        return
    for element_id in element_ids:
        if not element_id:
            continue
        holder = store.blocking_holder(graph, element_id, uid)
        if holder:
            raise HTTPException(
                status_code=409,
                detail=f"{holder['displayName']} 님이 편집 중입니다. 저장하지 않았습니다.",
            )
