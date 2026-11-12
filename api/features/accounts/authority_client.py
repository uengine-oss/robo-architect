"""PC → 중앙 계정 API. 권한 조회 실패 때 로컬 토큰/DB로 폴백하지 않는다."""
from __future__ import annotations

import json
import os
from ipaddress import ip_address, ip_network
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
    if parsed.scheme == "http" and not _internal_http_host(parsed.hostname):
        raise RuntimeError("HTTP 중앙 권한 API는 loopback 또는 사내망 IP만 허용합니다.")
    return raw


_INTRANET_NETWORKS = tuple(ip_network(cidr) for cidr in (
    "10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16", "fc00::/7",
))


def _internal_http_host(hostname: str) -> bool:
    if hostname == "localhost":
        return True
    # 점이 없는 한 단어 이름 — compose 서비스 이름(`authority`)이 이 모양이다.
    # 공용 DNS 에서는 풀리지 않고 컨테이너 망·사내 DNS 안에서만 닿는다. 서버 배포
    # (posco-web) 통합 서버가 이 이름으로 붙는다. IP 를 박으면 사내 대역과 겹칠 수 있다.
    if "." not in hostname and ":" not in hostname and hostname.replace("-", "").isalnum():
        return True
    try:
        address = ip_address(hostname)
    except ValueError:
        return False
    return address.is_loopback or any(address in network for network in _INTRANET_NETWORKS)


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


# `/api/auth/provider` 가 담는 AI 진단 칸. **이 프로세스가 답해야 하는 값**이다.
_LOCAL_AI_FIELDS = ("embeddings", "aiGateway")


def _overlay_local_ai(body: bytes) -> bytes:
    """중앙 응답의 AI 진단 칸을 **이 프로세스의 실제 설정**으로 덮는다.

    ⚠ 2026-11-12 실측: 서버 배포(posco-web) 통합 서버에서
    `curl /api/auth/provider` 가 `embeddings.baseUrl = https://api.openai.com/v1`,
    `keySource = inherited`, `chatBaseUrl = null` 을 돌려줬다. 그런데 같은 순간
    architect-api 컨테이너 안에서 `embeddings.describe()` 는
    `dedicated` + `.env` 가 정한 사내 주소를 돌려줬다. 응답이 **authority**
    컨테이너에서 계산되기 때문이다 — 그 컨테이너에는 `EMBEDDING_*` · `OPENAI_*`
    가 **한 줄도 없다**(실측 0개). 있을 이유도 없다: 임베딩을 부르는 것은
    architect-api 다.

    그러면 이 칸은 **둘 다 거짓**이 된다 — 제대로 맞춰 놔도 "본점으로 간다" 고
    하고, 잘못 맞춰 놔도 똑같이 말한다. 설정을 잡으려고 만든 칸이 설정을 못 본다.
    그래서 넘겨받은 본문에서 이 칸만 **여기서** 갈아 끼운다. 인증·승인 판단은
    그대로 중앙이 한다(이 함수는 AI 칸만 만진다).
    """
    try:
        payload = json.loads(body)
    except ValueError:
        return body
    if not isinstance(payload, dict):
        return body
    # 순환 import 를 피해 함수 안에서 부른다.
    from api.platform.ai_gateway import describe as describe_ai_gateway
    from api.platform.embeddings import describe as describe_embeddings

    try:
        payload["embeddings"] = describe_embeddings()
        payload["aiGateway"] = describe_ai_gateway()
    except Exception:
        # 진단 칸 하나 때문에 로그인 응답을 깨지 않는다.
        return body
    return json.dumps(payload, ensure_ascii=False).encode("utf-8")


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
        content = response.content
        if (request.url.path == "/api/auth/provider" and response.status_code == 200
                and "application/json" in (response.headers.get("content-type") or "")):
            content = _overlay_local_ai(content)
        return Response(content, status_code=response.status_code,
                        headers={name: response.headers[name] for name in ("content-type", "location")
                                 if name in response.headers})
