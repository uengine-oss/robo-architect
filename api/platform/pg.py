"""Ontological 이 얹혀 있는 Postgres 로 직접 가는 길.

그래프는 Bolt(Cypher)로 읽고 쓴다. 그런데 **권한과 사용자는 SQL 이다** —
`og_grant(role, level, graph)` 는 Postgres 함수이고 Bolt 게이트웨이는 Cypher 만
말한다. 그래서 이 둘은 같은 연결로 갈 수 없다.

접속 정보는 `NEO4J_*` 에서 끌어온다. 같은 서버의 다른 포트일 뿐이라, 호스트와
자격을 따로 적어 두면 한쪽만 고쳤을 때 **조용히 다른 데를 본다** — 이 저장소가
설정 키 불일치로 네 번 막혔던 자리다(`STATUS.md` §1).

```
NEO4J_URI=bolt://localhost:28687   →  host=localhost
OG_PG_PORT (기본 28816)            →  port
NEO4J_USER / NEO4J_PASSWORD        →  자격
OG_PG_DATABASE (기본 og)           →  데이터베이스 — graph 가 아니다
```

`NEO4J_DATABASE` 는 **graph 이름**이지 Postgres 데이터베이스가 아니다. 둘을
헷갈리면 접속은 되고 표만 안 보인다.
"""

from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Any, Iterator
from urllib.parse import urlparse

import psycopg
from psycopg.rows import dict_row

__all__ = ["connection", "query", "execute", "pg_dsn", "PgUnavailable"]


class PgUnavailable(RuntimeError):
    """Postgres 에 붙을 수 없다. 호출부가 기능을 끄고 안내할 수 있게 구분한다."""


def _host_from_bolt(uri: str) -> str:
    """`bolt://host:port` 에서 호스트만 꺼낸다. 스킴이 없어도 견딘다."""
    raw = (uri or "").strip()
    if not raw:
        return "localhost"
    if "://" not in raw:
        raw = "bolt://" + raw
    return urlparse(raw).hostname or "localhost"


def pg_dsn() -> str:
    """접속 문자열. 비밀번호는 여기서만 다루고 로그에 싣지 않는다."""
    explicit = os.environ.get("OG_PG_DSN")
    if explicit:
        return explicit
    host = os.environ.get("OG_PG_HOST") or _host_from_bolt(os.environ.get("NEO4J_URI", ""))
    port = os.environ.get("OG_PG_PORT", "28816")
    dbname = os.environ.get("OG_PG_DATABASE", "og")
    user = os.environ.get("OG_PG_USER") or os.environ.get("NEO4J_USER", "dev")
    password = os.environ.get("OG_PG_PASSWORD") or os.environ.get("NEO4J_PASSWORD", "")
    return f"host={host} port={port} dbname={dbname} user={user} password={password}"


@contextmanager
def connection() -> Iterator[psycopg.Connection]:
    """자동 커밋이 아닌 연결. 블록을 정상으로 빠져나가면 커밋한다.

    풀을 두지 않는 이유는 이 경로가 뜨겁지 않기 때문이다 — 로그인·승인·공유는
    사람의 속도로 일어난다. 그래프 읽기와 달리 요청마다 열어도 된다.
    """
    try:
        conn = psycopg.connect(pg_dsn(), row_factory=dict_row)
    except psycopg.Error as exc:  # 접속 자체가 안 되는 경우
        raise PgUnavailable(str(exc).split("\n")[0]) from exc
    try:
        with conn:
            yield conn
    finally:
        conn.close()


def query(sql: str, params: tuple | dict | None = None) -> list[dict[str, Any]]:
    """읽기. 행을 dict 로 돌려준다."""
    with connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            if cur.description is None:
                return []
            return list(cur.fetchall())


def execute(sql: str, params: tuple | dict | None = None) -> int:
    """쓰기. 영향받은 행 수를 돌려준다."""
    with connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            return cur.rowcount
