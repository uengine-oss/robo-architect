"""알림을 울릴지 말지 — 목에서 거르는 규칙.

여기서 재는 것은 **울리면 안 되는데 울리는 경우**다. 셋 다 조용히 나쁘다.

    실패한 쓰기에 울린다     아무것도 안 바뀌었는데 모두가 다시 읽는다
    스트림 자신에 울린다     자기 심장박동에 반응해 끝없이 울린다
    엉뚱한 graph 에 울린다   바뀐 프로젝트와 울린 프로젝트가 다르다
"""

from __future__ import annotations

import pytest

from api.features.collab import notify
from api.platform.neo4j_context import Neo4jOverride


class _Headers(dict):
    def get(self, k, d=None):  # 대소문자 무시 — Starlette 헤더와 같게
        return super().get(k.lower(), d)


def _bound(database):
    return Neo4jOverride(uri="bolt://x", user="u", password="p", database=database)


@pytest.mark.parametrize("method", ["POST", "PUT", "PATCH", "DELETE"])
def test_성공한_쓰기에_울린다(method):
    assert notify.should_notify(method, "/api/graph/event-modeling/nodes", 200)


@pytest.mark.parametrize("method", ["GET", "HEAD", "OPTIONS"])
def test_읽기에는_안_울린다(method):
    assert not notify.should_notify(method, "/api/graph/anything", 200)


@pytest.mark.parametrize("status", [400, 401, 403, 404, 409, 500])
def test_실패한_쓰기에는_안_울린다(status):
    """아무것도 안 바꿨다. 울리면 모두가 헛되이 다시 읽는다."""
    assert not notify.should_notify("POST", "/api/graph/x", status)


@pytest.mark.parametrize(
    "path",
    ["/api/collab/leave", "/api/collab/stream", "/api/auth/dev-login",
     "/api/accounts/approve", "/api/health"],
)
def test_graph_를_안_건드리는_경로에는_안_울린다(path):
    """특히 `/api/collab/` — 스트림이 자기 심장박동에 반응하면 끝없이 울린다."""
    assert not notify.should_notify("POST", path, 200)


def test_프로젝트_경로는_울린다():
    """공유·회수는 graph 를 안 건드리지만 **목록과 권한이 바뀐다.** 여기까지
    막으면 회수당한 사람 화면이 안 바뀐다."""
    assert notify.should_notify("POST", "/api/projects/prj_a/members", 200)


def test_세션이_정한_graph_가_헤더보다_세다():
    """바인딩이 켜져 있으면 클라이언트가 보낸 값은 이미 무시됐다. 알림만 헤더를
    따라가면 **바뀐 프로젝트와 울린 프로젝트가 달라진다.**"""
    headers = _Headers({"x-project-graph": "prj_남의것"})
    assert notify.graph_of(headers, _bound("prj_진짜")) == "prj_진짜"


def test_세션이_없으면_헤더를_본다():
    headers = _Headers({"x-project-graph": "prj_aaa"})
    assert notify.graph_of(headers, None) == "prj_aaa"


def test_옛_헤더_이름도_인정한다():
    headers = _Headers({"x-neo4j-database": "prj_bbb"})
    assert notify.graph_of(headers, None) == "prj_bbb"


def test_고른_프로젝트가_없으면_아무것도_안_한다():
    assert notify.graph_of(_Headers({}), None) is None
    # 울릴 대상이 없을 때 던지면 그 요청 전체가 깨진다.
    notify.after_request(_Headers({}), None, "POST", "/api/graph/x", 200)


def test_알림이_깨져도_요청은_안_깨진다(monkeypatch):
    """이 함수는 응답이 정해진 뒤에 불린다. 여기서 던지면 성공한 쓰기가
    500 으로 뒤집힌다."""
    from api.features.collab import store

    def boom(*a, **k):
        raise RuntimeError("표가 없다")

    monkeypatch.setattr(store, "bump", boom)
    notify.after_request(
        _Headers({"x-project-graph": "prj_aaa"}), None, "POST", "/api/graph/x", 200,
    )
