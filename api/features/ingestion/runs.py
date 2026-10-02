# -*- coding: utf-8 -*-
"""적재가 **돌고 있었다는 사실**을 프로세스 밖에 적어 둔다.

## 왜 있어야 하나

적재는 **지우기로 시작한다**. 하이브리드는 `clear_all_hybrid_workspace()`, 표준
경로는 `clear_event_storming_nodes()` 가 그 프로젝트의 생성물을 통째로 지우고 나서
수 분이 걸리는 추출로 들어간다. 그 사이에 앱이 강제 종료되면 —

```
세션          `_sessions` 는 **그 프로세스의 메모리**다(`ingestion_sessions.py`).
             백엔드가 앱과 같이 죽으면 "돌고 있었다" 는 기록이 어디에도 없다
BpmSession    완료 표시가 없다. 반쯤 쓰인 판이 완주한 판과 **구별되지 않는다**
화면          SSE 는 끊긴 자리에서 끝난다. 다시 접속하면 아무 말도 없다
```

남는 것은 **설계가 지워진 프로젝트**이고, 그것을 다음에 여는 사람은 무슨 일이
있었는지 알 길이 없다. 그래서 **지우기 전에** 한 줄 적고, 완주하면 닫는다. 죽은
뒤에는 쓸 수 없으니 이 순서는 거꾸로일 수 없다.

## 왜 Postgres 인가

graph 에 두면 **다음 wipe 가 그것까지 지운다** — `projects/snapshots.py` 가 같은
이유로 Postgres 에 쌓는다. 이 표는 그 wipe 바깥에 있어야 뜻이 있다.

## 왜 심장박동이 스레드인가

살아 있음을 재는 값이 `beat_at` 하나다. 이것을 asyncio 과제로 갱신하면, 추출
단계의 동기 호출이 이벤트 루프를 붙잡는 순간 박동이 멈춘다 — **멀쩡히 돌고 있는
작업이 중단으로 보인다**. 별도 스레드는 루프가 막혀도 뛴다.

## 왜 중단 판정을 읽을 때 하는가

중단을 적어야 할 사람이 **죽은 사람**이다. 그래서 잠금과 같은 모양을 쓴다 — 행은
`running` 으로 남고, 박동이 늙었으면 **읽는 쪽이** 중단으로 읽는다
(`collab/store.py` 의 `LOCK_ABSENT_GRACE_SECONDS` 와 같은 생각이다). 늦게 돌아온
작업이 다시 박동하면 저절로 `running` 으로 돌아온다.

사람이 멈춘 것(`cancelled`)과 오류로 끝난 것(`error`)은 중단이 아니다 — 그때는
화면이 이미 말을 했거나 사람이 스스로 멈춘 것이다. 경고는 **말할 사람이 없었던
경우**에만 띄운다.

## 권한은 이 표가 아니라 앱이 본다 — TPL-1 도 같은 자리다

`public.*` 표는 `pg.connection()` 으로 열리고 그 자격은 **소유자**
(`NEO4J_USER`/`NEO4J_PASSWORD`)다. 사용자 role 로 붙는 읽기 경로와 달리
**Postgres 가 격리를 걸어 주지 않는다.** 그래서 graph 로 거르는 일과 "이 사람이
이 프로젝트를 볼 수 있나" 를 **라우터가** 한다.

> 코드 생성 템플릿을 DB 로 옮길 때(TPL-1) 이 문장이 그대로 적용된다. 템플릿 표를
> `public.*` 에 두면 **관리자만 고칠 수 있다는 규칙도 앱이 지켜야 한다** — 등급으로
> 막힐 것이라 기대하면 아무도 안 막는다.
"""

from __future__ import annotations

import json
import os
import secrets
import threading
from datetime import datetime, timezone
from typing import Any, Callable, Iterable, Optional

from api.platform import pg
from api.platform.neo4j import design_database
from api.platform.observability.smart_logger import SmartLogger

__all__ = [
    "ensure_schema", "start", "beat", "note", "finish", "heartbeat", "Heartbeat",
    "state", "classify", "acknowledge", "interrupted_session_ids",
    "BEAT_SECONDS", "ABSENT_GRACE_SECONDS",
]

