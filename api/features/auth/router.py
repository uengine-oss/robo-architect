"""기업 인증 라우트.

```
GET      /api/auth/provider          현재 provider와 설정 상태 (진단)
GET      /api/auth/sso/init          SWP 로그인 URL 발급
GET|POST /api/auth/sso/valid         SWP 콜백 — ssoToken 검증
```

기준 구현(`local-msaez` data-gateway)은 이 뒤에 JWT 발급 · 사용자 upsert ·
승인 상태 판정까지 이어진다. 그 부분은 사용자 저장소 설계가 선행돼야 하므로
여기서는 **신원 확인까지만** 담당한다 — `enterprise-todo.md` ENT-AUTH-002.
"""

from __future__ import annotations

from fastapi import APIRouter, Form, HTTPException, Query, Request
from fastapi.responses import RedirectResponse

from api.features.auth.config import (
    AuthProvider,
    SwpSettings,
    auth_provider,
    callback_allowlist,
    is_allowed_callback,
)
from api.features.auth.swp import build_redirect_url, validate_sso_token
from api.platform.embeddings import describe as describe_embeddings
from api.platform.observability.request_logging import http_context
from api.platform.observability.smart_logger import SmartLogger

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _require_swp() -> SwpSettings:
    if auth_provider() is not AuthProvider.SWP:
        raise HTTPException(
            status_code=404,
            detail="SWP SSO 가 활성화돼 있지 않습니다. AUTH_PROVIDER=swp 로 설정하세요.",
        )
    return SwpSettings.from_env()


@router.get("/provider")
async def get_provider() -> dict:
    """현재 인증 설정 상태. 비밀값은 담지 않는다.

    LLM 라우팅 상태를 함께 반환한다 — 사내 게이트웨이 전환은 인증과 함께
    설정되므로, 한 번에 확인할 수 있어야 현장에서 오설정을 빨리 잡는다.
    """
    provider = auth_provider()
    payload: dict = {
        "provider": provider.value,
        "enterprise": provider is not AuthProvider.NONE,
        "callbackAllowlist": callback_allowlist(),
        "embeddings": describe_embeddings(),
    }

    if provider is AuthProvider.SWP:
        settings = SwpSettings.from_env()
        payload["swp"] = {
            "redirectUrl": settings.redirect_url,
            "validCheckUrl": settings.valid_check_url,
            "loginUrl": settings.login_url,
            "fieldIndexes": {
                "id": settings.idx_id,
                "empno": settings.idx_empno,
                "displayName": settings.idx_display_name,
                "mail": settings.idx_mail,
                "dept": settings.idx_dept,
            },
            "emailFallbackDomain": settings.email_fallback_domain,
        }
    return payload


@router.get("/sso/init")
async def sso_init(request: Request, callbackUrl: str = Query(..., min_length=1)) -> dict:
    """SWP 로그인 페이지 URL 을 발급한다.

    `callbackUrl` 은 허용 목록으로 검증한다. 검증 없이 그대로 실으면 SWP 를
    경유한 Open Redirect 가 된다.
    """
    settings = _require_swp()

    if not is_allowed_callback(callbackUrl):
        SmartLogger.log(
            "WARN",
            "Rejected SSO callback URL outside the allowlist.",
            category="auth.sso.callback_rejected",
            params={**http_context(request), "callback_url": callbackUrl},
        )
        raise HTTPException(status_code=400, detail="허용되지 않은 callbackUrl 입니다.")

    return {"redirectUrl": build_redirect_url(settings, callbackUrl)}


async def _handle_valid(request: Request, sso_token: str | None) -> RedirectResponse | dict:
    settings = _require_swp()

    # 토큰이 없거나 검증에 실패하면 SWP 로그인 홈으로 되돌려보낸다 (기준 구현 동작).
    if not sso_token:
        return RedirectResponse(settings.login_url, status_code=302)

    user, raw = await validate_sso_token(settings, sso_token)

    if user is None:
        SmartLogger.log(
            "WARN",
            "SWP SSO validation failed.",
            category="auth.sso.invalid",
            # 원문은 사용자 정보를 포함하므로 길이만 남긴다. 필드 순서 확인이
            # 필요하면 SWP_SSO_LOG_RAW 로 한시적으로 켠다.
            params={**http_context(request), "raw_length": len(raw or "")},
        )
        return RedirectResponse(settings.login_url, status_code=302)

    SmartLogger.log(
        "INFO",
        "SWP SSO validated.",
        category="auth.sso.validated",
        params={**http_context(request), "empno": user.empno, "username": user.username},
    )

    # NOTE: 세션/JWT 발급과 승인 상태 판정은 ENT-AUTH-002 에서 붙인다.
    # 지금은 신원 확인 결과만 돌려준다.
    return {"authenticated": True, "user": user.to_dict()}


@router.get("/sso/valid")
async def sso_valid_get(request: Request, ssoToken: str | None = Query(default=None)):
    return await _handle_valid(request, ssoToken)


@router.post("/sso/valid")
async def sso_valid_post(request: Request, ssoToken: str | None = Form(default=None)):
    # SWP EP 는 보통 form POST 로 되돌려보내지만 환경에 따라 GET 으로 오는
    # 사례가 있어 양쪽을 모두 받는다 (기준 구현과 동일).
    return await _handle_valid(request, ssoToken)
