"""PC → 중앙 계정 API. 권한 조회 실패 때 로컬 토큰/DB로 폴백하지 않는다."""
from __future__ import annotations

import os
from urllib.parse import urlsplit

import httpx
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse, Response


def authority_url() -> str:
    raw = (os.environ.get("ROBO_AUTHORITY_URL") or "").strip().rstrip("/")
    if not raw:
        return ""
    parsed = urlsplit(raw)
    if (parsed.scheme not in ("https", "http") or not parsed.hostname
            or parsed.username or parsed.password or parsed.query or parsed.fragment
            or parsed.path not in ("", "/")):
        raise RuntimeError("ROBO_AUTHORITY_URL은 중앙 서버의 origin이어야 합니다.")
    if parsed.scheme != "https" and parsed.hostname not in ("127.0.0.1", "localhost", "::1"):
        raise RuntimeError("중앙 권한 API는 HTTPS로 연결해야 합니다.")
    return raw


class AuthorityUnavailable(RuntimeError):  # noqa: N818
    """중앙 권한 서버를 확인할 수 없다."""


def introspect(token: str) -> dict:
    try:
        with httpx.Client(timeout=5, trust_env=False, follow_redirects=False) as client:
            response = client.post(authority_url() + "/api/auth/introspect",
                                   headers={"Authorization": "Bearer " + token})
    except (httpx.HTTPError, RuntimeError) as exc:
        raise AuthorityUnavailable("중앙 권한 서버에 연결할 수 없습니다.") from exc
    if response.status_code in (401, 403):
        from api.features.auth.tokens import TokenError
        raise TokenError("중앙 서버가 세션을 거절했습니다.")
    if response.status_code != 200:
        raise AuthorityUnavailable("중앙 권한 서버를 확인할 수 없습니다.")
    try:
        claims = response.json()
        if not isinstance(claims, dict) or not claims.get("sub") or claims.get("approved") is not True:
            raise ValueError("invalid claims")
        return claims
    except (ValueError, TypeError) as exc:
        raise AuthorityUnavailable("중앙 권한 서버의 응답이 올바르지 않습니다.") from exc


def delegated_path(path: str) -> bool:
    # 프로젝트 모델 컨텍스트는 PC의 그래프 바인딩을 사용한다.
    return (path == "/api/auth" or path.startswith("/api/auth/")
            or path == "/api/accounts" or path.startswith("/api/accounts/")
            or path == "/api/projects" or path.startswith("/api/projects/")
            or path == "/api/code-templates/sets" or path.startswith("/api/code-templates/sets/"))


class AuthorityProxyMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        try:
            origin = authority_url()
        except RuntimeError:
            return JSONResponse({"detail": "중앙 권한 서버 주소 설정을 확인하세요."}, status_code=503)
        if not origin or not delegated_path(request.url.path) or request.method == "OPTIONS":
            return await call_next(request)
        # PC의 신원/역할/연결/forwarded 헤더는 중앙 서버의 권한 근거가 될 수 없다.
        headers = {name: request.headers[name] for name in
                   ("authorization", "content-type", "accept", "x-project-graph")
                   if name in request.headers}
        try:
            async with httpx.AsyncClient(timeout=20, trust_env=False, follow_redirects=False) as client:
                response = await client.request(request.method, origin + request.url.path,
                                                params=list(request.query_params.multi_items()),
                                                headers=headers, content=await request.body())
        except httpx.HTTPError:
            return JSONResponse({"detail": "중앙 권한 서버에 연결할 수 없습니다."}, status_code=503)
        return Response(response.content, status_code=response.status_code,
                        headers={name: response.headers[name] for name in ("content-type", "location")
                                 if name in response.headers})
