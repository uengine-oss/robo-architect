"""요구사항이 하나도 없는 프로젝트에서 명확화 레이더가 500 이 되지 않는다.

overall_clarity 는 대상 없음/스캔 안 함을 None 으로 돌려준다(⑯). 그런데 라우트가 로그에
남기면서 round(None) 을 불러 요구사항 화면을 열 때마다 500 이 났다(2026-11-18 golden-1117).
"""
from __future__ import annotations

import asyncio

from starlette.requests import Request

from api.features.requirements.clarification_contracts import ScopeType
from api.features.requirements.routes import clarification as route


def _request() -> Request:
    return Request({"type": "http", "method": "GET", "path": "/", "headers": [], "query_string": b""})


def test_empty_project_scope_returns_no_score_instead_of_500(monkeypatch) -> None:
    monkeypatch.setattr(route, "_scope_name_and_user_stories", lambda *_a, **_k: ("golden", []))

    resp = asyncio.run(route.get_clarification_clarity(ScopeType("project"), "*", _request()))

    assert resp.totalUserStories == 0
    assert resp.overallScore is None
