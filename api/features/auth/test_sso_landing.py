"""SWP 콜백이 JSON 을 날것으로 보여주지 않고 SPA 로 넘기는지 (2026-11-13 현장)."""

import json
import re

from api.features.auth.router import SSO_STASH_KEY, sso_landing


def _stash(resp) -> dict:
    body = resp.body.decode() if hasattr(resp, 'body') else resp.text
    m = re.search(r"sessionStorage\.setItem\((\"[^\"]+\"),(\".*?\")\)\}catch", body)
    assert m, body
    assert json.loads(m.group(1)) == SSO_STASH_KEY
    return json.loads(json.loads(m.group(2)))


def test_landing_is_html_and_goes_home():
    resp = sso_landing({"authenticated": True, "status": "approved", "accessToken": "t"})
    assert resp.media_type == "text/html"
    assert resp.headers["cache-control"] == "no-store"
    assert "location.replace('/')" in resp.body.decode()


def test_payload_round_trips_and_cannot_close_script():
    payload = {
        "authenticated": False,
        "status": "pending",
        "user": {"displayName": "</script><script>alert(1)</script>", "department": "설계팀 \"A\""},
    }
    resp = sso_landing(payload)
    body = resp.body.decode()
    assert body.count("</script>") == 1          # 우리가 닫는 하나뿐
    assert _stash(resp) == payload


# ── 중앙(authority)으로 넘기는 길 — posco-web 이 실제로 타는 길 ─────────────

def _proxied_app(monkeypatch, authority_reply):
    import httpx
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from api.features.accounts import authority_client as ac

    monkeypatch.setenv("ROBO_AUTHORITY_URL", "http://authority:59020")
    real = httpx.AsyncClient

    def fake_client(*a, **kw):
        kw["transport"] = httpx.MockTransport(authority_reply)
        return real(*a, **kw)

    monkeypatch.setattr(ac.httpx, "AsyncClient", fake_client)
    app = FastAPI()
    app.add_middleware(ac.AuthorityProxyMiddleware)
    return TestClient(app, follow_redirects=False)


def test_proxied_sso_json_becomes_landing(monkeypatch):
    import httpx
    payload = {"authenticated": True, "status": "approved", "accessToken": "t"}
    client = _proxied_app(monkeypatch, lambda req: httpx.Response(200, json=payload))
    r = client.post("/api/auth/sso/valid", data={"ssoToken": "x"})
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/html")
    assert _stash(r) == payload


def test_proxied_sso_redirect_passes_through(monkeypatch):
    import httpx
    client = _proxied_app(monkeypatch, lambda req: httpx.Response(302, headers={"location": "https://swp/login"}))
    r = client.get("/api/auth/sso/valid")
    assert r.status_code == 302 and r.headers["location"] == "https://swp/login"


def test_other_auth_paths_stay_json(monkeypatch):
    import httpx
    client = _proxied_app(monkeypatch, lambda req: httpx.Response(200, json={"authenticated": False}))
    r = client.get("/api/auth/me")
    assert r.headers["content-type"].startswith("application/json")
