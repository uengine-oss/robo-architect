# -*- coding: utf-8 -*-
"""`/api/gateway/**` 를 **로그인을 본 뒤에** Analyzer API Gateway 로 넘긴다.

## 왜 생겼나 — 서버 배포(posco-web)

설치본에서는 이 경로를 Electron 의 `app://` 핸들러가 받아 **gateway 로 곧장**
보냈다(`desktop/src/main/index.ts` `registerAppProtocol`). 이 앱을 거치지 않았으므로
`AuthGuardMiddleware` 도 거치지 않았다. PC 한 대 · 사용자 한 명 · 루프백이라
문제가 안 됐다.

서버에 올리면 그 길이 **사내망 전체에 열린다.** gateway 뒤에는 analyzer·catalog·
fabric 이 있고, 거기에는 레거시 분석 그래프와 **데이터 소스 질의**가 있다. nginx 가
gateway 로 곧장 보내면 로그인 없이 누구나 그것을 읽는다. 그래서 nginx 는
`/api/gateway/**` 를 **이 앱으로** 보내고, 여기서 다음 셋을 본 뒤 넘긴다.

1. **로그인** — 이 경로는 `_OPEN_EXACT` 에 없으므로 `AuthGuardMiddleware` 가 먼저 본다.
2. **연결 자격은 브라우저에서 받지 않는다** — `X-Neo4j-URI/User/Password` 는 버린다.
   catalog·fabric 은 `*_ALLOW_NEO4J_HEADER_OVERRIDE=true` 라 그 헤더를 믿는다.
3. **그래프는 내 프로젝트 것만** — `X-Neo4j-Database` 가 오면, 그것이 내가 등급을
   가진 프로젝트의 설계·분석 graph 일 때만 넘긴다. 쓰기(POST 등)는 write 이상.

## `/robo/analyze` 요청 본문을 좁힌다

Electron 핸들러가 하던 일을 그대로 옮겼다. 분석기 화면은 Parser 용 메타데이터까지
통째로 보내는데(`target`·`nameCase`·`inferFkRelations`·`targetFolder`·
`project_root`), 분석기의 `AnalyzeRequest` 는 `extra="forbid"` 라 **422** 다.
화면에는 `[object Object]` 네 개로 보였다. 데스크톱에서는 이 보정이 핸들러에 숨어
있어서, 브라우저로 옮기면 **레거시 분석 첫 단계에서 바로** 막힌다.

⚠ 같은 보정이 두 곳에 있다(`index.ts` · 여기). 고칠 때는 **둘 다** 본다 —
  아니면 분석기 화면을 고쳐 보정 자체를 없앤다.
"""

from __future__ import annotations

import json
import os

import httpx
from fastapi import APIRouter, HTTPException, Request
from starlette.background import BackgroundTask
from starlette.responses import StreamingResponse

from api.features.projects import store as projects
from api.features.projects.access import request_uid

router = APIRouter(tags=["gateway-proxy"])

# 이 앱이 정한다 — 브라우저가 보낸 값은 넘기지 않는다.
_DROP_REQUEST = frozenset({
    "host", "content-length", "connection", "keep-alive", "transfer-encoding",
    "upgrade", "proxy-connection", "te", "trailer",
    "x-neo4j-uri", "x-neo4j-user", "x-neo4j-password",
})
_DROP_RESPONSE = frozenset({
    "content-length", "connection", "keep-alive", "transfer-encoding",
    "upgrade", "proxy-connection", "te", "trailer",
})
_READ_METHODS = frozenset({"GET", "HEAD"})


def _gateway_base() -> str:
    return (os.environ.get("ROBO_GATEWAY_URL") or "http://gateway:9000").strip().rstrip("/")


def _strict() -> bool:
    """`access.require_write` 와 같은 기준 — 중앙 구성이면 빈 신원을 거절한다."""
    return (os.environ.get("ROBO_GRAPH_MODE", "").strip().lower() == "central"
            or bool(os.environ.get("ROBO_AUTHORITY_URL", "").strip()))


