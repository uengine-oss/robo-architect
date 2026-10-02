# -*- coding: utf-8 -*-
"""적재 기록은 **지우기보다 먼저** 일어난다.

## 왜 순서가 전부인가

하이브리드 적재의 첫 일은 `clear_all_hybrid_workspace()` — 그 프로젝트의 설계를
통째로 지운다. 그 다음이 외부 추출기이고 **여기가 수 분**이다. 이 사이에 앱이 강제
종료되면, 남는 것은 **설계가 지워진 프로젝트**이고 무슨 일이 있었는지 말해 줄
프로세스는 이미 죽었다(`_sessions` 는 그 프로세스의 메모리다).

그래서 기록이 지우기보다 **한 줄이라도 늦으면** 장치 전체가 뜻이 없다. 늦게 적는
코드도 평소에는 멀쩡히 돌기 때문에, 이 순서는 **검사로 못 박아야** 지켜진다.

같이 재는 것 —

```
건수      지우기 전에 센 값이 기록에 들어간다 (지운 뒤에는 셀 수 없다)
보관      `capture_before_replace` 가 돌려준 키를 그대로 적는다.
          **빈 목록이면 되찾을 길이 없다는 뜻**이고, 경고가 그렇게 말해야 한다
오류      워크플로가 깨지면 `error` 로 닫는다 — 중단(경고)이 아니다
박동      어떻게 끝나든 스레드를 세운다
```
"""

from __future__ import annotations

import asyncio

import pytest

from api.features.ingestion.hybrid import hybrid_workflow_runner as mod


class _Recorder:
    """러너가 무엇을 **어떤 순서로** 했는지 본다."""

    def __init__(self) -> None:
        self.order: list[str] = []
        self.started: dict = {}
        self.noted: dict = {}
        self.finished: list[tuple[str, str]] = []
        self.stopped = False

    # ── runs 모듈 대역 ──
    def start(self, graph, session_id, *, uid=None, kind="hybrid", counts=None):
        self.order.append("record")
        self.started = {"graph": graph, "session_id": session_id, "uid": uid,
                        "kind": kind, "counts": counts}
        return "run-1"

    def heartbeat(self, run_id, interval=10):
        self.order.append("beat-start")
        rec = self

        class _HB:
            def stop(self_inner):
                rec.stopped = True
                rec.order.append("beat-stop")

        return _HB()

    def note(self, run_id, **fields):
        self.noted.update(fields)

    def finish(self, run_id, status="complete", message=""):
        # 두 번째 닫기는 DB 가 무시한다(`status = 'running'` 조건). 여기서는 호출만 본다.
        self.finished.append((run_id, status))


@pytest.fixture
def rec(monkeypatch: pytest.MonkeyPatch) -> _Recorder:
    r = _Recorder()
    monkeypatch.setattr(mod, "runs", r)
    monkeypatch.setattr(mod, "safe_counts", lambda: {"UserStory": 33, "BpmTask": 29})
    monkeypatch.setattr(mod, "capture_before_replace",
                        lambda reason="replaced", counts=None: (
                            r.order.append("snapshot"),
                            [{"snapshotKey": "snap-1"}],
                        )[1])
    monkeypatch.setattr(mod, "clear_all_hybrid_workspace", lambda: r.order.append("wipe"))
    monkeypatch.setattr(mod, "clear_event_storming_nodes", lambda client, sid="": None)
    monkeypatch.setattr(mod, "get_neo4j_client", lambda: object())

    async def _die(**kwargs):
        # 외부 추출기 자리. 실제로는 여기가 수 분이고, 강제 종료가 여기서 일어난다.
        raise RuntimeError("추출기가 죽었다")

    monkeypatch.setattr(mod, "extract_bpm_skeleton", _die)
    return r


def _run(**kw) -> list:
    async def _go():
        return [e async for e in mod.run_hybrid_workflow("sess-1", "문서 본문", **kw)]

    return asyncio.run(_go())


def test_기록이_지우기보다_먼저다(rec: _Recorder):
    _run(uid="u1")
    assert rec.order.index("record") < rec.order.index("wipe")
    # 보관도 지우기 전이다 — 원래 그랬고, 기록이 그 사이에 끼어도 그대로여야 한다.
    assert rec.order.index("snapshot") < rec.order.index("wipe")
    assert rec.order.index("record") < rec.order.index("snapshot")


def test_지워질_건수와_사람을_같이_적는다(rec: _Recorder):
    _run(uid="u1")
    assert rec.started["counts"] == {"UserStory": 33, "BpmTask": 29}
    assert rec.started["uid"] == "u1"
    assert rec.started["session_id"] == "sess-1"


def test_보관한_키를_기록에_남긴다(rec: _Recorder):
    """빈 목록이면 **되찾을 길이 없다는 사실**이 그대로 남아야 한다."""
    _run()
    assert rec.noted["snapshots"] == ["snap-1"]


def test_워크플로가_깨지면_오류로_닫는다(rec: _Recorder):
    """오류는 중단이 아니다 — 화면이 이 자리에서 말을 한다."""
    events = _run()
    assert rec.finished[0][1] == "error"
    assert "오류" in events[-1].message


def test_어떻게_끝나든_박동을_세운다(rec: _Recorder):
    _run()
    assert rec.stopped


def test_박동은_지우기_전에_시작한다(rec: _Recorder):
    """지우기와 추출 사이에서 죽는 것이 가장 나쁜 경우다. 그 구간이 비면 안 된다."""
    _run()
    assert rec.order.index("beat-start") < rec.order.index("wipe")
