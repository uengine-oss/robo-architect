"""중앙 API의 강제 인증과 PC의 폴백 금지."""
from __future__ import annotations

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.features.accounts import authority_client as client
from api.features.auth import tokens
from api.platform.identity.auth_guard import auth_enforced


@pytest.mark.parametrize("url", ["http://vm.example", "http://34.50.36.96",
                                 "https://user:secret@vm.example",
                                 "https://vm.example/path", "https://vm.example?token=secret"])
def test_authority_origin_validation(monkeypatch, url):
    monkeypatch.setenv("ROBO_AUTHORITY_URL", url)
    with pytest.raises(RuntimeError):
        client.authority_url()


@pytest.mark.parametrize("url", ["http://127.0.0.1:59020", "http://10.20.30.40:59020",
                                 "http://172.27.64.1:59020", "http://192.168.10.20:59020"])
def test_authority_allows_intranet_http(monkeypatch, url):
    monkeypatch.setenv("ROBO_AUTHORITY_URL", url)
    assert client.authority_url() == url


def test_pc_cannot_issue_or_verify_locally(monkeypatch):
    monkeypatch.setenv("ROBO_AUTHORITY_URL", "https://authority.example")
    monkeypatch.setenv("AUTH_ENFORCE", "0")
    assert auth_enforced()
    with pytest.raises(tokens.TokenError):
        tokens.issue_token({"uid": "a", "role": "admin", "status": "approved"})
    monkeypatch.setattr(client, "introspect", lambda token: (_ for _ in ()).throw(client.AuthorityUnavailable()))
    with pytest.raises(client.AuthorityUnavailable):
        tokens.verify_token("any-token")


def test_proxy_drops_pc_identity_headers(monkeypatch):
    monkeypatch.setenv("ROBO_AUTHORITY_URL", "https://authority.example")
    seen = []
    def handler(request):
        seen.append(request)
        return httpx.Response(403, json={"detail": "denied"})
    original = httpx.AsyncClient
    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: original(
        **kwargs, transport=httpx.MockTransport(handler)))
    app = FastAPI()
    app.add_middleware(client.AuthorityProxyMiddleware)
    with TestClient(app) as browser:
        result = browser.post("/api/accounts/b/role", json={"role": "admin"},
                              headers={"Authorization": "Bearer pc-token", "X-User-Roles": "admin",
                                       "X-Neo4j-Password": "do-not-forward", "X-Forwarded-For": "localhost"})
    assert result.status_code == 403
    assert seen[0].headers["authorization"] == "Bearer pc-token"
    for name in ("x-user-roles", "x-neo4j-password", "x-forwarded-for"):
        assert name not in seen[0].headers


def test_no_remote_template_write_fallback(monkeypatch):
    monkeypatch.setenv("ROBO_AUTHORITY_URL", "https://authority.example")
    def handler(request):
        raise httpx.ConnectError("offline")
    original = httpx.AsyncClient
    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: original(
        **kwargs, transport=httpx.MockTransport(handler)))
    app = FastAPI()
    app.add_middleware(client.AuthorityProxyMiddleware)
    @app.put("/api/code-templates/sets/a/file")
    def forbidden_local_write():
        pytest.fail("중앙 실패를 로컬 쓰기로 대체했다")
    with TestClient(app) as browser:
        assert browser.put("/api/code-templates/sets/a/file", json={"body": "x"}).status_code == 503
