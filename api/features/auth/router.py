"""기업 인증 라우트.

```
GET      /api/auth/provider          현재 provider와 설정 상태 (진단)
GET      /api/auth/sso/init          SWP 로그인 URL 발급
GET|POST /api/auth/sso/valid         SWP 콜백 — ssoToken 검증 + 세션 발급
POST     /api/auth/dev-login         사내망 밖 개발용 우회 (기본 꺼짐)
GET      /api/auth/me                내 세션 상태
```

신원 확인 뒤 **사용자 upsert → 승인 판정 → 세션 발급**까지 이어진다. 승인 대기·
거절 사용자에게는 토큰을 주지 않는다 — 토큰이 있으면 통과하는 구조라, 여기서
막지 않으면 뒤에서 다시 막을 자리가 마땅치 않다.
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
from api.features.auth.dev_login import DevLoginSettings, describe as describe_dev_login, is_loopback
from api.features.auth.swp import build_redirect_url, validate_sso_token
from api.features.auth.tokens import (
    TokenError, issue_token, jwt_secret_configured, token_ttl_seconds, verify_token,
)
from api.features.accounts import store as accounts
from api.platform.identity.auth_guard import auth_enforced
from api.platform.identity.connection_binding import binding_enabled
from api.platform.ai_gateway import describe as describe_ai_gateway
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
        # AI 호출 여섯 갈래가 지금 어디를 보는가. 옮겨지지 않는 갈래를
        # 이름으로 부르는 것이 이 값의 목적이다 — 조용히 초록이면 안 된다.
        "aiGateway": describe_ai_gateway(),
        # 우회로가 열려 있으면 진단에서 바로 보여야 한다. 조용히 열린 채로 두는
        # 것이 이 기능의 유일한 실패 방식이다.
        "devLogin": describe_dev_login(),
        "approvalRequired": accounts.approval_enabled(),
        "jwtSecretConfigured": jwt_secret_configured(),
        "sessionTtlSeconds": token_ttl_seconds(),
        # 화면이 로그인 게이트를 걸지 말지 정하는 값. 서버가 강제하지 않는데
        # 화면만 막으면 쓰던 사람이 갑자기 못 들어온다.
        "enforce": auth_enforced(),
        "bindConnection": binding_enabled(),
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

    return _sign_in(request, user.to_dict(), source="swp")


@router.get("/sso/valid")
async def sso_valid_get(request: Request, ssoToken: str | None = Query(default=None)):
    return await _handle_valid(request, ssoToken)


@router.post("/sso/valid")
async def sso_valid_post(request: Request, ssoToken: str | None = Form(default=None)):
    # SWP EP 는 보통 form POST 로 되돌려보내지만 환경에 따라 GET 으로 오는
    # 사례가 있어 양쪽을 모두 받는다 (기준 구현과 동일).
    return await _handle_valid(request, ssoToken)


# ── 세션 발급 ────────────────────────────────────────────────────────

def _sign_in(request: Request, identity: dict, source: str) -> dict:
    """확인된 신원으로 사용자를 만들고 세션을 준다.

    승인 대기·거절이면 **토큰을 주지 않는다.** 상태만 돌려주어 화면이 안내를
    띄우게 한다. 토큰을 주고 나중에 막는 구조는 막을 자리를 하나 더 만든다.
    """
    try:
        accounts.ensure_schema()
        user = accounts.upsert_from_sso(identity)
    except Exception as exc:  # 저장소가 없거나 붙지 못하는 경우
        SmartLogger.log(
            "ERROR", "사용자 저장소에 접근하지 못해 로그인을 마치지 못했다.",
            category="auth.signin.store_unavailable",
            params={**http_context(request), "error": str(exc)[:200], "source": source},
        )
        raise HTTPException(status_code=503, detail="사용자 저장소에 접근할 수 없습니다.")

    status = accounts.resolve_status(user)
    approved = accounts.is_approved(user)
    SmartLogger.log(
        "INFO", "로그인 처리됨.",
        category="auth.signin",
        params={
            **http_context(request), "uid": user.get("uid"), "status": status,
            "role": accounts.resolve_role(user), "source": source,
        },
    )
    payload = {
        "authenticated": approved,
        "status": status,
        "user": {
            "uid": user.get("uid"),
            "displayName": user.get("displayName"),
            "department": user.get("department"),
            "role": accounts.resolve_role(user),
            "status": status,
            "source": source,
        },
    }
    if approved:
        payload["accessToken"] = issue_token(user, source=source)
        payload["expiresIn"] = token_ttl_seconds()
    return payload


@router.post("/dev-login")
async def dev_login(
    request: Request,
    loginId: str = Form(...),
    password: str = Form(...),
) -> dict:
    """사내망 밖에서 쓰는 우회 로그인.

    SWP 는 사내망에서만 응답하므로, 밖에서는 이 길이 없으면 아무것도 확인할 수
    없다. 기본은 꺼져 있고 루프백만 허용한다.
    """
    settings = DevLoginSettings.from_env()
    if not settings.enabled:
        raise HTTPException(status_code=404, detail="개발용 로그인이 꺼져 있습니다.")

    client_host = request.client.host if request.client else None
    if not settings.allow_remote and not is_loopback(client_host):
        SmartLogger.log(
            "WARN", "루프백이 아닌 곳에서 개발용 로그인을 시도했다.",
            category="auth.dev_login.remote_rejected",
            params={**http_context(request), "client": client_host},
        )
        raise HTTPException(status_code=403, detail="개발용 로그인은 같은 기계에서만 됩니다.")

    # 계정은 여럿일 수 있다 — 프로젝트 격리와 공유는 사람이 둘 이상이어야 확인된다.
    account = settings.find(loginId, password)
    if account is None:
        SmartLogger.log(
            "WARN", "개발용 로그인 자격이 맞지 않는다.",
            category="auth.dev_login.rejected",
            params={**http_context(request), "login_id_len": len(loginId or "")},
        )
        raise HTTPException(status_code=401, detail="아이디 또는 비밀번호가 다릅니다.")

    SmartLogger.log(
        "WARN", "개발용 우회 로그인이 사용됐다. 사내 배포본에서는 꺼져 있어야 한다.",
        category="auth.dev_login.used",
        params={**http_context(request), "employee_no": account.employee_no},
    )
    return _sign_in(request, account.identity(), source="dev")


@router.get("/me")
async def me(request: Request) -> dict:
    """내 세션 상태. 토큰이 없거나 낡았으면 인증되지 않았다고만 답한다.

    **저장된 상태를 다시 읽는다.** 승인이 취소됐는데 토큰이 아직 살아 있는 창을
    좁히기 위해서다 — 이 경로는 뜨겁지 않아 표를 한 번 더 읽어도 된다.
    """
    header = request.headers.get("authorization") or ""
    token = header[7:].strip() if header[:7].lower() == "bearer " else None
    try:
        claims = verify_token(token)
    except TokenError as exc:
        return {"authenticated": False, "reason": str(exc)}

    try:
        user = accounts.get_user(claims.get("sub", ""))
    except Exception:
        user = None

    status = accounts.resolve_status(user) if user else claims.get("status", "approved")
    approved = accounts.is_approved(user) if user else bool(claims.get("approved"))
    return {
        "authenticated": approved,
        "status": status,
        "user": {
            "uid": claims.get("sub"),
            "displayName": (user or {}).get("displayName") or claims.get("name"),
            "department": (user or {}).get("department") or claims.get("dept"),
            "role": accounts.resolve_role(user) if user else claims.get("role"),
            "status": status,
            "source": claims.get("src"),
        },
    }
