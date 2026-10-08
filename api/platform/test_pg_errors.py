# -*- coding: utf-8 -*-
"""중앙 DB 가 거절한 것을 **사람 말로** 옮기는가.

## 왜 이 검사가 있나

2026-10-07 에 중앙 DB 의 연결 한계를 쟀다 — `max_connections` 100 · 예약 3 ·
포화시키면 `FATAL: sorry, too many clients already`. 그런데 **그 문장을 다루는 곳이
저장소에 0건**이었고, `PgUnavailable` 은 **잡는 쪽이 0개**였다. 그래서 21번째
사람에게는 "서버 오류"(500)만 보였다.

## 두 방향으로 다 틀릴 수 있다

```
안 옮기면   한계에 닿은 사람이 **왜 안 되는지 모른다**(그리고 기다리면 된다는 것도)
넘겨 옮기면 **진짜 고장이 "연결 문제" 로 분류돼 묻힌다** — 500 이어야 하는 것까지
           503 "잠시 뒤 다시" 가 되면, 고장이 사용자 탓처럼 보인다
```

그래서 "아는 다섯" 과 "모르는 것은 손대지 않는다" 를 같이 건다.
"""
from __future__ import annotations

from api.platform.pg_errors import explain, payload, sqlstate_of


class FakePgError(Exception):
    """psycopg 의 모양만 흉내 낸다 — 드라이버를 띄우지 않고 재려고."""

    def __init__(self, message: str, sqlstate: str | None = None, pgcode: str | None = None):
        super().__init__(message)
        if sqlstate is not None:
            self.sqlstate = sqlstate
        if pgcode is not None:
            self.pgcode = pgcode


# ---------------------------------------------------------------------------
# 아는 것
# ---------------------------------------------------------------------------


def test_too_many_connections_is_503_and_says_wait():
    told = explain(FakePgError("FATAL:  sorry, too many clients already", sqlstate="53300"))
    assert told is not None
    status, code, detail = told
    assert status == 503
    assert code == "DB_TOO_MANY_CONNECTIONS"
    # **할 일**이 있어야 한다 — 증상만 적으면 사람이 할 수 있는 것이 없다.
    assert "잠시 뒤 다시" in detail
    assert "max_connections" in detail


def test_too_many_connections_without_a_server_code():
    """게이트웨이를 거치면 코드가 안 실려 온다 — **문장으로도** 잡는다."""
    told = explain(Exception("connection failed: FATAL: sorry, too many clients already"))
    assert told is not None
    assert told[1] == "DB_TOO_MANY_CONNECTIONS"


def test_psycopg2_style_pgcode_is_also_read():
    """드라이버를 올리면 속성 이름이 바뀐다 — **둘 다** 본다."""
    assert sqlstate_of(FakePgError("nope", pgcode="53300")) == "53300"
    assert explain(FakePgError("nope", pgcode="53300"))[1] == "DB_TOO_MANY_CONNECTIONS"


def test_wrong_password_points_at_this_pc():
    told = explain(FakePgError('password authentication failed for user "robo"', sqlstate="28P01"))
    assert told[0] == 503
    assert told[1] == "DB_AUTH_FAILED"
    # 서버가 아니라 **이 PC** 가 문제라는 것이 핵이다.
    assert "이 PC" in told[2]


def test_missing_database_says_the_name_is_wrong():
    told = explain(FakePgError('database "og" does not exist', sqlstate="3D000"))
    assert told[1] == "DB_NO_DATABASE"
    assert "이름이 틀렸" in told[2]


def test_unreachable_says_it_may_be_another_machine():
    """중앙 모드에서 가장 흔한 실수다 — 주소가 **다른 기계**를 가리킨다."""
    for message in (
        "could not connect to server: Connection refused",
        "connection to server at 172.27.64.1, port 55432 failed: timeout expired",
        "could not translate host name \"robo-central\" to address",
    ):
        told = explain(Exception(message))
        assert told is not None, message
        assert told[1] == "DB_UNREACHABLE"
        assert "다른 기계" in told[2]


# ---------------------------------------------------------------------------
# 모르는 것은 **손대지 않는다**
# ---------------------------------------------------------------------------


def test_unknown_failures_stay_unknown():
    """아는 척 옮기면 **진짜 고장이 연결 문제로 분류돼 묻힌다.**"""
    assert explain(Exception("syntax error at or near \"slect\"")) is None
    assert explain(FakePgError("division by zero", sqlstate="22012")) is None
    assert explain(FakePgError("deadlock detected", sqlstate="40P01")) is None
    assert explain(ValueError("그냥 버그")) is None


def test_payload_shape_matches_the_graph_side():
    """화면은 `detail` 을 읽는다 — 그래프 쪽과 **같은 모양**이어야 한다."""
    body = payload(FakePgError("too many", sqlstate="53300"))
    assert set(body) == {"detail", "code"}
    assert payload(Exception("모르는 것")) is None


def test_detail_never_carries_the_connection_string():
    """접속 문자열에는 비밀번호가 섞인다 — **원문을 그대로 싣지 않는다.**"""
    leaky = FakePgError(
        "connection failed: host=172.27.64.1 user=robo password=supersecret dbname=og",
        sqlstate="28P01",
    )
    told = explain(leaky)
    assert "supersecret" not in told[2]
    assert "password" not in told[2]


# ---------------------------------------------------------------------------
# 전역 핸들러가 **실제로 걸려 있는가**
# ---------------------------------------------------------------------------


def test_app_registers_the_handler():
    """라우터마다 잡으면 한 곳이 빠진다 — 자리를 **하나만** 두고, 그 자리를 건다.

    이 검사가 없으면 핸들러를 지워도 아무도 모른다(지워진 뒤의 증상은 500 이고,
    그건 "원래 그런 줄" 알기 쉽다).
    """
    import api.main as main
    from api.platform.pg import PgUnavailable

    assert PgUnavailable in main.app.exception_handlers


def test_handler_maps_the_cause_not_the_wrapper():
    """서버 코드는 **원래 예외**에 있다. 감싼 쪽만 보면 영원히 모르는 실패다."""
    import asyncio

    import api.main as main
    from api.platform.pg import PgUnavailable

    wrapped = PgUnavailable("FATAL:  sorry, too many clients already")
    wrapped.__cause__ = FakePgError("FATAL:  sorry, too many clients already", sqlstate="53300")

    handler = main.app.exception_handlers[PgUnavailable]
    response = asyncio.run(handler(None, wrapped))

    assert response.status_code == 503
    assert b"DB_TOO_MANY_CONNECTIONS" in response.body


def test_handler_reraises_what_it_does_not_know():
    """모르는 실패는 **500 으로 둔다** — 아는 척하면 고장이 묻힌다."""
    import asyncio

    import api.main as main
    from api.platform.pg import PgUnavailable

    wrapped = PgUnavailable("뭔가 이상하다")
    wrapped.__cause__ = FakePgError("deadlock detected", sqlstate="40P01")

    handler = main.app.exception_handlers[PgUnavailable]
    try:
        asyncio.run(handler(None, wrapped))
    except PgUnavailable:
        return
    raise AssertionError("모르는 실패를 조용히 503 으로 옮겼다")
