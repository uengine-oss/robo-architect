"""Tests for IdentityMiddleware (spec 032 T011).

Builds a tiny FastAPI app with only IdentityMiddleware mounted, then
asserts the right `Actor` lands on `request.state.actor` across all the
documented header conditions.
"""

from __future__ import annotations

import socket

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from starlette.requests import Request
from starlette.testclient import TestClient

from api.platform.identity.middleware import IdentityMiddleware
from api.platform.identity.models import Actor


def _build_app() -> FastAPI:
    app = FastAPI()
    app.add_middleware(IdentityMiddleware)

    @app.get("/whoami")
    def whoami(request: Request) -> JSONResponse:
        actor: Actor = request.state.actor
        return JSONResponse(
            {"name": actor.name, "email": actor.email, "source": actor.source}
        )

    return app


def test_headers_present_populates_actor():
    app = _build_app()
    with TestClient(app) as client:
        r = client.get(
            "/whoami",
            headers={"X-User-Name": "Jane%20Doe", "X-User-Email": "jane@example.com"},
        )
    assert r.status_code == 200
    body = r.json()
    assert body["name"] == "Jane Doe"
    assert body["email"] == "jane@example.com"
    assert body["source"] == "env"


def test_headers_missing_fall_back_to_unknown():
    app = _build_app()
    with TestClient(app) as client:
        r = client.get("/whoami")
    assert r.status_code == 200
    body = r.json()
    assert body["name"] == "unknown user"
    assert body["email"] == f"unknown@{socket.gethostname()}"
    assert body["source"] == "unknown-header-missing"


def test_empty_headers_treated_as_missing():
    app = _build_app()
    with TestClient(app) as client:
        r = client.get(
            "/whoami",
            headers={"X-User-Name": "", "X-User-Email": ""},
        )
    body = r.json()
    assert body["source"] == "unknown-header-missing"


def test_whitespace_only_headers_treated_as_missing():
    app = _build_app()
    with TestClient(app) as client:
        r = client.get(
            "/whoami",
            headers={"X-User-Name": "   ", "X-User-Email": "  \t  "},
        )
    body = r.json()
    assert body["source"] == "unknown-header-missing"


def test_one_header_missing_falls_back():
    # Per the contract, BOTH headers must be present. Missing email alone
    # should fall back rather than partially populate.
    app = _build_app()
    with TestClient(app) as client:
        r = client.get("/whoami", headers={"X-User-Name": "Jane"})
    assert r.json()["source"] == "unknown-header-missing"


def test_percent_encoded_unicode_name_round_trips():
    app = _build_app()
    # 장진영 → percent-encoded UTF-8
    with TestClient(app) as client:
        r = client.get(
            "/whoami",
            headers={
                "X-User-Name": "%EC%9E%A5%EC%A7%84%EC%98%81",
                "X-User-Email": "jyjang@uengine.org",
            },
        )
    body = r.json()
    assert body["name"] == "장진영"
    assert body["source"] == "env"


def test_actor_never_raises_on_malformed_percent_encoding():
    # Malformed % sequence should not 500; we degrade to raw header bytes.
    app = _build_app()
    with TestClient(app) as client:
        r = client.get(
            "/whoami",
            headers={
                "X-User-Name": "Jane%ZZ",  # invalid percent escape
                "X-User-Email": "jane@example.com",
            },
        )
    assert r.status_code == 200
    body = r.json()
    # `urllib.parse.unquote` actually tolerates malformed sequences by
    # leaving them as-is — confirm we still got "env" source and didn't 500.
    assert body["source"] == "env"
    assert "jane@example.com" == body["email"]
