"""SWP 콜백이 토큰 없이 · 검증 실패로 오면 EP 메인이 아니라 우리 화면으로 (2026-11-23 포스코 현장).

전에는 `SWP_SSO_LOGIN_URL`(swp.posco.net = EP 메인)로 보냈다 — "로그인은 되는데 EP 메인이 뜬다".
화면은 `?sso=` 를 보고 한 번 더 SSO 를 거쳐 온다(auth.store.js `shouldAutoSso`).
"""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.features.auth import router as auth_router


@pytest.fixture()
def client(monkeypatch):
    monkeypatch.setenv("AUTH_PROVIDER", "swp")
    monkeypatch.setenv("SWP_SSO_REDIRECT_URL", "http://swp.example/redirect.jsp?redir_url=")
    monkeypatch.setenv("SWP_SSO_VALID_CHECK_URL", "http://swp.example/isValidSSO.jsp")
    monkeypatch.setenv("SWP_SSO_LOGIN_URL", "http://swp.example")
    app = FastAPI()
    app.include_router(auth_router.router)
    return TestClient(app, follow_redirects=False)


def test_missing_token_comes_back_to_robo_not_ep_main(client):
    for r in (client.get(f"/api/auth/sso/valid"),
              client.post(f"/api/auth/sso/valid", data={"other": "x"})):
        assert r.status_code == 302
        assert r.headers["location"] == "/?sso=missing"


def test_invalid_token_comes_back_to_robo(client, monkeypatch):
    async def fake_validate(settings, token):
        return None, "Unauthenticated"
    monkeypatch.setattr(auth_router, "validate_sso_token", fake_validate)
    r = client.post(f"/api/auth/sso/valid", data={"ssoToken": "dead"})
    assert r.status_code == 302
    assert r.headers["location"] == "/?sso=invalid"


def test_missing_token_logs_names_not_values(client, monkeypatch):
    seen = []
    monkeypatch.setattr(auth_router.SmartLogger, "log", lambda *a, **kw: seen.append(kw.get("params", {})))
    client.cookies.set("SWP-H-SESSION-ID", "secret-cookie")
    client.post(f"/api/auth/sso/valid?x=1", data={"ssotoken": "secret-value"})
    shape = next(p for p in seen if "form_keys" in p)
    assert shape["method"] == "POST"
    assert shape["form_keys"] == ["ssotoken"] and shape["query_keys"] == ["x"]
    assert "SWP-H-SESSION-ID" in shape["cookie_names"]
    assert "secret" not in repr(shape)
