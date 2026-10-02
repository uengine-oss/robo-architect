# -*- coding: utf-8 -*-
"""접속 문자열 — **빈 값이 멈춤이 되지 않게** (2026-10-02).

## 무엇이 멈췄나

`password=` 뒤에 다른 키를 붙이는 순간, 비밀번호가 없는 환경에서 `psycopg.connect`
가 **영영 안 돌아왔다.** 끝에 있을 때는 멀쩡하던 것이라, `connect_timeout` 을
덧붙이면서 드러났다 — 템플릿 목록 호출 하나가 수십 초를 먹다가 멈췄다.

고장이 조용하다는 것이 핵심이다. 오류도 안 나고, 제한시간도 안 듣는다.

## 여기서 재는 것

```
① 빈 비밀번호는 **아예 안 싣는다** (실린 적이 없으면 멈출 일도 없다)
② 있으면 싣는다
③ 제한시간이 늘 붙는다 — 없으면 OS 의 TCP 재시도가 끝날 때까지 기다린다
```
"""

from __future__ import annotations

import pytest

from api.platform import pg


@pytest.fixture(autouse=True)
def _clean(monkeypatch: pytest.MonkeyPatch):
    for k in ("OG_PG_DSN", "OG_PG_HOST", "OG_PG_PORT", "OG_PG_DATABASE", "OG_PG_USER",
              "OG_PG_PASSWORD", "OG_PG_CONNECT_TIMEOUT", "NEO4J_URI", "NEO4J_USER",
              "NEO4J_PASSWORD"):
        monkeypatch.delenv(k, raising=False)
    yield


def _keys(dsn: str) -> dict[str, str]:
    return dict(part.split("=", 1) for part in dsn.split(" ") if "=" in part)


def test_빈_비밀번호는_싣지_않는다():
    dsn = pg.pg_dsn()
    assert "password=" not in dsn
    # 그래도 나머지는 온전해야 한다 — 빼는 것이 망가뜨리는 것이면 안 된다.
    keys = _keys(dsn)
    assert keys["host"] and keys["port"] and keys["dbname"] and keys["user"]


def test_비밀번호가_있으면_싣는다(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("NEO4J_PASSWORD", "s3cret")
    assert _keys(pg.pg_dsn())["password"] == "s3cret"


def test_제한시간이_늘_붙는다():
    assert int(_keys(pg.pg_dsn())["connect_timeout"]) > 0


def test_제한시간은_환경으로_바꾼다(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("OG_PG_CONNECT_TIMEOUT", "2")
    assert _keys(pg.pg_dsn())["connect_timeout"] == "2"


def test_명시한_DSN_은_그대로_쓴다(monkeypatch: pytest.MonkeyPatch):
    """직접 준 문자열을 고쳐 쓰면 **준 사람이 모르는 접속**이 된다."""
    monkeypatch.setenv("OG_PG_DSN", "postgresql://a/b")
    assert pg.pg_dsn() == "postgresql://a/b"


def test_Bolt_주소에서_호스트를_가져온다(monkeypatch: pytest.MonkeyPatch):
    """호스트를 따로 적어 두면 한쪽만 고쳤을 때 **조용히 다른 데를 본다.**"""
    monkeypatch.setenv("NEO4J_URI", "bolt://10.10.0.5:57687")
    assert _keys(pg.pg_dsn())["host"] == "10.10.0.5"
