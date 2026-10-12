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

import os
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

    중앙 구성은 로그인·프로젝트 선택·현재 쓰기 등급을 모두 확인하고,
    저장소 장애 때 실행을 거절한다. 단일 PC 구성은 기존 호환 동작을 유지한다.
    앱 관리자 역할이 아니라 프로젝트 write/admin 등급이 실행 근거다.
    """
    graph = request_graph(request)
    uid = request_uid(request)
    strict = (os.environ.get("ROBO_GRAPH_MODE", "").strip().lower() == "central"
              or bool(os.environ.get("ROBO_AUTHORITY_URL", "").strip()))
    if not graph or not uid:
        if strict:
            raise HTTPException(status_code=403, detail="로그인 후 프로젝트를 선택하세요.")
        return
    try:
        level = projects.level_of(uid, graph)
    except Exception:
        if strict:
            raise HTTPException(status_code=503, detail="프로젝트 쓰기 권한을 확인할 수 없습니다.")
        # 등급을 못 읽는 것은 **거절의 근거가 아니다.** 뒤에서 다시 걸린다.
        return
    if level == "read":
        raise HTTPException(status_code=403, detail=_READ_ONLY_DETAIL)
    if strict and level not in ("write", "admin"):
        raise HTTPException(status_code=403, detail="이 프로젝트에 쓰기 권한이 없습니다.")
