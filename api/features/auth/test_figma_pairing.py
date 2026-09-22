"""Figma pairing codes must be one-use and tokens must stay project-scoped."""

from __future__ import annotations

from api.features.auth.figma_pairing import create_code, exchange_code
from api.features.auth.tokens import verify_token


def test_pairing_code_is_single_use_and_project_scoped(monkeypatch):
    monkeypatch.setenv("AUTH_JWT_SECRET", "figma-pairing-test-secret-with-at-least-32-bytes")
    code, ttl = create_code({"sub": "user-1", "approved": True}, "prj_a")
    assert ttl == 300
    result = exchange_code(code)
    assert result is not None
    token, graph = result
    assert graph == "prj_a"
    claims = verify_token(token)
    assert claims["sub"] == "user-1"
    assert claims["project"] == "prj_a"
    assert claims["scope"] == "figma-plugin"
    assert exchange_code(code) is None
