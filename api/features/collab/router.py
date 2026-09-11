"""같은 프로젝트를 여럿이 볼 때 — 알림 스트림과 접속자.

```
GET  /api/collab/stream     이 프로젝트의 변경·접속자·잠금 (SSE)
GET  /api/collab/state      같은 내용 1회 (진단·검사용)
POST /api/collab/lock       이 요소를 내가 잡는다
POST /api/collab/unlock     내 잠금을 푼다
POST /api/collab/leave      창을 닫았다
```

**모든 경로가 신원과 프로젝트를 요구한다.** 프로젝트가 없으면 알릴 대상이
없고, 신원이 없으면 접속자 목록에 이름을 못 적는다.

## 왜 긴 폴링이 아니라 SSE 인가

받는 쪽(`robo:data-changed`)이 이미 있다. 모자란 것은 **다시 물을 계기**였다 —
한 번 열어 두고 밀어 주면 화면 코드는 한 줄도 안 바꿔도 된다.

브라우저의 `EventSource` 는 헤더를 못 실어서 401 이 난다. 프런트는
`app/sse.js` 의 `openSse` 로 연다 — `fetch` 라 인터셉터를 그대로 지난다.

## 이 스트림이 못 보는 쓰기

진행 표시가 SSE 인 긴 작업은 **GET 으로 열려서 그 안에서 쓴다.** 요청 메서드로
안 잡히므로 작업이 끝나는 자리에서 `store.bump` 를 직접 부른다. 지금 그런 자리:

    인제스천 완료        features/ingestion/*        (아직 안 붙임 — §17-1 Todo)
    이벤트 스토밍 승격    features/ingestion/hybrid/  (아직 안 붙임)

그 둘은 지금도 **자기 창에서는** `emitDataChanged` 로 갱신된다. 못 보는 것은
**남의 창**이다.
"""

from __future__ import annotations

import asyncio
import json
from typing import AsyncIterator

from fastapi import APIRouter, Body, HTTPException, Request
from fastapi.responses import StreamingResponse

from api.features.auth.tokens import TokenError, verify_token
from api.features.collab import store
from api.features.projects import store as projects

router = APIRouter(prefix="/api/collab", tags=["collab"])

# 판이 바뀌었는지 묻는 주기. 사람이 "바로"라고 느끼는 선에서 가장 느리게.
POLL_SECONDS = 2.0

# 스트림이 살아 있는지 알리는 주기. 중간 프록시가 조용한 연결을 끊는다.
PING_EVERY = 15


def _claims(request: Request) -> dict:
    claims = getattr(request.state, "auth_claims", None)
    if not claims:
        header = request.headers.get("authorization") or ""
        token = header[7:].strip() if header[:7].lower() == "bearer " else None
        try:
            claims = verify_token(token)
        except TokenError:
            raise HTTPException(status_code=401, detail="로그인이 필요합니다.")
    return claims or {}


def _uid(request: Request) -> str:
    uid = str(_claims(request).get("sub") or "")
    if not uid:
        raise HTTPException(status_code=401, detail="사용자를 알 수 없습니다.")
    return uid


def _graph(request: Request, uid: str) -> str:
    """이 요청이 볼 프로젝트. **권한을 여기서 확인한다.**

    확인을 빠뜨리면 graph 이름만 알면 남의 프로젝트가 언제 바뀌는지, 누가 보고
    있는지를 들여다볼 수 있다. 내용은 안 나가지만 그것도 새는 것이다.
    """
    graph = (
        request.headers.get("x-project-graph")
        or request.headers.get("x-neo4j-database")
        or ""
    ).strip()
    if not graph:
        raise HTTPException(status_code=400, detail="프로젝트를 먼저 고르세요.")
    if not store.valid_graph(graph):
        raise HTTPException(status_code=400, detail="프로젝트 이름이 올바르지 않습니다.")
    if projects.level_of(uid, graph) is None:
        raise HTTPException(status_code=403, detail="이 프로젝트를 볼 수 없습니다.")
    return graph


def _snapshot(graph: str) -> dict:
    rev = store.revision(graph)
    return {
        "graph": graph, **rev,
        "viewers": store.viewers(graph),
        "locks": store.locks(graph),
    }


def _writable(uid: str, graph: str) -> None:
    """잠글 수 있는 사람인가. **읽기 등급은 못 잠근다** — 못 고칠 것을 잡아
    두면 그건 잠금이 아니라 방해다."""
    if projects.level_of(uid, graph) == "read":
        raise HTTPException(status_code=403, detail="읽기 권한으로는 편집할 수 없습니다.")


