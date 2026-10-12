"""VM 전용 중앙 계정·템플릿 API: uvicorn api.authority:app.

개발 로그인·로컬 인증 스위치가 이 서버의 권한 검사를 끄지 못한다.
DB DDL은 scripts.accounts_admin migrate에서 먼저 수행한다.
"""
from __future__ import annotations

import os
from contextlib import asynccontextmanager

import psycopg
from fastapi import FastAPI, HTTPException, Request
from starlette.responses import JSONResponse

from api.features.accounts import store
from api.features.accounts.authority_client import authority_url
from api.features.auth.tokens import TokenError, jwt_secret_configured, verify_token
from api.platform import pg


@asynccontextmanager
async def lifespan(app):
    if authority_url():
        raise RuntimeError("중앙 서버에는 ROBO_AUTHORITY_URL을 설정하지 않습니다.")
    if not jwt_secret_configured() or len(os.environ.get("AUTH_JWT_SECRET", "").strip()) < 32:
        raise RuntimeError("중앙 서버의 AUTH_JWT_SECRET이 필요합니다.")
    from api.features.auth.config import AuthProvider, auth_provider
    if auth_provider() is not AuthProvider.SWP:
        raise RuntimeError("중앙 서버는 AUTH_PROVIDER=swp로 설정해야 합니다.")
    # 서버 runtime 자격은 superuser가 아니다. 스키마도 여기서 만들지 않는다.
    role = pg.query("SELECT rolsuper, rolcreaterole, rolcreatedb, rolbypassrls "
                    "FROM pg_roles WHERE rolname = current_user")[0]
    if any(role.values()):
        raise RuntimeError("중앙 API에는 제한된 DB runtime 자격을 사용해야 합니다.")
    store.get_policy()
    operator_dsn = os.environ.get("ROBO_PROJECT_OPERATOR_DSN", "").strip()
    if operator_dsn:
        if len(os.environ.get("AUTH_ROLE_SECRET", "").strip()) < 32:
            raise RuntimeError("프로젝트 서버의 AUTH_ROLE_SECRET이 필요합니다.")
        with pg.using_dsn(operator_dsn):
            operator = pg.query("SELECT current_user AS name, current_database() AS db")[0]
            pg.query("SELECT graph FROM public.app_projects LIMIT 0")
        runtime = pg.query("SELECT current_user AS name, current_database() AS db")[0]
        if operator["name"] == runtime["name"] or operator["db"] != runtime["db"]:
            raise RuntimeError("프로젝트 운영 자격은 같은 DB의 별도 서버 역할이어야 합니다.")
    os.environ["ROBO_AUTHORITY_SERVER"] = "1"
    yield


app = FastAPI(title="Robo central account authority", lifespan=lifespan,
              docs_url=None, redoc_url=None, openapi_url=None)


def current_claims(request: Request) -> dict:
    header = request.headers.get("authorization") or ""
    token = header[7:].strip() if header[:7].lower() == "bearer " else None
    try:
        claims = verify_token(token)
    except TokenError as exc:
        raise HTTPException(401, "로그인이 필요합니다.") from exc
    store.require_initialized()
    user = store.get_user(str(claims.get("sub") or ""))
    if not store.is_approved(user) or claims.get("src") == "dev":
        raise HTTPException(403, "승인된 실제 인증 계정이 필요합니다.")
    return {**claims, "role": store.resolve_role(user), "approved": True}


_OPEN = {"/healthz", "/api/auth/provider", "/api/auth/sso/init", "/api/auth/sso/valid",
         "/api/auth/me", "/api/auth/figma-exchange"}


@app.middleware("http")
async def central_guard(request: Request, call_next):
    if request.url.path == "/api/auth/dev-login":
        return JSONResponse({"detail": "중앙 서버에서는 개발 로그인을 허용하지 않습니다."}, status_code=404)
    try:
        if request.url.path not in _OPEN:
            claims = current_claims(request)
            if claims.get("scope") and request.url.path != "/api/auth/introspect":
                raise HTTPException(403, "일반 사용자 세션이 필요합니다.")
            request.state.auth_claims = claims
        if request.url.path == "/api/projects" or request.url.path.startswith("/api/projects/"):
            if request.url.path == "/api/projects/adopt" and claims.get("role") != "admin":
                raise HTTPException(403, "기존 그래프 이관은 중앙 관리자만 할 수 있습니다.")
            operator_dsn = os.environ.get("ROBO_PROJECT_OPERATOR_DSN", "").strip()
            if not operator_dsn:
                return JSONResponse({"detail": "서버 프로젝트 운영 자격을 설정하세요."}, status_code=503)
            # Authentication and current approval were checked using limited runtime credentials.
            # Only fixed project routes inherit this server-owned credential scope.
            with pg.using_dsn(operator_dsn):
                return await call_next(request)
        return await call_next(request)
    except HTTPException as exc:
        return JSONResponse({"detail": exc.detail}, status_code=exc.status_code)
    except (store.AuthorityNotInitialized, pg.PgUnavailable, psycopg.Error):
        return JSONResponse({"detail": "중앙 권한 저장소를 초기화하거나 연결을 확인하세요."}, status_code=503)


@app.get("/healthz")
def health():
    policy = store.get_policy()
    return {"status": "ok", "initialized": policy["initialized"]}


@app.post("/api/auth/introspect")
def introspect_session(request: Request):
    # Middleware의 DB 최신 조회 결과. 플러그인 토큰은 일반 API에 재사용하지 않는다.
    return request.state.auth_claims


@app.get("/api/auth/provider")
async def central_provider():
    from api.features.auth.router import get_provider
    payload = await get_provider()
    payload.update(enforce=True, bindConnection=True,
                   devLogin={"enabled": False, "accounts": [], "allowRemote": False})
    payload["authorityInitialized"] = store.get_policy()["initialized"]
    return payload


from api.features.accounts.router import router as accounts_router  # noqa: E402
from api.features.auth.router import router as auth_router  # noqa: E402
from api.features.code_templates.router import router as templates_router  # noqa: E402
from api.features.projects.router import router as projects_router  # noqa: E402

app.include_router(accounts_router)
app.include_router(auth_router)
app.include_router(projects_router)
# /context는 프로젝트별 그래프에 붙는 PC에서 처리한다.
for route in templates_router.routes:
    if route.path != "/api/code-templates/context":
        app.router.routes.append(route)
