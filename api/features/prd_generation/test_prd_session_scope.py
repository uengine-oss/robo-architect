from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.features.prd_generation import prd_model_data
from api.features.prd_generation.prd_model_data import get_bcs_from_nodes
from api.features.prd_generation.routes import prd_export
from api.features.prd_generation.routes.prd_export import router as prd_export_router


def test_generate_route_passes_session_id(monkeypatch):
    app = FastAPI()
    app.include_router(prd_export_router, prefix="/api/prd")
    captured: dict[str, object] = {}

    def _fake_get_bcs_from_nodes(node_ids, session_id=None):
        captured["node_ids"] = node_ids
        captured["session_id"] = session_id
        return [{"id": "bc-1", "name": "Billing"}]

    monkeypatch.setattr(prd_export, "get_bcs_from_nodes", _fake_get_bcs_from_nodes)

    client = TestClient(app)
    response = client.post(
        "/api/prd/generate",
        json={
            "session_id": "sid-123",
            "tech_stack": {"project_name": "demo"},
        },
    )

    assert response.status_code == 200
    assert captured["node_ids"] is None
    assert captured["session_id"] == "sid-123"


def test_download_route_passes_session_id(monkeypatch):
    app = FastAPI()
    app.include_router(prd_export_router, prefix="/api/prd")
    captured: dict[str, object] = {}

    def _fake_get_bcs_from_nodes(node_ids, session_id=None):
        captured["node_ids"] = node_ids
        captured["session_id"] = session_id
        return [{"id": "bc-1", "name": "Billing", "aggregates": [], "readmodels": [], "policies": [], "uis": [], "gwts": []}]

    monkeypatch.setattr(prd_export, "get_bcs_from_nodes", _fake_get_bcs_from_nodes)
    monkeypatch.setattr(prd_export, "generate_main_prd", lambda bcs, config: "# PRD")
    monkeypatch.setattr(prd_export, "generate_cursor_rules", lambda config: "rules")
    monkeypatch.setattr(prd_export, "generate_readme", lambda bcs, config: "readme")
    monkeypatch.setattr(prd_export, "generate_bc_spec", lambda bc, config: f"# {bc.get('name')}")

    client = TestClient(app)
    response = client.post(
        "/api/prd/download",
        json={
            "session_id": "sid-dl",
            "tech_stack": {"project_name": "demo"},
        },
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/zip")
    assert captured["node_ids"] is None
    assert captured["session_id"] == "sid-dl"


def test_get_bcs_from_nodes_forwards_session_id_to_fetch(monkeypatch):
    class _DummyRecord:
        def __init__(self, ids):
            self._ids = ids

        def __getitem__(self, key):
            if key == "bc_ids":
                return self._ids
            raise KeyError(key)

    class _DummyResult:
        def __init__(self, ids):
            self._ids = ids

        def single(self):
            return _DummyRecord(self._ids)

    class _DummySession:
        def __init__(self):
            self.calls = []

        def run(self, query, **params):
            self.calls.append(params)
            return _DummyResult(["bc-a", "bc-b"])

    class _SessionCtx:
        def __init__(self, session):
            self._session = session

        def __enter__(self):
            return self._session

        def __exit__(self, exc_type, exc, tb):
            return False

    dummy_session = _DummySession()
    forwarded: list[tuple[str, str | None]] = []

    monkeypatch.setattr(
        "api.features.prd_generation.prd_model_data.get_session",
        lambda: _SessionCtx(dummy_session),
    )

    def _fake_fetch_bc_data(bc_id, session_id=None):
        forwarded.append((bc_id, session_id))
        return {"id": bc_id, "name": bc_id}

    monkeypatch.setattr(
        "api.features.prd_generation.prd_model_data.fetch_bc_data",
        _fake_fetch_bc_data,
    )

    bcs = get_bcs_from_nodes(None, session_id="sid-xyz")

    assert len(bcs) == 2
    assert forwarded == [("bc-a", "sid-xyz"), ("bc-b", "sid-xyz")]
    assert dummy_session.calls[0]["session_id"] == "sid-xyz"


def test_get_bcs_from_nodes_node_ids_branch_filters_by_session(monkeypatch):
    class _DummyRecord:
        def __init__(self, ids):
            self._ids = ids

        def __getitem__(self, key):
            if key == "bc_ids":
                return self._ids
            raise KeyError(key)

    class _DummyResult:
        def single(self):
            return _DummyRecord(["bc-node"])

    class _DummySession:
        def __init__(self):
            self.calls = []

        def run(self, query, **params):
            self.calls.append({"query": query, "params": params})
            return _DummyResult()

    class _SessionCtx:
        def __init__(self, session):
            self._session = session

        def __enter__(self):
            return self._session

        def __exit__(self, exc_type, exc, tb):
            return False

    dummy_session = _DummySession()
    monkeypatch.setattr(
        "api.features.prd_generation.prd_model_data.get_session",
        lambda: _SessionCtx(dummy_session),
    )
    monkeypatch.setattr(
        "api.features.prd_generation.prd_model_data.fetch_bc_data",
        lambda bc_id, session_id=None: {"id": bc_id},
    )

    bcs = get_bcs_from_nodes(["node-1"], session_id="sid-node")

    assert len(bcs) == 1
    first_call = dummy_session.calls[0]
    assert first_call["params"]["session_id"] == "sid-node"
    assert first_call["params"]["node_ids"] == ["node-1"]
    assert "coalesce(bc.session_id, '') = $session_id" in first_call["query"]


def test_fetch_bc_data_full_data_shape(monkeypatch):
    class _DummyRecord:
        def __init__(self, data):
            self._data = data

        def __getitem__(self, key):
            if key == "bc_data":
                return self._data
            raise KeyError(key)

    class _DummyResult:
        def __init__(self, data):
            self._data = data

        def single(self):
            return _DummyRecord(self._data)

    class _DummySession:
        def run(self, query, **params):
            assert params["bc_id"] == "bc-full"
            assert params["session_id"] == "sid-full"
            return _DummyResult(
                {
                    "id": "bc-full",
                    "name": "billing",
                    "displayName": "Billing",
                    "description": "desc",
                    "aggregates": [{"id": "agg-1", "commands": [], "events": []}],
                    "readmodels": [],
                    "policies": [],
                    "uis": [],
                    "gwts": [],
                    "userStories": [],
                    "questions": [],
                }
            )

    class _SessionCtx:
        def __init__(self, session):
            self._session = session

        def __enter__(self):
            return self._session

        def __exit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr(
        prd_model_data,
        "get_session",
        lambda: _SessionCtx(_DummySession()),
    )

    called: list[tuple[str, str | None]] = []

    def _fake_attach(bc_id, bc_data, session_id=None):
        called.append((bc_id, session_id))
        bc_data["aggregates"][0]["sourceRules"] = []

    monkeypatch.setattr(prd_model_data, "_attach_per_node_source_rules", _fake_attach)

    bc = prd_model_data.fetch_bc_data("bc-full", session_id="sid-full")

    assert bc is not None
    assert bc["id"] == "bc-full"
    assert called == [("bc-full", "sid-full")]
    assert "sourceRules" in bc["aggregates"][0]


def test_fetch_bc_data_graceful_for_partial_or_none(monkeypatch):
    class _DummyResultNone:
        def single(self):
            return None

    class _DummySession:
        def run(self, query, **params):
            return _DummyResultNone()

    class _SessionCtx:
        def __init__(self, session):
            self._session = session

        def __enter__(self):
            return self._session

        def __exit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr(
        prd_model_data,
        "get_session",
        lambda: _SessionCtx(_DummySession()),
    )

    # "none analyzer" / "no BC in scope" equivalent should return None, not raise.
    assert prd_model_data.fetch_bc_data("bc-none", session_id="sid-none") is None