# 박동 주기. 짧을수록 중단이 빨리 보이지만 쓰기가 그만큼 잦아진다.
BEAT_SECONDS = 10

# 박동이 이만큼 끊기면 **중단된 것으로 읽는다**.
#
# 넉넉해야 한다 — 추출이 외부 추출기를 기다리는 동안 PC 가 바쁘면 스레드도 밀린다.
# 다섯 번을 놓쳐도 버티게 둔다. 잠금(25초)보다 큰 이유는 잠금이 재는 것이 사람의
# 접속(5초마다 알린다)이고 이쪽은 **한 작업의 생존**이라서다.
ABSENT_GRACE_SECONDS = 60

assert ABSENT_GRACE_SECONDS > BEAT_SECONDS * 3

# 프로젝트당 남기는 행 수. 이력이 아니라 **지금 할 말**을 들고 있는 표다.
RETENTION = 50

_SCHEMA = """
CREATE TABLE IF NOT EXISTS public.app_ingestion_runs (
    run_id      TEXT PRIMARY KEY,
    graph       TEXT NOT NULL,
    session_id  TEXT NOT NULL,
    uid         TEXT,
    kind        TEXT NOT NULL,
    status      TEXT NOT NULL,
    started_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    beat_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    ended_at    TIMESTAMPTZ,
    acked_at    TIMESTAMPTZ,
    acked_by    TEXT,
    value       JSONB NOT NULL DEFAULT '{}'::jsonb
);
CREATE INDEX IF NOT EXISTS idx_app_ingestion_runs_graph
    ON public.app_ingestion_runs (graph, started_at DESC);
"""


def ensure_schema() -> None:
    with pg.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(_SCHEMA)


def _warn(what: str, exc: Exception, **params: Any) -> None:
    """기록이 실패해도 적재는 막지 않는다. **다만 조용히 넘어가지 않는다.**"""
    SmartLogger.log(
        "WARN", f"적재 기록 {what} 실패 (적재는 계속한다): {exc}",
        category="ingestion.runs.error",
        params={"what": what, "error": str(exc), **params},
    )


def start(
    graph: Optional[str],
    session_id: str,
    *,
    uid: Optional[str] = None,
    kind: str = "hybrid",
    counts: Optional[dict[str, int]] = None,
) -> Optional[str]:
    """**지우기 전에** 부른다. 실패하면 `None` — 적재는 그대로 간다.

    `counts` 는 이 적재가 지울 것들의 라벨별 건수다. 지운 뒤에는 셀 수 없으므로
    여기서 받아 둔다. 경고가 "무엇이 없어졌는지" 를 말할 수 있는 근거는 이 값뿐이다.
    """
    # graph 를 안 주면 이 요청이 보고 있는 프로젝트다. 부르는 자리가 둘(표준·하이브리드)
    # 이라 양쪽이 같은 계산을 베껴 두지 않게 여기서 한 번만 푼다.
    graph = graph or design_database()
    if not graph or not session_id:
        return None
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    run_id = f"{session_id}-{stamp}-{secrets.token_hex(2)}"
    total = sum((counts or {}).values())
    value = {
        "wiped": counts or {},
        "wipedTotal": total,
        # 어느 PC 에서 돌던 작업인가. 중앙 DB 에서는 **남의 PC 가 죽은 것을 내가 본다.**
        "host": os.environ.get("COMPUTERNAME") or os.environ.get("HOSTNAME") or "",
    }
    try:
        ensure_schema()
        pg.execute(
            "INSERT INTO public.app_ingestion_runs "
            "(run_id, graph, session_id, uid, kind, status, value) "
            "VALUES (%s, %s, %s, %s, %s, 'running', %s::jsonb)",
            (run_id, graph, session_id, uid or None, kind,
             json.dumps(value, ensure_ascii=False)),
        )
        _prune(graph)
        SmartLogger.log(
            "INFO", "적재 시작을 기록했다",
            category="ingestion.runs.start",
            params={"run_id": run_id, "graph": graph, "session_id": session_id,
                    "uid": uid, "kind": kind, "wiped_total": total},
        )
        return run_id
    except Exception as exc:  # noqa: BLE001 — 기록 실패가 적재를 막지 않는다
        _warn("start", exc, graph=graph, session_id=session_id)
        return None


