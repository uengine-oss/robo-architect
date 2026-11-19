"""연결과 떨어져 도는 스트림 작업 — 화면이 끊겼다 다시 붙어도 작업은 한 번만 돈다.

Intent 분해처럼 GET 스트림이 작업 시작을 겸하는 경우, 예전에는 작업이 응답 생성기 안에서
돌아서 연결이 끊기면(창 새로 고침 · 셸 탭 · 네트워크) 작업도 같이 취소됐고, 다시 붙으면
처음부터 다시 돌았다(lite L-4, 2026-11-19).

여기서는 작업을 따로 된 task 로 돌리고 나온 이벤트를 쌓아 둔다. 붙는 쪽은 처음부터 다시 받고
(replay) 이어서 따라간다. 같은 키로 돌고 있는 작업이 있으면 새로 시작하지 않고 그 작업에 붙는다.
끝난 작업은 잠시(`KEEP_SECONDS`) 남겨 둔다 — 끊긴 사이에 끝났어도 붙는 쪽이 결과(done/error)를 받는다.

프로세스 안 상태다(uvicorn 한 프로세스 전제 — workers 를 올리면 밖으로 빼야 한다).
"""

from __future__ import annotations

import asyncio
import time
from typing import AsyncGenerator, AsyncIterator, Callable, Optional

Event = tuple[str, dict]

KEEP_SECONDS = 600
MAX_EVENTS = 5000


class DetachedRun:
    def __init__(self, key: str, factory: Callable[[], AsyncIterator[Event]]):
        self.key = key
        self.events: list[Event] = []
        self.dropped = 0
        self.finished = False
        self.cancelled = False
        self.started_at = time.monotonic()
        self.finished_at: Optional[float] = None
        self._changed = asyncio.Event()
        self.task = asyncio.create_task(self._pump(factory), name=f"detached:{key}")

    async def _pump(self, factory: Callable[[], AsyncIterator[Event]]) -> None:
        try:
            async for event in factory():
                self._append(event)
        except asyncio.CancelledError:
            self.cancelled = True
            self._append(("error", {"code": "CANCELLED", "message": "작업을 멈췄습니다."}))
        except Exception as exc:  # noqa: BLE001 — 붙은 쪽이 error 이벤트로 알게 한다
            self._append(("error", {"code": "STREAM_FAILED", "message": str(exc)[:500]}))
        finally:
            self.finished = True
            self.finished_at = time.monotonic()
            self._notify()

    def _append(self, event: Event) -> None:
        self.events.append(event)
        if len(self.events) > MAX_EVENTS:
            # 오래된 log_line 부터 버린다 — 결과 이벤트는 남긴다.
            for i, (name, _) in enumerate(self.events):
                if name == "log_line":
                    del self.events[i]
                    self.dropped += 1
                    break
        self._notify()

    def _notify(self) -> None:
        changed, self._changed = self._changed, asyncio.Event()
        changed.set()

    async def follow(self) -> AsyncGenerator[Event, None]:
        """처음부터 다시 주고, 끝날 때까지 따라간다. 이 생성기가 취소돼도 작업은 계속 돈다."""
        sent = 0
        while True:
            changed = self._changed  # 비우기 전에 잡아 둔다 — 사이에 들어온 이벤트를 놓치지 않는다
            while sent < len(self.events):
                yield self.events[sent]
                sent += 1
            if self.finished:
                return
            await changed.wait()
            # 앞쪽 log_line 이 버려졌으면 위치가 당겨진다 — 넘친 만큼만 되돌린다
            sent = min(sent, len(self.events))

    def status(self) -> dict:
        return {
            "running": not self.finished,
            "finished": self.finished,
            "cancelled": self.cancelled,
            "events": len(self.events),
            "lastEvent": self.events[-1][0] if self.events else None,
        }


_RUNS: dict[str, DetachedRun] = {}


def intent_key(proposal_id: str) -> str:
    """Intent 분해의 키 — 스트림 시작·붙기·명확화 답변 뒤 재실행이 같은 작업을 가리킨다."""
    return f"intent:{proposal_id}"


def _sweep() -> None:
    now = time.monotonic()
    for key in [k for k, r in _RUNS.items() if r.finished and r.finished_at and now - r.finished_at > KEEP_SECONDS]:
        del _RUNS[key]


def start_or_join(key: str, factory: Callable[[], AsyncIterator[Event]]) -> DetachedRun:
    """돌고 있으면 그 작업을, 아니면(없거나 끝났으면) 새 작업을 돌려준다."""
    _sweep()
    run = _RUNS.get(key)
    if run is not None and not run.finished:
        return run
    run = DetachedRun(key, factory)
    _RUNS[key] = run
    return run


def get_run(key: str) -> Optional[DetachedRun]:
    """돌고 있거나 최근에 끝난 작업(없으면 None)."""
    _sweep()
    return _RUNS.get(key)


def cancel(key: str) -> bool:
    run = _RUNS.get(key)
    if run is None or run.finished:
        return False
    run.task.cancel()
    return True
