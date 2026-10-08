# -*- coding: utf-8 -*-
"""Postgres 가 거절한 것을 **사람이 읽을 수 있는 말**로 옮긴다.

## 왜 있어야 하나 (2026-10-07 실측)

중앙 DB 는 PC 20여 대가 **같이** 본다. 그 서버의 연결 한계를 재 봤다 —

```
max_connections                100
superuser_reserved_connections   3
포화시키니                      FATAL:  sorry, too many clients already
                              (TCP 로 붙어도 같은 문장)
```

그런데 **그 문장을 다루는 곳이 저장소에 0건**이었다(`api/`·`desktop/src` 에서
`too many clients`·`53300`·`TooManyConnections` 를 찾으면 벤더 라이브러리의 정의뿐).
즉 한계에 닿은 21번째 사람에게는 **일반 실패**로 보인다 — 058 이 없애려던
"조용히 비는 화면" 이 연결 쪽에 그대로 남아 있었다.

같은 자리에 하나 더 있었다. `PgUnavailable` 은 "호출부가 기능을 끄고 안내할 수
있게 구분한다" 고 적혀 있었는데 **잡는 쪽이 0개**였다. 그래서 접속 실패는 이름만
구분된 채 **500 으로 올라갔다.** 이 저장소에서 같은 모양을 네 번째로 본다 —
만들어 두고 아무도 안 부르는 구분.

## 무엇을 가르나

```
53300  연결이 한계다        → 503. **잠시 뒤 다시** 하면 된다. 고장이 아니다
53400  연결 자원이 모자라다  → 503. 같은 말로 묶는다(원인은 서버 쪽 설정이다)
28P01  비밀번호가 틀렸다     → 503. 서버가 아니라 **이 PC 의 설정**이 문제다
3D000  데이터베이스가 없다   → 503. 주소는 맞고 이름이 틀렸다
붙지 못했다(연결 거부·시간 초과) → 503. 서버가 꺼졌거나 **주소가 다른 기계**다
```

전부 **500 이 아니다.** 500 은 "우리 잘못이고 원인을 모른다" 는 뜻이고, 여기 다섯은
원인을 정확히 안다. 모르는 실패는 `None` 으로 돌려 **아는 척하지 않는다** — 그래야
진짜 고장이 "연결 문제" 로 분류돼 묻히지 않는다.
"""

from __future__ import annotations

from typing import Any

__all__ = ["explain", "payload", "sqlstate_of"]

# 고칠 수 있는 말이어야 한다. **증상이 아니라 할 일**을 적는다.
TOO_MANY_DETAIL = (
    "중앙 DB 에 지금 접속할 자리가 없습니다(동시 접속 한계). "
    "잠시 뒤 다시 시도해 주세요 — 계속 이러면 설치 담당자에게 "
    "서버의 max_connections 를 늘려 달라고 전해 주세요."
)

AUTH_DETAIL = (
    "이 PC 의 중앙 DB 접속 자격이 서버의 값과 다릅니다. "
    "그래서 이 PC 에서만 안 됩니다 — 설치 담당자에게 이 메시지를 그대로 전해 주세요."
)

NO_DATABASE_DETAIL = (
    "중앙 DB 에 붙었지만 지정된 데이터베이스가 없습니다. "
    "주소는 맞고 이름이 틀렸습니다 — 설치 담당자에게 전해 주세요."
)

UNREACHABLE_DETAIL = (
    "중앙 DB 에 붙지 못했습니다. 서버가 꺼져 있거나, 이 PC 가 보는 주소가 "
    "다른 기계를 가리키고 있습니다 — 설치 담당자에게 이 메시지를 그대로 전해 주세요."
)

# 붙지도 못한 경우. libpq 가 영어로 내는 문장이라 **그 문장으로** 가른다 —
# `sqlstate` 가 없는 실패이기 때문이다(서버까지 못 갔으니 서버 코드가 없다).
_UNREACHABLE_MARKS = (
    "could not connect",
    "connection refused",
    "connection timed out",
    "timeout expired",
    "no route to host",
    "server closed the connection unexpectedly",
    "could not translate host name",
    "network is unreachable",
)


def sqlstate_of(exc: BaseException) -> str:
    """psycopg 가 실어 주는 서버 코드. 없으면 빈 문자열.

    psycopg3 는 `exc.sqlstate`, psycopg2 는 `exc.pgcode` 다. **둘 다 본다** —
    한쪽만 보면 드라이버를 올리는 날 조용히 모르는 실패가 된다.
    """
    for attribute in ("sqlstate", "pgcode"):
        value = getattr(exc, attribute, None)
        if value:
            return str(value)
    return ""


def explain(exc: BaseException) -> tuple[int, str, str] | None:
    """`(상태코드, 코드, 사람에게 할 말)`. 우리가 아는 거절이 아니면 `None`."""
    state = sqlstate_of(exc)
    if state in ("53300", "53400"):
        return 503, "DB_TOO_MANY_CONNECTIONS", TOO_MANY_DETAIL
    if state in ("28P01", "28000"):
        return 503, "DB_AUTH_FAILED", AUTH_DETAIL
    if state == "3D000":
        return 503, "DB_NO_DATABASE", NO_DATABASE_DETAIL

    # 서버 코드가 없는 실패 — 서버까지 못 갔다는 뜻이다. 문장으로 가른다.
    text = str(exc).lower()
    if "too many clients" in text:
        # 코드가 안 실려 오는 경로(게이트웨이·프록시)를 위해 한 겹 더 둔다.
        return 503, "DB_TOO_MANY_CONNECTIONS", TOO_MANY_DETAIL
    if any(mark in text for mark in _UNREACHABLE_MARKS):
        return 503, "DB_UNREACHABLE", UNREACHABLE_DETAIL
    return None


def payload(exc: BaseException) -> dict[str, Any] | None:
    """`explain` 을 응답 본문 모양으로. 라우터는 `detail` 을 읽는다."""
    told = explain(exc)
    if not told:
        return None
    _status, code, detail = told
    return {"detail": detail, "code": code}