def note(run_id: Optional[str], **fields: Any) -> None:
    """`value` 에 몇 가지를 덧붙인다(겹치면 새 값이 이긴다)."""
    if not run_id or not fields:
        return
    try:
        pg.execute(
            "UPDATE public.app_ingestion_runs SET value = value || %s::jsonb "
            "WHERE run_id = %s",
            (json.dumps(fields, ensure_ascii=False, default=str), run_id),
        )
    except Exception as exc:  # noqa: BLE001
        _warn("note", exc, run_id=run_id)


def beat(run_id: Optional[str]) -> None:
    """살아 있다고 알린다. `running` 이 아닌 행은 건드리지 않는다."""
    if not run_id:
        return
    try:
        pg.execute(
            "UPDATE public.app_ingestion_runs SET beat_at = now() "
            "WHERE run_id = %s AND status = 'running'",
            (run_id,),
        )
    except Exception as exc:  # noqa: BLE001
        _warn("beat", exc, run_id=run_id)


def finish(run_id: Optional[str], status: str = "complete", message: str = "") -> None:
    """작업을 닫는다. `running` 이 아니면 아무것도 안 한다 — 처음 닫은 사유가 남는다."""
    if not run_id:
        return
    if status not in ("complete", "error", "cancelled"):
        status = "complete"
    try:
        pg.execute(
            "UPDATE public.app_ingestion_runs "
            "SET status = %s, ended_at = now(), value = value || %s::jsonb "
            "WHERE run_id = %s AND status = 'running'",
            (status, json.dumps({"message": message or ""}, ensure_ascii=False), run_id),
        )
    except Exception as exc:  # noqa: BLE001
        _warn("finish", exc, run_id=run_id, status=status)


def _prune(graph: str) -> None:
    """끝난 행만 걷는다 — **돌고 있는 것은 절대 지우지 않는다.**"""
    try:
        pg.execute(
            "DELETE FROM public.app_ingestion_runs WHERE graph = %s AND run_id IN ("
            " SELECT run_id FROM public.app_ingestion_runs"
            "  WHERE graph = %s AND status <> 'running'"
            "  ORDER BY started_at DESC OFFSET %s)",
            (graph, graph, RETENTION),
        )
    except Exception as exc:  # noqa: BLE001
        _warn("prune", exc, graph=graph)


# ── 심장박동 ────────────────────────────────────────────────────────────────

def _beat_loop(
    tick: Callable[[], None],
    stop: threading.Event,
    interval: float,
) -> None:
    """멈추라고 할 때까지 뛴다.

    기다리는 일을 `Event.wait` 가 하므로 **종료가 한 주기만큼 늦어지지 않는다**.
    검사는 `stop` 을 미리 세팅해 두고 한 번 뛰는 것까지 본다.
    """
    while True:
        tick()
        if stop.wait(interval):
            return


class Heartbeat:
    """`stop()` 까지 `beat_at` 을 갱신한다. **데몬 스레드**라 프로세스를 붙잡지 않는다."""

    def __init__(self, run_id: Optional[str], interval: float = BEAT_SECONDS) -> None:
        self.run_id = run_id
        self._stop = threading.Event()
        self.thread: Optional[threading.Thread] = None
        if not run_id:
            return
        self.thread = threading.Thread(
            target=_beat_loop,
            args=(lambda: beat(run_id), self._stop, interval),
            name=f"ingestion-beat-{run_id[:12]}",
            daemon=True,
        )
        self.thread.start()

    def stop(self) -> None:
        self._stop.set()


def heartbeat(run_id: Optional[str], interval: float = BEAT_SECONDS) -> Heartbeat:
    return Heartbeat(run_id, interval)


# ── 읽기 ────────────────────────────────────────────────────────────────────

def _iso(v: Any) -> Optional[str]:
    if v is None:
        return None
    return v.isoformat() if hasattr(v, "isoformat") else str(v)


