# -*- coding: utf-8 -*-
"""서비스 ID — **이제 받지 않는다. 이미 붙은 값만 지킨다.**

2026-11-17 — 프로젝트 만들기와 적재 입구 셋(표준 업로드 · Figma · 하이브리드)의
**서비스 ID 입력을 모두 뺐다**(사용자 지시). 모양 규칙(`service_id.py`)과 적재
게이트(`ingestion/service_id_gate.py`)도 함께 지웠다.

예전에 붙은 프로젝트의 `serviceId` 는 `value` 에 남아 있고 목록에 보인다.
그 값이 조용히 사라지지 않는지, 입력이 몰래 되살아나지 않는지만 본다.
"""

from __future__ import annotations

import json

import pytest

from api.features.projects import store


# ── 저장: 값이 실제로 실리나 ────────────────────────────────────────────────

class _Cur:
    """`cur.execute` 를 받아 적는다. 무엇이 어떤 값으로 들어갔는지만 본다."""

    def __init__(self, sink: list):
        self.sink = sink

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def execute(self, sql, params=None):
        self.sink.append((sql, params))


class _Conn:
    def __init__(self, sink: list):
        self.sink = sink

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def cursor(self):
        return _Cur(self.sink)


@pytest.fixture
def 기록(monkeypatch: pytest.MonkeyPatch) -> list:
    sink: list = []
    monkeypatch.setattr(store.roles, "ensure_role", lambda uid: f"role_{uid}")
    monkeypatch.setattr(store, "graph_exists", lambda g: False)
    monkeypatch.setattr(store.pg, "connection", lambda: _Conn(sink))
    return sink


def _inserted_value(sink: list) -> dict:
    for sql, params in sink:
        if "INSERT INTO public.app_projects" in sql:
            return json.loads(params[1])
    raise AssertionError("app_projects INSERT 가 없다")


def test_만들기는_서비스_ID_를_받지_않는다():
    """입력을 뺐다(2026-11-17). 인자가 다시 생기면 이 검사가 알린다."""
    import inspect
    assert "service_id" not in inspect.signature(store.create_project).parameters


def test_안_주면_칸_자체가_없다(기록):
    """`None` 을 넣어 두면 부분 유일 인덱스가 그 행들을 서로 부딪치게 본다.

    키를 아예 안 쓰는 것이 "값이 없다" 의 올바른 표현이다.
    """
    store.create_project("인사관리", "u1")
    assert "serviceId" not in _inserted_value(기록)


class _Dup(Exception):
    sqlstate = "23505"


def test_만들다_난_오류는_그대로_올린다(monkeypatch: pytest.MonkeyPatch):
    """유일 위반이라도 "서비스 ID 가 겹쳤다" 로 바꿔 말하지 않는다 — 이제 받지 않는 값이다."""
    monkeypatch.setattr(store.roles, "ensure_role", lambda uid: "role_u1")
    monkeypatch.setattr(store, "graph_exists", lambda g: False)

    def _boom():
        raise _Dup("graph 이름이 겹쳤다")

    monkeypatch.setattr(store.pg, "connection", _boom)
    with pytest.raises(_Dup):
        store.create_project("인사관리", "u1")


# ── ③ 불변 ────────────────────────────────────────────────────────────────

def test_서비스_ID_를_바꾸는_함수가_없다():
    """사용자 지시는 "일단 나중에는 변경할 수 없도록" 이다.

    강제 수단이 "그런 함수가 없다" 인 이상, 누가 편의로 하나 추가하는 순간
    지시가 조용히 풀린다. 이 검사가 그 문을 잠근다.
    """
    허용: set[str] = set()
    설정하는_것 = [n for n in store.__all__
                 if "service" in n.lower() and n not in 허용]
    assert 설정하는_것 == []


def test_분석_graph_를_바꿔도_서비스_ID_가_살아남는다(monkeypatch: pytest.MonkeyPatch):
    """`set_analyzer_graph` 는 `value` 를 **통째로 다시 쓴다.**

    남겨야 할 키를 빠뜨리면 서비스 ID 가 조용히 사라진다 — 오류는 안 난다.
    """
    쓴_값: dict = {}
    monkeypatch.setattr(store, "get_project", lambda g: {
        "graph": g, "displayName": "인사관리", "ownerUid": "u1",
        "serviceId": "ROBO-1", "level": "admin",
    })
    monkeypatch.setattr(store, "graph_exists", lambda g: True)
    monkeypatch.setattr(store, "_warn_if_shared", lambda *a: None)
    monkeypatch.setattr(store.pg, "execute",
                        lambda sql, params: 쓴_값.update(json.loads(params[0])))

    out = store.set_analyzer_graph("prj_a", "prj_a_a")
    assert 쓴_값["serviceId"] == "ROBO-1"
    assert out["serviceId"] == "ROBO-1"
