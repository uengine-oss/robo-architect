# -*- coding: utf-8 -*-
"""서비스 ID — **사람이 정하고, 겹치면 막고, 만든 뒤엔 못 바꾼다**.

## 왜 이 검사가 있나

이 값은 기업이 자기 서비스를 식별하는 체계의 값이다. 우리 쪽 식별자와 달리
**틀려도 오류가 안 난다** — 겹친 ID 로 두 프로젝트가 돌아가도, 모양이 어긋난 값이
로그와 내보낸 문서에 섞여 나가도, 화면은 멀쩡하다. 그래서 재는 것은 넷이다.

```
① 모양   한 군데(`service_id.py`)서만 정한다. 두 입구가 이 하나를 본다
② 유일   **DB 인덱스**가 지킨다 — SELECT 검사는 동시 생성을 통과시킨다
③ 불변   바꾸는 함수가 없다. 그것이 강제다
④ 선택   안 줘도 된다 — 체계를 못 받은 사람이 일을 못 하면 안 된다
```
"""

from __future__ import annotations

import json

import pytest

from api.features.projects import service_id as service_ids
from api.features.projects import store


# ── ① 모양 ────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("value", [
    "ROBO-2026-001",      # 하이픈 — graph 이름에는 못 쓰는 모양이다
    "HR_LEAVE_01",
    "erp.billing.v2",
    "AB",                 # 가장 짧은 것
    "a" * 64,             # 가장 긴 것
])
def test_기업_체계가_쓸_만한_모양은_받는다(value: str):
    assert service_ids.validate(value) == value


@pytest.mark.parametrize("value", [
    "ROBO 2026",          # 공백 — 로그와 URL 에서 쪼개진다
    "연차관리",            # 한글 — 내보낸 파일 이름에서 깨진다
    "-ROBO-1",            # 기호로 시작
    "ROBO-1-",            # 기호로 끝
    "A",                  # 한 자 — 사람이 식별자로 못 쓴다
    "a" * 65,             # 너무 길다
    "ROBO/2026",          # 경로 구분자
])
def test_나중에_말썽이_되는_모양은_막는다(value: str):
    with pytest.raises(ValueError):
        service_ids.validate(value)


# ── ④ 선택 ────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("value", [None, "", "   "])
def test_안_준_것과_빈_칸을_같게_본다(value):
    """화면의 빈 칸은 `""` 로 오고 API 직접 호출은 아예 안 온다.

    둘을 다르게 보면 "비웠는데 모양 오류가 난다" 가 된다.
    """
    assert service_ids.validate(value) is None
    assert service_ids.normalize(value) is None


def test_앞뒤_공백은_떼고_받는다():
    assert service_ids.validate("  ROBO-1  ") == "ROBO-1"


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
    monkeypatch.setattr(store, "service_id_guard_ready", lambda: True)
    monkeypatch.setattr(store.pg, "connection", lambda: _Conn(sink))
    return sink


def _inserted_value(sink: list) -> dict:
    for sql, params in sink:
        if "INSERT INTO public.app_projects" in sql:
            return json.loads(params[1])
    raise AssertionError("app_projects INSERT 가 없다")


def test_준_서비스_ID_가_프로젝트에_실린다(기록):
    store.create_project("인사관리", "u1", service_id="ROBO-2026-001")
    assert _inserted_value(기록)["serviceId"] == "ROBO-2026-001"


def test_안_주면_칸_자체가_없다(기록):
    """`None` 을 넣어 두면 부분 유일 인덱스가 그 행들을 서로 부딪치게 본다.

    키를 아예 안 쓰는 것이 "값이 없다" 의 올바른 표현이다.
    """
    store.create_project("인사관리", "u1")
    assert "serviceId" not in _inserted_value(기록)


def test_모양이_틀리면_graph_를_만들기_전에_멈춘다(기록):
    """검사가 INSERT 뒤에 있으면 graph 와 권한이 먼저 생긴다 — 되돌릴 일이 남는다."""
    with pytest.raises(ValueError):
        store.create_project("인사관리", "u1", service_id="ROBO 2026")
    assert 기록 == []


# ── ② 유일 ────────────────────────────────────────────────────────────────

class _Dup(Exception):
    sqlstate = "23505"