def _view(row: dict[str, Any]) -> dict[str, Any]:
    value = row.get("value") or {}
    return {
        "runId": row.get("run_id"),
        "sessionId": row.get("session_id"),
        "uid": row.get("uid"),
        "displayName": row.get("who") or row.get("uid") or "",
        "kind": row.get("kind"),
        "startedAt": _iso(row.get("started_at")),
        "lastBeatAt": _iso(row.get("beat_at")),
        "host": value.get("host") or "",
        "wiped": value.get("wiped") or {},
        "wipedTotal": int(value.get("wipedTotal") or 0),
        "snapshots": value.get("snapshots") or [],
        "phase": value.get("phase") or "",
    }


def state(graph: Optional[str], *, now: Optional[datetime] = None) -> dict[str, Any]:
    """이 프로젝트에서 **지금 돌고 있는 것**과 **중단된 것**.

    SQL 은 범위만 좁히고(이 graph · `running` · 아직 안 닫은 것) 중단 판정은
    파이썬이 한다 — 문턱이 한 곳에만 있고, DB 없이도 검사할 수 있다.
    """
    empty: dict[str, Any] = {"running": [], "interrupted": []}
    if not graph:
        return empty
    try:
        rows = pg.query(
            "SELECT r.run_id, r.graph, r.session_id, r.uid, r.kind, r.status,"
            "       r.started_at, r.beat_at, r.value,"
            "       COALESCE(u.value->>'displayName', r.uid) AS who"
            "  FROM public.app_ingestion_runs r"
            "  LEFT JOIN public.app_users u ON u.uid = r.uid"
            " WHERE r.graph = %s AND r.status = 'running' AND r.acked_at IS NULL"
            " ORDER BY r.started_at",
            (graph,),
        )
    except Exception as exc:  # noqa: BLE001 — 표가 없어도 화면은 떠야 한다
        _warn("state", exc, graph=graph)
        return empty
    return classify(rows, now=now)


def classify(rows: Iterable[dict[str, Any]], *, now: Optional[datetime] = None) -> dict[str, Any]:
    """박동이 늙은 것은 중단이다. **문턱은 여기 한 곳에만 있다.**"""
    at = now or datetime.now(timezone.utc)
    running: list[dict[str, Any]] = []
    interrupted: list[dict[str, Any]] = []
    for row in rows:
        seen = row.get("beat_at")
        if seen is None:
            interrupted.append(_view(row))
            continue
        age = (at - seen).total_seconds()
        (interrupted if age > ABSENT_GRACE_SECONDS else running).append(_view(row))
    return {"running": running, "interrupted": interrupted}


def interrupted_session_ids(graph: Optional[str]) -> set[str]:
    """중단된 적재가 쓰다 만 **세션 아이디**들.

    `BpmSession` 에는 완료 표시가 없어서, 반쯤 쓰인 판이 완주한 판과 목록에서
    구별되지 않는다(`ontology/neo4j_ops.py` 의 세션 목록은 건수만 센다). 그 구별을
    여기서 돌려준다 — 세션을 **지우지는 않는다**. 반쯤이라도 그게 그 프로젝트에
    남은 전부일 수 있고, 지우는 판단은 사람의 것이다.
    """
    st = state(graph)
    return {r["sessionId"] for r in st["interrupted"] if r.get("sessionId")}


def acknowledge(run_id: str, uid: str, *, graph: Optional[str] = None) -> bool:
    """사람이 경고를 닫는다. **graph 를 함께 걸러** 남의 프로젝트는 못 닫는다."""
    if not run_id:
        return False
    sql = ("UPDATE public.app_ingestion_runs SET acked_at = now(), acked_by = %s "
           "WHERE run_id = %s AND acked_at IS NULL")
    params: tuple[Any, ...] = (uid or None, run_id)
    if graph:
        sql += " AND graph = %s"
        params = params + (graph,)
    try:
        return pg.execute(sql, params) > 0
    except Exception as exc:  # noqa: BLE001
        _warn("acknowledge", exc, run_id=run_id)
        return False
