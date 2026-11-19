"""같은 열쇠의 동시 조회는 한 번만 돌고, 끝나면 잊는다."""

from __future__ import annotations

import threading
import time

import pytest

from api.platform import singleflight


def test_concurrent_same_key_runs_once_and_shares_result():
    calls = []
    gate = threading.Event()

    def work():
        calls.append(1)
        gate.wait(2)
        return {"v": len(calls)}

    out = []
    threads = [threading.Thread(target=lambda: out.append(singleflight.run("k", work))) for _ in range(8)]
    for t in threads:
        t.start()
    time.sleep(0.1)
    gate.set()
    for t in threads:
        t.join(2)
    assert calls == [1] and len(out) == 8 and all(o == {"v": 1} for o in out)
    # 끝나면 잊는다 — 다음 호출은 새로 돈다(캐시가 아니다)
    assert singleflight.run("k", lambda: "again") == "again"


def test_failure_reaches_every_waiter_and_is_forgotten():
    gate = threading.Event()

    def boom():
        gate.wait(2)
        raise RuntimeError("db down")

    errors = []

    def call():
        try:
            singleflight.run("e", boom)
        except RuntimeError as exc:
            errors.append(str(exc))

    threads = [threading.Thread(target=call) for _ in range(3)]
    for t in threads:
        t.start()
    time.sleep(0.1)
    gate.set()
    for t in threads:
        t.join(2)
    assert errors == ["db down"] * 3
    assert singleflight.run("e", lambda: 1) == 1


def test_different_keys_do_not_share():
    assert singleflight.run(("g1", "x"), lambda: 1) == 1
    assert singleflight.run(("g2", "x"), lambda: 2) == 2