def _check_graph(request: Request) -> None:
    graph = (request.headers.get("x-neo4j-database") or "").strip()
    if not graph:
        # 헤더가 없으면 각 서비스가 자기 기본 graph(`NEO4J_DATABASE` = 공용 분석 graph)
        # 를 쓴다. 그것은 설치본과 같은 동작이고, 프로젝트 graph 는 아니다.
        return
    uid = request_uid(request)
    if not uid:
        if _strict():
            raise HTTPException(status_code=403, detail="로그인 후 프로젝트를 선택하세요.")
        return
    try:
        mine = projects.list_projects(uid)
    except Exception:
        raise HTTPException(status_code=503, detail="프로젝트 권한을 확인할 수 없습니다.")
    for project in mine:
        if graph in (project.get("graph"), project.get("analyzerGraph")):
            level = project.get("level")
            if request.method not in _READ_METHODS and level not in ("write", "admin"):
                raise HTTPException(status_code=403, detail="이 프로젝트에 쓰기 권한이 없습니다.")
            return
    raise HTTPException(status_code=403, detail="이 그래프에 접근할 권한이 없습니다.")


async def _narrow_analyze_body(request: Request) -> bytes:
    try:
        data = json.loads(await request.body() or b"{}")
    except ValueError:
        raise HTTPException(status_code=400, detail="분석 요청 본문이 JSON 이 아닙니다.")
    if not isinstance(data, dict):
        raise HTTPException(status_code=400, detail="분석 요청 본문이 객체가 아닙니다.")
    narrowed = {
        "strategy": data.get("strategy"),
        "locale": data["locale"] if isinstance(data.get("locale"), str) else "ko",
        "selected_source_ids": data["selected_source_ids"]
        if isinstance(data.get("selected_source_ids"), list) else [],
        "datasource": data.get("datasource", data.get("datasourceName")),
    }
    return json.dumps(narrowed, ensure_ascii=False).encode("utf-8")


@router.api_route(
    "/api/gateway/{path:path}",
    methods=["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD"],
    include_in_schema=False,
)
async def gateway_proxy(path: str, request: Request):
    _check_graph(request)

    headers = {k: v for k, v in request.headers.items() if k.lower() not in _DROP_REQUEST}
    if request.method == "POST" and path == "robo/analyze":
        content: object = await _narrow_analyze_body(request)
        headers["content-type"] = "application/json"
    elif request.method in _READ_METHODS:
        content = None
    else:
        # 소스 업로드가 이 길로 온다 — **메모리에 다 올리지 않고** 흘려 보낸다.
        content = request.stream()

    # 분석은 SSE 로 수십 분 간다. 읽기 시한을 두지 않는다(연결만 시한을 둔다).
    client = httpx.AsyncClient(timeout=httpx.Timeout(None, connect=10.0))
    upstream = client.build_request(
        request.method,
        f"{_gateway_base()}/api/gateway/{path}",
        params=request.query_params,
        headers=headers,
        content=content,
    )
    try:
        response = await client.send(upstream, stream=True)
    except httpx.HTTPError as exc:
        await client.aclose()
        raise HTTPException(status_code=502, detail=f"분석 게이트웨이에 닿지 못했습니다: {type(exc).__name__}")

    async def close() -> None:
        await response.aclose()
        await client.aclose()

    out_headers = {k: v for k, v in response.headers.items() if k.lower() not in _DROP_RESPONSE}
    # nginx 가 SSE 를 모았다가 한꺼번에 내보내지 않게 한다(백엔드의 다른 SSE 와 같은 처리).
    out_headers["X-Accel-Buffering"] = "no"
    return StreamingResponse(
        response.aiter_raw(),
        status_code=response.status_code,
        headers=out_headers,
        background=BackgroundTask(close),
    )