def test_유일_인덱스가_없는_DB_는_서비스_ID_를_받지_않는다(monkeypatch: pytest.MonkeyPatch):
    """⚠ 이 검사가 이 파일에서 가장 중요하다.

    중앙 구성에서 `/api/projects` 는 **authority 서버**가 서비스하고, 거기서는
    `ensure_schema()` 가 DDL 을 돌리지 않는다. 운영 명령 `migrate` 를 다시 돌리지
    않은 DB 에서는 인덱스가 없고 — 그러면 `serviceId` 가 **그냥 들어간다.**
    INSERT 는 성공하고 겹쳐도 아무 일이 없다. 유일성이 조용히 사라진다.
    """
    monkeypatch.setattr(store, "_service_id_guard_seen", False)
    monkeypatch.setattr(store.pg, "query", lambda sql, params=None: [])

    with pytest.raises(ValueError) as caught:
        store.create_project("인사관리", "u1", service_id="ROBO-1")
    assert "migrate" in str(caught.value)


def test_지킴이가_없어도_ID_없는_프로젝트는_만들_수_있다(monkeypatch: pytest.MonkeyPatch):
    """막는 것은 **ID 를 받는 일**뿐이다. 제품 전체를 세우면 안 된다."""
    sink: list = []
    monkeypatch.setattr(store, "_service_id_guard_seen", False)
    monkeypatch.setattr(store.pg, "query", lambda sql, params=None: [])
    monkeypatch.setattr(store.roles, "ensure_role", lambda uid: "role_u1")
    monkeypatch.setattr(store, "graph_exists", lambda g: False)
    monkeypatch.setattr(store.pg, "connection", lambda: _Conn(sink))

    store.create_project("인사관리", "u1")
    assert "serviceId" not in _inserted_value(sink)


def test_지킴이를_한_번_보면_다시_묻지_않는다(monkeypatch: pytest.MonkeyPatch):
    """프로젝트를 만들 때마다 `pg_class` 를 뒤지지 않는다. 인덱스는 사라지지 않는다."""
    물어본_횟수 = {"n": 0}

    def _query(sql, params=None):
        물어본_횟수["n"] += 1
        return [{"?column?": 1}]

    monkeypatch.setattr(store, "_service_id_guard_seen", False)
    monkeypatch.setattr(store.pg, "query", _query)
    assert store.service_id_guard_ready() is True
    assert store.service_id_guard_ready() is True
    assert 물어본_횟수["n"] == 1


def test_지킴이가_없다는_답은_기억하지_않는다(monkeypatch: pytest.MonkeyPatch):
    """관리자가 `migrate` 를 돌린 뒤 **앱을 다시 띄우지 않아도** 되게 한다."""
    답 = {"있다": False}
    monkeypatch.setattr(store, "_service_id_guard_seen", False)
    monkeypatch.setattr(store.pg, "query",
                        lambda sql, params=None: [{"x": 1}] if 답["있다"] else [])
    assert store.service_id_guard_ready() is False
    답["있다"] = True
    assert store.service_id_guard_ready() is True


def test_겹친_서비스_ID_는_사람이_읽는_말로_돌려준다(monkeypatch: pytest.MonkeyPatch):
    """유일 인덱스에 걸린 것은 사용자가 고칠 수 있는 일이다 — 503 이 아니라 400 이어야 한다."""
    monkeypatch.setattr(store.roles, "ensure_role", lambda uid: "role_u1")
    monkeypatch.setattr(store, "graph_exists", lambda g: False)
    monkeypatch.setattr(store, "service_id_guard_ready", lambda: True)

    def _boom():
        raise _Dup("duplicate key value violates unique constraint")

    monkeypatch.setattr(store.pg, "connection", _boom)
    with pytest.raises(ValueError) as caught:
        store.create_project("인사관리", "u1", service_id="ROBO-1")
    assert "ROBO-1" in str(caught.value)


def test_서비스_ID_없이_난_오류는_그대로_올린다(monkeypatch: pytest.MonkeyPatch):
    """ID 와 무관한 고장을 "겹쳤다" 로 바꿔 말하면 원인을 못 찾는다."""
    monkeypatch.setattr(store.roles, "ensure_role", lambda uid: "role_u1")
    monkeypatch.setattr(store, "graph_exists", lambda g: False)
    monkeypatch.setattr(store, "service_id_guard_ready", lambda: True)

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
    허용 = {"create_project", "service_id_guard_ready"}
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
