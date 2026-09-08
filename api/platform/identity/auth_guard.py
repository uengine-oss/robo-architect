"""인증 강제 미들웨어.

`IdentityMiddleware` 는 설계상 **절대 401 을 내지 않는다**(그 파일의 주석에 명시).
로컬 데스크톱 신뢰 모델에서는 맞는 선택이지만, 사내 배포에서는 헤더만 있으면
누구나 통과한다. 이 미들웨어가 그 위에 얹혀 기업 모드에서만 문을 잠근다.

```
AUTH_ENFORCE 가 꺼져 있으면   아무것도 하지 않는다 (지금까지의 동작)
켜져 있으면                   Bearer 토큰이 있고 승인된 사용자만 통과
```

**기본이 꺼짐인 이유**는 이 스위치가 켜지는 순간 프런트엔드에 로그인 화면이
없으면 화면이 통째로 막히기 때문이다. 배선이 끝난 뒤 환경에서 켠다.

열어 두는 경로는 인증 자체와 상태 확인, 그리고 문서·헬스뿐이다. 목록을 넓히면
그만큼 구멍이 되므로 접두사로 느슨하게 열지 않고 하나씩 적는다.
"""

from __future__ import annotations

import os

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.types import ASGIApp

from api.features.auth.tokens import TokenError, verify_token
from api.platform.observability.smart_logger import SmartLogger

_TRUE = ("1", "true", "yes", "on")

# 인증 없이 닿을 수 있는 자리. 로그인하려면 여기가 열려 있어야 한다.
_OPEN_EXACT = frozenset({
    "/health", "/healthz", "/docs", "/redoc", "/openapi.json", "/favicon.ico",
    "/api/auth/provider", "/api/auth/sso/init", "/api/auth/sso/valid",
    "/api/auth/dev-login", "/api/auth/me",
})
# 정적 자산은 접두사로 연다 — 로그인 화면을 그리는 데 필요하다.
_OPEN_PREFIX = ("/assets/", "/static/", "/@vite/", "/node_modules/")


def auth_enforced() -> bool:
    return (os.environ.get("AUTH_ENFORCE") or "").strip().lower() in _TRUE


def _is_open(path: str) -> bool:
    return path in _OPEN_EXACT or path.startswith(_OPEN_PREFIX)


class AuthGuardMiddleware(BaseHTTPMiddleware):
    """기업 모드에서 인증되지 않은 요청을 401 로 막는다."""

    async def dispatch(self, request: Request, call_next):
        if not auth_enforced() or request.method == "OPTIONS" or _is_open(request.url.path):
            return await call_next(request)

        header = request.headers.get("authorization") or ""
        token = header[7:].strip() if header[:7].lower() == "bearer " else None
        try:
            claims = verify_token(token)
        except TokenError as exc:
            SmartLogger.log(
                "INFO", "인증되지 않은 요청을 막았다.",
                category="auth.guard.denied",
                params={"path": request.url.path, "reason": str(exc)},
            )
            return JSONResponse(
                {"detail": "로그인이 필요합니다.", "code": "AUTH_REQUIRED"},
                status_code=401,
            )

        if not claims.get("approved"):
            # 승인 대기·거절. 403 으로 구분해야 화면이 "다시 로그인"이 아니라
            # "승인을 기다리는 중"을 보여줄 수 있다.
            return JSONResponse(
                {"detail": "승인 대기 중인 계정입니다.", "code": "AUTH_NOT_APPROVED"},
                status_code=403,
            )

        request.state.auth_claims = claims
        return await call_next(request)
