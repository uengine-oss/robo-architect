"""같은 읽기가 동시에 몰리면 한 번만 돈다(single-flight).

남이 쓰면 보고 있던 창이 모두 같은 트리를 **동시에** 다시 읽는다(collab `changed` →
`robo:data-changed` → navigator refreshAll). 창 20개면 같은 조회가 20번이다 — 포스코 로컬 측정
(2026-11-19): 5초마다 쓰기 한 번에 다시 읽기 p95 933ms.

여기서는 **결과를 남겨 두지 않는다**(캐시가 아니다). 같은 열쇠의 조회가 돌고 있는 동안 들어온
요청만 그 결과를 같이 받는다 — 끝나면 바로 잊는다. 그래서 낡은 값을 오래 주는 일이 없다.
돌려준 값은 여럿이 나눠 가지므로 **받은 쪽이 고치면 안 된다**(라우트는 그대로 직렬화만 한다).

스레드에서 부른다(동기 라우트는 FastAPI 스레드풀에서 돈다).
"""

from __future__ import annotations

import threading
from concurrent.futures import Future
from typing import Any, Callable, Hashable, TypeVar

T = TypeVar("T")

_lock = threading.Lock()
_inflight: dict[Hashable, Future] = {}


def run(key: Hashable, fn: Callable[[], T]) -> T:
    with _lock:
        fut = _inflight.get(key)
        leader = fut is None
        if leader:
            fut = Future()
            _inflight[key] = fut
    if not leader:
        return fut.result()
    try:
        result = fn()
    except BaseException as exc:
        fut.set_exception(exc)
        raise
    else:
        fut.set_result(result)
        return result
    finally:
        with _lock:
            _inflight.pop(key, None)


def graph_key(*parts: Any) -> tuple:
    """현재 요청이 보는 그래프(연결 주소 + 설계 graph)를 앞에 붙인 열쇠."""
    from api.platform.neo4j import design_database
    from api.platform.neo4j_context import get_override

    override = get_override()
    return (override.uri if override is not None else None, design_database(), *parts)
