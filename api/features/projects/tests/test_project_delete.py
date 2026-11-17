"""프로젝트 삭제 — 소유자만 · 이름 확인 · posco-web 에서는 중앙으로 안 넘긴다(2026-11-16)."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.features.accounts.authority_client import delegated_path, handled_locally
from api.features.projects import router as projects_router
from api.features.projects import store


def test_only_project_delete_is_handled_locally():
    assert handled_locally("DELETE", "/api/projects/prj_abc")
    assert not handled_locally("DELETE", "/api/projects/prj_abc/members/123")   # 공유 회수는 중앙으로
    assert not handled_locally("GET", "/api/projects/prj_abc")
    assert not handled_locally("DELETE", "/api/projects")
    assert not handled_locally("DELETE", "/api/projects/")
    assert delegated_path("/api/projects/prj_abc")   # 나머지는 여전히 중앙의 몫


@pytest.fixture
def client(monkeypatch):
    dropped: list[str] = []
    projects = {"prj_mine": {"graph": "prj_mine", "displayName": "주문 설계", "ownerUid": "100"},
                "prj_other": {"graph": "prj_other", "displayName": "남의 것", "ownerUid": "200"}}
    monkeypatch.setattr(store, "get_project", lambda g: projects.get(g))
    monkeypatch.setattr(store, "drop_project", lambda g: dropped.append(g))
    monkeypatch.setattr(projects_router, "_uid", lambda request: "100")
    app = FastAPI()
    app.include_router(projects_router.router)
    c = TestClient(app)
    c.dropped = dropped
    return c


def test_owner_with_matching_name_deletes(client):
    r = client.delete("/api/projects/prj_mine", params={"confirm": "주문 설계"})
    assert r.status_code == 200 and r.json() == {"deleted": "prj_mine", "name": "주문 설계"}
    assert client.dropped == ["prj_mine"]


def test_wrong_confirm_name_is_refused(client):
    r = client.delete("/api/projects/prj_mine", params={"confirm": "주문"})
    assert r.status_code == 400
    assert client.dropped == []


def test_not_owner_is_refused(client):
    r = client.delete("/api/projects/prj_other", params={"confirm": "남의 것"})
    assert r.status_code == 403
    assert client.dropped == []


def test_unknown_project_is_404(client):
    assert client.delete("/api/projects/prj_none", params={"confirm": "x"}).status_code == 404
