"""설계 화면의 서비스 이름을 프로젝트에 저장한다 (2026-11-24)."""

import json

import pytest

from api.features.projects import store


@pytest.fixture()
def saved(monkeypatch):
    calls = []
    monkeypatch.setattr(store, "get_project", lambda g: {"graph": g, "displayName": "test1123", "ownerUid": "u", "level": "admin"})
    monkeypatch.setattr(store.pg, "execute", lambda sql, params: calls.append((sql, params)))
    return calls


def test_sets_name_in_project_value(saved):
    out = store.set_service_name("prj_x", "  자동납부   서비스 ")
    assert out["serviceName"] == "자동납부 서비스"
    value = json.loads(saved[0][1][0])
    assert value["serviceName"] == "자동납부 서비스" and value["displayName"] == "test1123"
    assert "graph" not in value and "level" not in value


def test_blank_removes_it(saved, monkeypatch):
    monkeypatch.setattr(store, "get_project", lambda g: {"graph": g, "displayName": "p", "serviceName": "old"})
    out = store.set_service_name("prj_x", "   ")
    assert "serviceName" not in out and "serviceName" not in json.loads(saved[0][1][0])


def test_too_long_is_refused(saved):
    with pytest.raises(ValueError):
        store.set_service_name("prj_x", "가" * (store.SERVICE_NAME_MAX + 1))
