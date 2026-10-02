# -*- coding: utf-8 -*-
"""**관리자인가** 를 판정하는 한 자리.

사용자 관리(`accounts/router.py`)에만 있던 판정인데, 관리자만 할 수 있는 일이
둘로 늘었다 — 코드 생성 템플릿을 고치는 일이 붙었다(TPL-1). 같은 판정을 두 군데에
베껴 두면 한쪽만 고쳐지고, **느슨해진 쪽이 조용하다.**

## 클레임을 믿지 않는다

토큰의 역할은 발급 시점의 사실이다. 관리자에서 내려온 사람의 토큰은 만료 전까지
살아 있으므로, **저장된 값을 다시 읽는다.** 관리자 전용 경로는 뜨겁지 않아 표를 한
번 더 읽어도 된다.
"""

from __future__ import annotations

from fastapi import HTTPException, Request

from api.features.accounts import store
from api.features.auth.tokens import TokenError, verify_token

__all__ = ["require_admin", "current_uid"]


def current_uid(request: Request) -> str:
    """이 요청의 사람. 토큰이 없거나 낡았으면 401."""
    claims = getattr(request.state, "auth_claims", None)
    if not claims:
        header = request.headers.get("authorization") or ""
        token = header[7:].strip() if header[:7].lower() == "bearer " else None
        try:
            claims = verify_token(token)
        except TokenError:
            raise HTTPException(status_code=401, detail="로그인이 필요합니다.")
    return str(claims.get("sub") or "")


def require_admin(request: Request) -> str:
    """관리자의 사번. 아니면 401/403."""
    uid = current_uid(request)
    store.ensure_schema()
    if not store.is_admin(store.get_user(uid)):
        raise HTTPException(status_code=403, detail="관리자만 할 수 있습니다.")
    return uid
