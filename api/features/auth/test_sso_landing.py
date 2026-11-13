"""SWP 콜백이 JSON 을 날것으로 보여주지 않고 SPA 로 넘기는지 (2026-11-13 현장)."""

import json
import re

from api.features.auth.router import SSO_STASH_KEY, sso_landing


def _stash(resp) -> dict:
    body = resp.body.decode()
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
