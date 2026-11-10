"""`/api/gateway/**` 프록시 — 자격 헤더를 버리고, 남의 graph 를 막고, 분석 본문을 좁힌다."""
from __future__ import annotations

import json
import types

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.features.gateway_proxy import router as mod

MINE = [
    {"graph": "p_mine", "analyzerGraph": "p_mine_a", "level": "write"},
    {"graph": "p_read", "analyzerGraph": "p_read_a", "level": "read"},
]


class _Stream(httpx.AsyncByteStream):
    """실제 전송처럼 **아직 안 읽힌** 응답 — `aiter_raw` 가 흘려 읽을 수 있다."""

    def __init__(self, data: bytes):
        self._data = data

    async def __aiter__(self):
        yield self._data


@pytest.fixture
def seen():
    return []


@pytest.fixture
def client(monkeypatch, seen):
    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, stream=_Stream(b"data: ok\n\n"),
                              headers={"content-type": "text/event-stream"})

    transport = httpx.MockTransport(handler)
    fake = types.SimpleNamespace(
        AsyncClient=lambda **kw: httpx.AsyncClient(transport=transport, **kw),
        Timeout=httpx.Timeout,
        HTTPError=httpx.HTTPError,
    )
    monkeypatch.setattr(mod, "httpx", fake)
    monkeypatch.setattr(mod, "request_uid", lambda request: "u1")
    monkeypatch.setattr(mod.projects, "list_projects", lambda uid: MINE)
    monkeypatch.setenv("ROBO_GATEWAY_URL", "http://gateway:9000")
    monkeypatch.setenv("ROBO_GRAPH_MODE", "central")
    app = FastAPI()
    app.include_router(mod.router)
    return TestClient(app)


def test_forwards_path_and_drops_browser_credentials(client, seen):
    r = client.get("/api/gateway/robo/graph?x=1", headers={
        "X-Neo4j-Database": "p_mine_a",
        "X-Neo4j-User": "robo", "X-Neo4j-Password": "nope", "X-Neo4j-URI": "bolt://evil:7687",
        "Authorization": "Bearer t",
    })
    assert r.status_code == 200
    assert r.headers["x-accel-buffering"] == "no"
    up = seen[0]
    assert str(up.url) == "http://gateway:9000/api/gateway/robo/graph?x=1"
    assert up.headers["x-neo4j-database"] == "p_mine_a"
    assert up.headers["authorization"] == "Bearer t"
    for name in ("x-neo4j-user", "x-neo4j-password", "x-neo4j-uri"):
        assert name not in up.headers


def test_rejects_graph_of_other_project(client, seen):
    r = client.get("/api/gateway/robo/graph", headers={"X-Neo4j-Database": "p_theirs_a"})
    assert r.status_code == 403
    assert seen == []


def test_read_level_cannot_write(client, seen):
    r = client.post("/api/gateway/robo/analyze", json={"strategy": "dbms"},
                    headers={"X-Neo4j-Database": "p_read_a"})
    assert r.status_code == 403
    assert client.get("/api/gateway/robo/graph",
                      headers={"X-Neo4j-Database": "p_read_a"}).status_code == 200


def test_central_mode_requires_identity_for_graph(client, monkeypatch, seen):
    monkeypatch.setattr(mod, "request_uid", lambda request: "")
    r = client.get("/api/gateway/robo/graph", headers={"X-Neo4j-Database": "p_mine_a"})
    assert r.status_code == 403


def test_analyze_body_is_narrowed(client, seen):
    r = client.post("/api/gateway/robo/analyze", headers={"X-Neo4j-Database": "p_mine_a"}, json={
        "strategy": "framework", "target": "java", "nameCase": "camel",
        "inferFkRelations": True, "targetFolder": "src", "project_root": "/tmp/x",
        "datasourceName": "erp",
    })
    assert r.status_code == 200
    body = json.loads(seen[0].content)
    assert body == {"strategy": "framework", "locale": "ko",
                    "selected_source_ids": [], "datasource": "erp"}


def test_unreachable_gateway_is_502(monkeypatch, client):
    def boom(request):
        raise httpx.ConnectError("refused")

    transport = httpx.MockTransport(boom)
    monkeypatch.setattr(mod, "httpx", types.SimpleNamespace(
        AsyncClient=lambda **kw: httpx.AsyncClient(transport=transport, **kw),
        Timeout=httpx.Timeout, HTTPError=httpx.HTTPError))
    assert client.get("/api/gateway/robo/graph").status_code == 502
