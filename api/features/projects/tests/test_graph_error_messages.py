# -*- coding: utf-8 -*-
"""그래프의 거절이 **500 으로 조용해지지 않는다** (2026-10-02).

## 무엇이 조용했나

중앙 DB 에서 `AUTH_ROLE_SECRET` 이 서버와 다른 PC 를 쓰면, 읽기 등급 사용자가
프로젝트를 여는 순간 `AuthError`(`Neo.ClientError.Security.Unauthorized`)가 나고
화면에는 **500 "서버 오류"** 만 보였다. 같은 원인을 `ensure_role` 쪽은 503 과 함께
"이 PC 의 값이 다르다" 로 말해 준다 — 사람이 **먼저 만나는 쪽**이 침묵하던 것이다.

## 여기서 재는 것

```
① AuthError   → 503 + 고칠 수 있는 말 (서버가 아니라 이 PC 의 설정이다)
② Forbidden   → 403 (등급이 막은 것이고 고장이 아니다)
③ 그 밖의 것   → **그대로 500** — 모르는 실패를 "권한 문제"로 분류하면 묻힌다
④ 실제 앱의 배선으로 잰다 — 해석하는 자리를 베껴 두면 저쪽이 바뀌어도 통과한다
```
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from neo4j.exceptions import AuthError, DatabaseError, Forbidden

from api.platform.identity import graph_errors


# ── 판정 ──────────────────────────────────────────────────────────────────

def test_자격_실패는_503_이고_할_일을_말한다():
    status, code, detail = graph_errors.explain(AuthError("unauthorized"))
    assert status == 503 and code == "GRAPH_ROLE_AUTH_FAILED"
    # 증상("Unauthorized")이 아니라 **무엇을 해야 하는가**가 담겨야 한다.
    assert "AUTH_ROLE_SECRET" in detail
    assert "다른 PC" in detail and "설치 담당자" in detail


def test_권한_없음은_403_이다():
    status, code, _ = graph_errors.explain(Forbidden("permission denied"))
    assert status == 403 and code == "GRAPH_PERMISSION_DENIED"


def test_서버_코드만_와도_알아본다():
    """게이트웨이를 거치면 클래스가 아니라 코드만 남는 경우가 있다."""
    class _Odd(Exception):
        code = "Neo.ClientError.Security.Unauthorized"

    assert graph_errors.explain(_Odd())[0] == 503


def test_모르는_실패는_손대지_않는다():
    """`None` 이어야 500 이 유지된다 — 진짜 고장을 권한 문제로 숨기지 않는다."""
    assert graph_errors.explain(DatabaseError("disk full")) is None
    assert graph_errors.explain(RuntimeError("뭔가")) is None


# ── 실제 앱 배선 ───────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def client() -> TestClient:
    """**진짜 앱**에 시험용 길을 하나 붙인다. 배선을 베껴 두면 뜻이 없다."""
    from api.main import app

    @app.get("/__test__/graph-error/{kind}")
    async def _boom(kind: str):  # pragma: no cover - 시험용 길
        if kind == "auth":
            raise AuthError("unauthorized")
        if kind == "forbidden":
            raise Forbidden("permission denied for table og_role_player")
        raise DatabaseError("disk full")

    return TestClient(app, raise_server_exceptions=False)


def test_앱이_자격_실패를_503_으로_답한다(client: TestClient):
    r = client.get("/__test__/graph-error/auth")
    assert r.status_code == 503
    body = r.json()
    assert body["code"] == "GRAPH_ROLE_AUTH_FAILED"
    assert "AUTH_ROLE_SECRET" in body["detail"]


def test_앱이_권한_없음을_403_으로_답한다(client: TestClient):
    r = client.get("/__test__/graph-error/forbidden")
    assert r.status_code == 403
    assert r.json()["code"] == "GRAPH_PERMISSION_DENIED"


def test_앱이_모르는_오류는_500_으로_둔다(client: TestClient):
    assert client.get("/__test__/graph-error/other").status_code == 500
