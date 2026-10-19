"""라우터에 **실제로 등록된 경로**를 꺼낸다 — 중첩된 라우터까지 내려간다.

왜 필요한가
-----------
`{r.path for r in router.routes}` 는 **묶음 라우터에서 더는 통하지 않는다.**
2026-10-19 에 FastAPI 0.127 → 0.146(starlette 0.50 → 1.9)으로 올리니
`include_router` 가 자식 경로를 부모에 **펼쳐 넣지 않고** `_IncludedRouter` 래퍼를
하나 꽂는다. 그 래퍼에는 `.path` 가 없어서 검사 둘이
`AttributeError: '_IncludedRouter' object has no attribute 'path'` 로 죽었다
(`test_chat_edit.py` · `test_deletion_recovery.py` · done14 §287).

**제품은 멀쩡했다.** 같은 판에서 `TestClient` 로 네 경로를 두드려 확인했다 —
맞는 메서드는 핸들러까지 가고(422·404) 반대 메서드는 **405** 가 온다. 405 는
"경로는 있는데 그 메서드가 아니다" 라는 뜻이니 **등록의 증거**다. 즉 깨진 것은
**내부 표현을 들여다본 검사의 가정**이었다.

그래서 검사를 FastAPI 판에 안 묶이게 만든다 — `.routes` 를 **재귀로** 걸어서
`.path` 를 가진 것만 모은다. 펼쳐 주던 옛 판에서도 같은 답이 나온다.

쓰는 법
-------
    from api.tests.route_paths import route_paths, route_methods

    assert "/api/requirements/deletion-records" in route_paths(router)
    assert ("/api/requirements/bounded-context", "DELETE") in route_methods(router)

⚠ `prefix` 는 각 라우터가 자기 경로에 이미 반영해 두므로 여기서 더하지 않는다 —
더하면 옛 판과 답이 달라진다.
"""

from __future__ import annotations

from typing import Any, Iterator


def _expand(route: Any) -> Iterator[Any]:
    """라우트 하나를 **경로를 가진 것들**로 펼친다.

    FastAPI 0.146 의 `_IncludedRouter` 는 `.path` 도 `.routes` 도 없다. 대신
    `effective_candidates()` 가 `_EffectiveRouteContext` 를 내는데, 그것의 `.path` 는
    **접두사가 이미 붙은 최종 경로**다(`/api/requirements/tree`). 우리가 접두사를
    조립하지 않고 **FastAPI 가 계산한 값**을 쓰는 것이 맞다 — 조립하면 그쪽 규칙이
    바뀔 때 또 어긋난다.
    """
    cands = getattr(route, "effective_candidates", None)
    if callable(cands):
        for c in cands():
            yield from _expand(c)
        low = getattr(route, "effective_low_priority_routes", None)
        if callable(low):
            for c in low():
                yield from _expand(c)
        return

    if getattr(route, "path", None) is not None:
        yield route

    # 옛 판(펼쳐 넣던 쪽)과 Mount 류를 위해 자식도 걷는다.
    inner = getattr(route, "routes", None)
    if inner:
        for r in inner:
            yield from _expand(r)


def iter_routes(router: Any) -> Iterator[Any]:
    """`.path` 를 가진 라우트를 **깊이 우선**으로 모두 낸다."""
    for route in getattr(router, "routes", ()) or ():
        yield from _expand(route)


def route_paths(router: Any) -> set[str]:
    """등록된 경로의 집합."""
    return {r.path for r in iter_routes(router)}


def route_methods(router: Any) -> set[tuple[str, str]]:
    """`(경로, 메서드)` 쌍의 집합. 메서드가 없는 라우트는 건너뛴다."""
    return {
        (r.path, m)
        for r in iter_routes(router)
        for m in (getattr(r, "methods", None) or ())
    }
