"""Tests for 034 — Epic(BC)/Feature create & edit endpoints.

These exercise the validation + persistence wiring of the deterministic
(non-LLM) backend slice: POST/PATCH /bounded-context and PATCH /feature.
The Neo4j client is stubbed so the tests run without a live database.
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.features.requirements.router import router


class _StubClient:
    """In-memory stand-in for the Neo4j client used by the routes."""

    def __init__(self) -> None:
        self.bcs: dict[str, dict] = {
            "bc-1": {
                "id": "bc-1",
                "key": "orders",
                "name": "Orders",
                "displayName": "Orders",
                "description": None,
            }
        }
        self.features: dict[str, dict] = {
            "f-1": {
                "id": "f-1",
                "key": "orders::checkout",
                "name": "Checkout",
                "description": None,
                "source": "manual",
                "boundedContextId": "bc-1",
            }
        }

    def create_bounded_context(self, *, name, display_name=None, description=None, **_):
        bc = {
            "id": "bc-new",
            "key": name.lower().replace(" ", "-"),
            "name": name,
            "displayName": display_name or name,
            "description": description,
        }
        self.bcs[bc["id"]] = bc
        return bc

    def update_bounded_context(self, bc_id, *, name=None, display_name=None, description=None):
        bc = self.bcs.get(bc_id)
        if not bc:
            return None
        if name is not None:
            bc["name"] = name
        if display_name is not None:
            bc["displayName"] = display_name
        if description is not None:
            bc["description"] = description
        return bc

    def update_feature(self, feature_id, *, name=None, description=None):
        f = self.features.get(feature_id)
        if not f:
            return None
        if name is not None:
            f["name"] = name
        if description is not None:
            f["description"] = description
        return f


@pytest.fixture
def client(monkeypatch):
    stub = _StubClient()
    monkeypatch.setattr(
        "api.features.requirements.routes.bounded_context_crud.get_neo4j_client",
        lambda: stub,
    )
    monkeypatch.setattr(
        "api.features.requirements.routes.feature_crud.get_neo4j_client",
        lambda: stub,
    )
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def test_create_epic(client):
    res = client.post("/api/requirements/bounded-context", json={"name": "Payments"})
    assert res.status_code == 201
    assert res.json()["boundedContext"]["name"] == "Payments"


def test_create_epic_blank_name_rejected(client):
    res = client.post("/api/requirements/bounded-context", json={"name": "   "})
    assert res.status_code == 422


def test_update_epic(client):
    res = client.patch(
        "/api/requirements/bounded-context",
        json={"boundedContextId": "bc-1", "name": "Order Mgmt"},
    )
    assert res.status_code == 200
    assert res.json()["boundedContext"]["name"] == "Order Mgmt"


def test_update_epic_not_found(client):
    res = client.patch(
        "/api/requirements/bounded-context",
        json={"boundedContextId": "nope", "name": "X"},
    )
    assert res.status_code == 404


def test_update_feature(client):
    res = client.patch(
        "/api/requirements/feature",
        json={"featureId": "f-1", "name": "One-click Checkout"},
    )
    assert res.status_code == 200
    assert res.json()["feature"]["name"] == "One-click Checkout"


def test_update_feature_blank_name_rejected(client):
    res = client.patch(
        "/api/requirements/feature",
        json={"featureId": "f-1", "name": ""},
    )
    assert res.status_code == 422


def test_update_feature_not_found(client):
    res = client.patch(
        "/api/requirements/feature",
        json={"featureId": "nope", "name": "X"},
    )
    assert res.status_code == 404