@router.get("/state")
async def get_state(request: Request) -> dict:
    """지금 판과 접속자. 스트림 없이 한 번만 볼 때."""
    uid = _uid(request)
    graph = _graph(request, uid)
    store.ensure_schema()
    store.heartbeat(graph, uid, _claims(request).get("name"))
    return _snapshot(graph)


@router.post("/lock")
async def post_lock(request: Request, body: dict = Body(default={})) -> dict:
    """이 요소를 내가 잡는다.

    못 잡았을 때 **누가 갖고 있는지 함께 돌려준다.** "실패"만 말하면 화면이
    아무것도 설명하지 못하고, 사람은 같은 버튼을 계속 누른다.
    """
    uid = _uid(request)
    graph = _graph(request, uid)
    _writable(uid, graph)
    element_id = str((body or {}).get("elementId") or "").strip()
    if not element_id:
        raise HTTPException(status_code=400, detail="어느 요소인지 없습니다.")
    store.ensure_schema()
    result = store.acquire_lock(
        graph, element_id, uid,
        display_name=_claims(request).get("name"),
        label=str((body or {}).get("label") or "")[:120] or None,
    )
    # **판 번호는 올리지 않는다.** 올리면 누가 노드를 고르기만 해도 남의 창이
    # 그래프를 통째로 다시 읽는다. 자물쇠는 자기 이벤트(`locks`)로 간다.
    return result


@router.post("/unlock")
async def post_unlock(request: Request, body: dict = Body(default={})) -> dict:
    """내 잠금을 푼다. **남의 것은 못 푼다** — 풀 수 있으면 잠금이 아니다."""
    uid = _uid(request)
    graph = _graph(request, uid)
    element_id = str((body or {}).get("elementId") or "").strip()
    released = store.release_lock(graph, element_id, uid) if element_id else False
    return {"ok": released}


@router.post("/leave")
async def post_leave(request: Request, body: dict = Body(default={})) -> dict:
    """창을 닫았다. 안 불려도 TTL 이 걷어가지만, 불리면 즉시 사라진다."""
    uid = _uid(request)
    graph = (body or {}).get("graph") or request.headers.get("x-project-graph") or ""
    if store.valid_graph(graph):
        store.leave(graph, uid)
        # 잠금도 같이 푼다. 안 그러면 TTL 이 걷어갈 때까지 남이 못 고친다.
        store.release_all(graph, uid)
    return {"ok": True}


@router.get("/stream")
async def stream(request: Request) -> StreamingResponse:
    uid = _uid(request)
    graph = _graph(request, uid)
    display = _claims(request).get("name")
    store.ensure_schema()

    async def gen() -> AsyncIterator[bytes]:
        # 첫 이벤트는 **지금 상태**다. 이걸 안 보내면 창을 새로 연 사람은 다음
        # 변경이 있을 때까지 자기가 몇 판을 보고 있는지 모른다.
        last = store.revision(graph)["rev"]
        last_viewers: list[str] = []
        last_locks: list[tuple] = []
        yield _sse("hello", _snapshot(graph))
        ticks = 0
        try:
            while True:
                if await request.is_disconnected():
                    break
                await asyncio.sleep(POLL_SECONDS)
                ticks += 1
                # 폴링 한 바퀴가 곧 심장박동이다. 별도 타이머를 두면 둘이
                # 어긋나 유령 접속자가 남는다.
                store.heartbeat(graph, uid, display)
                # 내 잠금도 같은 바퀴에 갱신한다. 따로 타이머를 두면 둘이
                # 어긋나 **내가 보고 있는데 내 잠금이 만료된다.**
                store.refresh_locks(graph, uid)

                current = store.revision(graph)
                if current["rev"] != last:
                    last = current["rev"]
                    yield _sse("changed", {"graph": graph, **current})

                # 접속자는 바뀔 때만 보낸다 — 매 바퀴 보내면 화면이 깜빡인다.
                people = store.viewers(graph)
                ids = sorted(p["uid"] for p in people)
                if ids != last_viewers:
                    last_viewers = ids
                    yield _sse("viewers", {"graph": graph, "viewers": people})

                held = store.locks(graph)
                shape = [(l["elementId"], l["uid"]) for l in held]
                if shape != last_locks:
                    last_locks = shape
                    yield _sse("locks", {"graph": graph, "locks": held})

                if ticks % PING_EVERY == 0:
                    yield _sse("ping", {"rev": last})
        finally:
            # 브라우저가 창을 닫으면 여기로 온다. TTL 을 기다리지 않는다.
            store.leave(graph, uid)
            store.release_all(graph, uid)

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            # nginx 가 SSE 를 버퍼링하면 한참 뒤에 몰아서 온다.
            "X-Accel-Buffering": "no",
        },
    )


def _sse(event: str, data: dict) -> bytes:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n".encode()
