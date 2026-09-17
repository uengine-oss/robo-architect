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


def _session(request: Request, body: dict | None = None) -> str | None:
    """이 요청이 **어느 창**에서 왔나.

    잠금의 수명을 이 값으로 잰다. 사람이 아니라 창을 세는 이유는, 한 사람이
    창을 둘 열었을 때 하나를 닫는다고 다른 창의 잠금이 죽으면 안 되기 때문이다.

    없으면 `None` — 그때는 세션 행을 안 만든다. **그러면 그 클라이언트의 잠금은
    아무도 안 살려 주므로 유예 뒤에 걷힌다.** 옛 화면·스크립트가 조용히 영구
    잠금을 만드는 것보다 낫다.
    """
    v = (
        request.headers.get("x-collab-session")
        or request.query_params.get("session")
        or ((body or {}).get("session") if isinstance(body, dict) else None)
        or ""
    )
    v = str(v).strip()
    return v[:64] or None


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
    # **이 호출이 창의 심장박동이다.** 화면은 스트림과 별개로 이것을 주기적으로
    # 부른다 — 프록시가 SSE 만 끊거나 재연결 백오프가 길어져도, 사람이 거기
    # 있다는 사실은 이 길로 계속 전해진다. 그 사실이 곧 잠금의 수명이다.
    store.heartbeat(graph, uid, _claims(request).get("name"), _session(request))
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
    # 잡는 것과 "붙어 있다"를 **같은 자리에서** 올린다. 따로 두면 잡자마자
    # 유예 안에 죽는 창이 생긴다 — 세션을 안 보내는 클라이언트가 그렇다.
    store.heartbeat(graph, uid, _claims(request).get("name"), _session(request, body))
    result = store.acquire_lock(
        graph, element_id, uid,
        display_name=_claims(request).get("name"),
        label=str((body or {}).get("label") or "")[:120] or None,
        session=_session(request, body),
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
    session = _session(request, body)
    if store.valid_graph(graph):
        store.leave(graph, uid, session)
        # **이 창이 잡은 것만 푼다.** 같은 사람의 다른 창이 고치고 있는 것까지
        # 놓아 버리면 안 되고, 반대로 "다른 창이 있으니 그대로 둔다"로 하면
        # 아무도 열고 있지 않은 요소가 잠긴 채 남는다. 둘 다 실제로 겪었다.
        store.release_all(graph, uid, session)
    return {"ok": True}


@router.get("/stream")
async def stream(request: Request) -> StreamingResponse:
    uid = _uid(request)
    graph = _graph(request, uid)
    display = _claims(request).get("name")
    session = _session(request)
    store.ensure_schema()
    # 스트림을 여는 이 요청 자체는 창이 진짜로 보낸 것이다 — 한 번은 찍는다.
    store.heartbeat(graph, uid, display, session)

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
                # **여기서 세션을 올리지 않는다.**
                #
                # 올렸더니 서버가 제 손으로 창을 살려 놨다. 창이 완전히 끊긴
                # 뒤에도(오프라인 실측) 이 고리가 계속 돌면서 "붙어 있다"를
                # 찍어, 선점이 60초가 지나도 안 풀렸다. **붙어 있다는 사실은
                # 창이 실제로 보낸 요청으로만 안다** — 서버의 고리는 그 증거가
                # 아니다.
                #
                # 접속자 표시는 이 고리로 갱신해도 된다. 그쪽은 "보여 줄까"의
                # 문제이고, 잘못돼도 남의 편집을 막지 않는다.
                store.heartbeat(graph, uid, display)
                store.refresh_locks(graph, uid)
                # 보유자가 사라진 잠금을 이 바퀴에 치운다. 숨기는 것으로는
                # 부족하다 — 행이 남으면 표를 들여다본 사람이 유령을 진짜로
                # 착각하고, 취득 경로가 그 행을 계속 만난다.
                store.sweep_absent_locks(graph)

                current = store.revision(graph)
                if current["rev"] != last:
                    # **무엇이 바뀌었는지 실을 수 있으면 싣는다.** 그러면 받는
                    # 쪽이 그 요소만 제자리에서 갈아끼우고, 통째로 다시 읽지
                    # 않으므로 편집 중이던 화면이 안 깨진다.
                    #
                    # 못 실으면(목록 없는 쓰기가 섞였거나 너무 뒤처졌으면)
                    # 목록 없이 보낸다 — 받는 쪽이 거친 길로 간다.
                    # **빈 목록과 "모른다"를 구별해야 한다**: 합치면 빠진 변경이
                    # 조용히 사라진다.
                    detail = store.changes_since(graph, last, current["rev"])
                    last = current["rev"]
                    payload = {"graph": graph, **current}
                    if detail is not None:
                        payload["changes"] = detail
                    yield _sse("changed", payload)

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
            # **여기서 아무것도 놓지 않는다.**
            #
            # 전에는 `leave` + `release_all` 이 있었다. 그래서 스트림이 끊기는
            # 순간 잠금이 풀렸다 — 프록시가 SSE 만 끊거나, 절전에서 깨거나,
            # 재연결 백오프가 도는 그 몇 초 사이에. 사람은 화면 앞에 앉아
            # 글자를 치고 있는데 서버는 이미 놓은 뒤였고, 그 틈에 남이 집어
            # 가면 돌아와서 저장할 때 409 를 맞았다. 실측: 끊고 10초 만에 사라진다.
            #
            # **스트림이 끊긴 것과 사람이 떠난 것은 다르다.** 떠난 것은 두 길로만
            # 안다 — 창이 알려 주거나(`/leave`), 심장박동이 유예만큼 멎거나.
            # 후자는 `sweep_absent_locks` 가 치운다.
            pass

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
