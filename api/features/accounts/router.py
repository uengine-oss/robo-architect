"""사용자 관리 라우트 — 관리자만.

```
GET    /api/accounts                 전체 목록 (status 로 좁힐 수 있다)
POST   /api/accounts/{uid}/status    승인 · 거절 · 되돌리기
POST   /api/accounts/{uid}/role      관리자 지정 · 해제
```

**자기 자신은 바꿀 수 없다.** 스스로를 승격시키는 길과, 마지막 관리자가 스스로를
내려 아무도 승인할 수 없게 되는 길을 함께 막는다.
"""

from __future__ import annotations

from fastapi import APIRouter, Body, HTTPException, Query, Request

from api.features.accounts import store
from api.features.auth.tokens import TokenError, verify_token
from api.platform.observability.request_logging import http_context
from api.platform.observability.smart_logger import SmartLogger

router = APIRouter(prefix="/api/accounts", tags=["accounts"])


def _require_admin(request: Request) -> str:
    """관리자의 사번. 아니면 401/403.

    클레임의 역할을 믿지 않고 **저장된 값을 다시 읽는다.** 관리자에서 내려온
    사람의 토큰이 만료 전까지 살아 있기 때문이다 — 사용자 관리는 뜨거운 경로가
    아니라 표를 한 번 더 읽어도 된다.
    """
    claims = getattr(request.state, "auth_claims", None)
    if not claims:
        header = request.headers.get("authorization") or ""
        token = header[7:].strip() if header[:7].lower() == "bearer " else None
        try:
            claims = verify_token(token)
        except TokenError:
            raise HTTPException(status_code=401, detail="로그인이 필요합니다.")
    uid = str(claims.get("sub") or "")
    store.ensure_schema()
    user = store.get_user(uid)
    if not store.is_admin(user):
        raise HTTPException(status_code=403, detail="관리자만 할 수 있습니다.")
    return uid


@router.get("")
async def list_accounts(request: Request, status: str | None = Query(default=None)) -> dict:
    _require_admin(request)
    users = store.list_by_status(status) if status else store.list_users()
    return {
        "users": users,
        "approvalRequired": store.approval_enabled(),
        "counts": {
            s: len(store.list_by_status(s))
            for s in (store.STATUS_PENDING, store.STATUS_APPROVED, store.STATUS_REJECTED)
        },
    }


@router.post("/{uid}/status")
async def set_status(request: Request, uid: str, body: dict = Body(...)) -> dict:
    admin_uid = _require_admin(request)
    if uid == admin_uid:
        raise HTTPException(status_code=403, detail="자기 계정의 상태는 바꿀 수 없습니다.")
    status = str((body or {}).get("status") or "")
    if status not in store.VALID_STATUSES:
        raise HTTPException(status_code=400, detail=f"알 수 없는 상태입니다: {status}")
    user = store.set_status(uid, status)
    if user is None:
        raise HTTPException(status_code=404, detail="그런 사용자가 없습니다.")
    SmartLogger.log(
        "INFO", "사용자 상태를 바꿨다.",
        category="accounts.status_changed",
        params={**http_context(request), "by": admin_uid, "uid": uid, "status": status},
    )
    return user


@router.post("/{uid}/role")
async def set_role(request: Request, uid: str, body: dict = Body(...)) -> dict:
    admin_uid = _require_admin(request)
    if uid == admin_uid:
        # 자기 승격도, 마지막 관리자가 스스로 내려오는 것도 여기서 막힌다.
        raise HTTPException(status_code=403, detail="자기 계정의 역할은 바꿀 수 없습니다.")
    role = str((body or {}).get("role") or "")
    if role not in (store.ROLE_ADMIN, store.ROLE_MEMBER):
        raise HTTPException(status_code=400, detail=f"알 수 없는 역할입니다: {role}")
    user = store.set_role(uid, role)
    if user is None:
        raise HTTPException(status_code=404, detail="그런 사용자가 없습니다.")
    SmartLogger.log(
        "INFO", "사용자 역할을 바꿨다.",
        category="accounts.role_changed",
        params={**http_context(request), "by": admin_uid, "uid": uid, "role": role},
    )
    return user
