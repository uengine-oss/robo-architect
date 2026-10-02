# -*- coding: utf-8 -*-
"""프로젝트 등급으로 **쓰기를 가르는** 한 자리.

## 왜 따로 두나

같은 판정이 여러 라우터에 흩어지면 한 곳이 빠진다. 그리고 **빠진 곳은 조용하다** —
2026-10-02 에 그 모양을 실제로 봤다.

읽기 등급 사용자가 `POST /api/ingest/hybrid/upload` 를 불렀더니 **200 과 세션
아이디**가 나왔다. 워크플로가 돌면서 **임베딩을 실제로 호출하고**(돈이 든다)
첫 쓰기에서 Postgres 가 막았다 —

    Neo.ClientError.Security.Forbidden: permission denied for table og_role_player

데이터는 안전했다. 막은 것은 **DB** 다. 그런데 사람에게는 아무 말도 안 갔다 —
SSE 로 0바이트가 왔다. **"조용히 아무 일도 안 일어난다" 에 비용까지 붙은 꼴**이다.

그래서 **일을 시작하기 전에** 가른다. 거절은 비싸지 않고, 침묵은 비싸다.
"""

from __future__ import annotations

from fastapi import HTTPException, Request

from api.features.projects import store as projects
from api.features.auth.tokens import TokenError, verify_token

__all__ = ["request_uid", "request_graph", "require_write"]

_READ_ONLY_DETAIL = "읽기 권한으로는 편집할 수 없습니다."


def request_uid(request: Request) -> str:
    """토큰이 말하는 사람. 없으면 빈 문자열 — 인증은 미들웨어가 이미 본다."""
    raw = request.headers.get("authorization") or ""
    token = raw[7:].strip() if raw[:7].lower() == "bearer " else None
    if not token:
        return ""
    try:
        return str(verify_token(token).get("sub") or "")
    except TokenError:
        return ""


def request_graph(request: Request) -> str:
    """이 요청이 가리키는 프로젝트. 없으면 빈 문자열."""
    return (
        request.headers.get("x-project-graph")
        or request.headers.get("x-neo4j-database")
        or ""
    ).strip()


def require_write(request: Request) -> None:
    """이 요청이 **쓸 수 있는가**. 못 쓰면 403 으로 **지금** 끝낸다.

    프로젝트를 안 골랐거나 등급을 모르면 **막지 않는다** — 그 판정은 연결
    바인딩(`AUTH_BIND_CONNECTION`)과 각 라우터가 이미 한다. 여기서 또 막으면
    단일 PC 구성(등급 표가 비어 있다)에서 멀쩡하던 길이 닫힌다.
    """
    graph = request_graph(request)
    uid = request_uid(request)
    if not graph or not uid:
        return
    try:
        level = projects.level_of(uid, graph)
    except Exception:
        # 등급을 못 읽는 것은 **거절의 근거가 아니다.** 뒤에서 다시 걸린다.
        return
    if level == "read":
        raise HTTPException(status_code=403, detail=_READ_ONLY_DETAIL)
