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
import threading
import time
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any, Iterator
from urllib.parse import urlparse

import psycopg
from psycopg.rows import dict_row

__all__ = ["connection", "query", "execute", "pg_dsn", "PgUnavailable"]


class PgUnavailable(RuntimeError):
    """Postgres 에 붙을 수 없다.

    **이 구분을 잡는 곳이 0개였다**(2026-10-08 실측). "호출부가 기능을 끄고 안내할
    수 있게" 만들어 둔 이름인데, 아무도 안 잡아서 접속 실패가 그대로 500 으로
    올라갔다. 이제 `api/main.py` 가 전역에서 받아 `pg_errors.explain` 으로 옮긴다 —
    라우터마다 잡으면 **한 곳이 빠지고, 빠진 곳은 다시 500 으로 조용해진다.**

    원래 예외를 `__cause__` 로 들고 간다(서버 코드가 거기 있다).
    """


_request_dsn: ContextVar[str | None] = ContextVar("pg_request_dsn", default=None)


@contextmanager
def using_dsn(dsn: str):
    """Server-selected DB credentials, scoped to one task; never from request headers."""
    token = _request_dsn.set(dsn)
    try:
        yield
    finally:
        _request_dsn.reset(token)


def _host_from_bolt(uri: str) -> str:
    """`bolt://host:port` 에서 호스트만 꺼낸다. 스킴이 없어도 견딘다."""
    raw = (uri or "").strip()
    if not raw:
        return "localhost"
    if "://" not in raw:
        raw = "bolt://" + raw
    return urlparse(raw).hostname or "localhost"


# 붙는 데 이만큼 걸리면 **안 붙는 것으로 본다**.
#
# 기본값이 없으면 psycopg 는 OS 의 TCP 재시도가 끝날 때까지 기다린다 — 중앙 DB 가
# 꺼져 있거나 주소가 틀린 PC 에서 요청 하나가 수십 초를 먹는다(2026-10-02 실측:
# 템플릿 목록 호출 하나가 그렇게 늘어졌다). **멈춘 화면보다 빨리 틀리는 편이 낫다** —
# 호출부는 `PgUnavailable` 을 이미 다룬다.
_CONNECT_TIMEOUT_SECONDS = "5"


def pg_dsn() -> str:
    """접속 문자열. 비밀번호는 여기서만 다루고 로그에 싣지 않는다."""
    explicit = _request_dsn.get() or os.environ.get("OG_PG_DSN")
    if explicit:
        return explicit
    host = os.environ.get("OG_PG_HOST") or _host_from_bolt(os.environ.get("NEO4J_URI", ""))
    port = os.environ.get("OG_PG_PORT", "28816")
    dbname = os.environ.get("OG_PG_DATABASE", "og")
    user = os.environ.get("OG_PG_USER") or os.environ.get("NEO4J_USER", "dev")
    password = os.environ.get("OG_PG_PASSWORD") or os.environ.get("NEO4J_PASSWORD", "")
    timeout = (os.environ.get("OG_PG_CONNECT_TIMEOUT") or _CONNECT_TIMEOUT_SECONDS).strip()
    # **빈 값은 아예 안 쓴다.** `password=` 뒤에 다른 키가 오면 libpq 가 그 자리에서
    # 멈춘다 — 비밀번호가 없는 환경에서 모든 PG 호출이 영영 안 돌아왔다(2026-10-02
    # 실측). 끝에 있을 때는 멀쩡하던 것이라, 키를 하나 덧붙이는 순간 드러났다.
    parts = [f"host={host}", f"port={port}", f"dbname={dbname}", f"user={user}"]
    if password:
        parts.append(f"password={password}")
    if timeout:
        parts.append(f"connect_timeout={timeout}")
    return " ".join(parts)


# ── 연결 재사용 ─────────────────────────────────────────────────────────
#
# 예전에는 부를 때마다 새로 붙었다("이 경로는 뜨겁지 않다"). 협업이 들어오며 뜨거워졌다 —
# 창 하나가 2초마다 6번(collab 스트림) + 10초마다 7번(heartbeat)을 부른다. 포스코 로컬에서
# 잰 값(2026-11-19): 붙고 조회 한 번 평균 4.5ms, 창 20개면 graph-db CPU 55% · API 의 /health
# p95 663ms. 쉬는 연결을 DSN 마다 몇 개 남겨 두고 다시 쓴다.
#
# 세션 상태를 남기는 호출(SET ROLE · LISTEN · 임시 테이블)은 여기를 쓰지 않는다(지금 없다).
# 오류가 난 연결 · 트랜잭션이 열린 채 돌아온 연결 · 오래 쉰 연결은 버린다.
_POOL_MAX_IDLE = int(os.getenv("ROBO_PG_POOL_IDLE", "8"))
_POOL_MAX_AGE = 300.0  # 초 — DB 가 다시 떠도 오래된 연결을 오래 붙들지 않는다
_POOL_PING_AFTER = 30.0  # 초 — 이만큼 쉰 연결은 내주기 전에 한 번 확인한다
_pool: dict[str, list[tuple[psycopg.Connection, float, float]]] = {}
_pool_lock = threading.Lock()


def _checkout(dsn: str) -> psycopg.Connection:
    now = time.monotonic()
    while True:
        with _pool_lock:
            idle = _pool.get(dsn) or []
            item = idle.pop() if idle else None
        if item is None:
            break
        conn, born, last_used = item
        if conn.closed or conn.broken or now - born > _POOL_MAX_AGE:
            conn.close()
            continue
        if now - last_used > _POOL_PING_AFTER:
            try:
                conn.execute("SELECT 1")
                conn.rollback()
            except psycopg.Error:
                conn.close()
                continue
        return conn
    try:
        conn = psycopg.connect(dsn, row_factory=dict_row)
    except psycopg.Error as exc:  # 접속 자체가 안 되는 경우
        raise PgUnavailable(str(exc).split("\n")[0]) from exc
    conn._robo_born = now  # type: ignore[attr-defined]
    return conn


def _checkin(dsn: str, conn: psycopg.Connection) -> None:
    if (_POOL_MAX_IDLE <= 0 or conn.closed or conn.broken
            or conn.info.transaction_status != psycopg.pq.TransactionStatus.IDLE):
        conn.close()
        return
    born = getattr(conn, "_robo_born", time.monotonic())
    with _pool_lock:
        idle = _pool.setdefault(dsn, [])
        if len(idle) < _POOL_MAX_IDLE:
            idle.append((conn, born, time.monotonic()))
            return
    conn.close()


@contextmanager
def connection() -> Iterator[psycopg.Connection]:
    """자동 커밋이 아닌 연결. 블록을 정상으로 빠져나가면 커밋하고, 예외면 되돌린다.

    연결은 DSN 마다 쉬는 것을 몇 개 남겨 두고 다시 쓴다(위 "연결 재사용").
    """
    dsn = pg_dsn()
    conn = _checkout(dsn)
    try:
        yield conn
    except BaseException:
        try:
            conn.rollback()
        except Exception:  # noqa: BLE001 — 끊긴 연결이면 버린다
            conn.close()
        raise
    else:
        try:
            conn.commit()
        except BaseException:
            conn.close()
            raise
    finally:
        if not conn.closed:
            _checkin(dsn, conn)


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
