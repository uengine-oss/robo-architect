# -*- coding: utf-8 -*-
"""적재 기록 — **지우기 전에 적고, 박동으로 생존을 재고, 중단만 경고한다**.

## 왜 이 검사가 있나

적재는 지우기로 시작하고 수 분이 걸린다. 그 사이 앱이 강제 종료되면 설계가 지워진
프로젝트만 남고, 그 사실을 아는 프로세스는 **이미 죽었다**. 그래서 재는 것은 셋이다 —

```
① 순서      기록이 **지우기보다 먼저** 일어난다. 거꾸로면 기록할 사람이 없다
② 문턱      박동이 늙은 것만 중단이다. 한 곳에서만 판정한다
③ 사유      사람이 멈춘 것·오류로 끝난 것은 **중단이 아니다** (화면이 이미 말했다)
```

그리고 **기록이 적재를 못 세운다** — Postgres 가 없어도 적재는 돈다.
"""

from __future__ import annotations

import threading
from datetime import datetime, timedelta, timezone

import pytest

from api.features.ingestion import runs


def _row(**kw):
    base = {
        "run_id": "s1-x", "graph": "prj_a", "session_id": "s1", "uid": "u1",
        "kind": "hybrid", "status": "running", "started_at": None,
        "beat_at": datetime.now(timezone.utc), "value": {}, "who": "홍길동",
    }
    base.update(kw)
    return base


# ── ② 문턱 ────────────────────────────────────────────────────────────────

def test_박동이_싱싱하면_돌고_있는_것이다():
    now = datetime.now(timezone.utc)
    out = runs.classify([_row(beat_at=now - timedelta(seconds=5))], now=now)
    assert len(out["running"]) == 1 and not out["interrupted"]


def test_박동이_늙으면_중단이다():
    now = datetime.now(timezone.utc)
    old = now - timedelta(seconds=runs.ABSENT_GRACE_SECONDS + 1)
    out = runs.classify([_row(beat_at=old)], now=now)
    assert not out["running"]
    assert out["interrupted"][0]["displayName"] == "홍길동"


def test_박동이_없으면_중단이다():
    out = runs.classify([_row(beat_at=None)])
    assert len(out["interrupted"]) == 1


def test_지워진_건수를_그대로_돌려준다():
    """경고가 "무엇이 없어졌는지" 를 말하는 근거다. 지운 뒤에는 셀 수 없다."""
    row = _row(value={"wiped": {"UserStory": 33}, "wipedTotal": 33,
                      "snapshots": ["k1"], "host": "PC-A"})
    view = runs.classify([_row(beat_at=None, value=row["value"])])["interrupted"][0]
    assert view["wiped"] == {"UserStory": 33}
    assert view["wipedTotal"] == 33 and view["snapshots"] == ["k1"]
    assert view["host"] == "PC-A"


# ── 기록이 적재를 못 세운다 ─────────────────────────────────────────────────

def test_표가_없어도_적재는_돈다(monkeypatch: pytest.MonkeyPatch):
    def _boom(*a, **k):
        raise RuntimeError("no postgres")

    monkeypatch.setattr(runs.pg, "execute", _boom)
    monkeypatch.setattr(runs, "ensure_schema", _boom)
    assert runs.start("prj_a", "s1") is None          # 예외가 올라오지 않는다
    runs.beat("s1-x")                                  # 조용히 넘어가지 않고 WARN
    runs.finish("s1-x", "complete")


def test_상태를_못_읽으면_빈_것으로_본다(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(runs.pg, "query", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("x")))
    assert runs.state("prj_a") == {"running": [], "interrupted": []}


def test_프로젝트를_모르면_아무것도_안_적는다(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(runs, "design_database", lambda: None)
    assert runs.start(None, "s1") is None


# ── ③ 사유 ────────────────────────────────────────────────────────────────

def test_닫는_것은_돌고_있는_행만이다(monkeypatch: pytest.MonkeyPatch):
    """두 번 닫아도 **처음 사유가 남는다** — SQL 이 `running` 만 고른다."""
    seen: list[tuple] = []
    monkeypatch.setattr(runs.pg, "execute", lambda sql, params=None: seen.append((sql, params)) or 1)
    runs.finish("r1", "cancelled")
    sql, params = seen[-1]
    assert "status = 'running'" in sql
    assert params[0] == "cancelled"


def test_모르는_사유는_완료로_접는다(monkeypatch: pytest.MonkeyPatch):
    seen: list[tuple] = []
    monkeypatch.setattr(runs.pg, "execute", lambda sql, params=None: seen.append((sql, params)) or 1)
    runs.finish("r1", "뭔가이상한값")
    assert seen[-1][1][0] == "complete"


def test_시작은_running_과_건수를_같이_적는다(monkeypatch: pytest.MonkeyPatch):
    seen: list[tuple] = []
    monkeypatch.setattr(runs, "ensure_schema", lambda: None)
    monkeypatch.setattr(runs.pg, "execute", lambda sql, params=None: seen.append((sql, params)) or 1)
    rid = runs.start("prj_a", "s1", uid="u1", counts={"UserStory": 3})
    assert rid and rid.startswith("s1-")
    sql, params = seen[0]
    assert "INSERT INTO public.app_ingestion_runs" in sql and "'running'" in sql
    assert '"wipedTotal": 3' in params[-1]


def test_남의_프로젝트_경고는_못_닫는다(monkeypatch: pytest.MonkeyPatch):
    seen: list[tuple] = []
    monkeypatch.setattr(runs.pg, "execute", lambda sql, params=None: seen.append((sql, params)) or 1)
    runs.acknowledge("r1", "u1", graph="prj_a")
    sql, params = seen[-1]
    assert "AND graph = %s" in sql and params[-1] == "prj_a"


# ── 반쯤 쓰인 세션 ─────────────────────────────────────────────────────────

def test_중단된_적재의_세션을_가려낸다(monkeypatch: pytest.MonkeyPatch):
    """`BpmSession` 에는 완료 표시가 없다. 그 구별을 적재 기록이 대신 한다."""
    now = datetime.now(timezone.utc)
    old_beat = now - timedelta(seconds=runs.ABSENT_GRACE_SECONDS + 5)
    monkeypatch.setattr(runs.pg, "query", lambda *a, **k: [
        _row(session_id="half", beat_at=old_beat),
        _row(session_id="alive", beat_at=now),
    ])
    assert runs.interrupted_session_ids("prj_a") == {"half"}


# ── 박동 ──────────────────────────────────────────────────────────────────

def test_박동은_멈추라고_할_때까지_뛴다():
    beats: list[int] = []
    stop = threading.Event()

    def tick():
        beats.append(1)
        if len(beats) >= 3:
            stop.set()

    runs._beat_loop(tick, stop, 0.0)
    assert len(beats) == 3


def test_박동_스레드는_프로세스를_붙잡지_않는다(monkeypatch: pytest.MonkeyPatch):
    """데몬이 아니면 백엔드 종료가 적재 스레드를 기다린다."""
    monkeypatch.setattr(runs, "beat", lambda rid: None)
    hb = runs.heartbeat("r1", interval=0.01)
    try:
        assert hb.thread is not None and hb.thread.daemon
    finally:
        hb.stop()


def test_기록이_없으면_박동도_없다():
    hb = runs.heartbeat(None)
    assert hb.thread is None
