"""쓰기가 지나는 목 — 여기서 "이 프로젝트가 바뀌었다"를 표시한다.

신호원을 저장소가 아니라 **앱 계층**에 두는 이유는 §17-1 에 적었다. 요약하면,
`og_audit` 트리거는 "저장소가 무엇을 실행했나"이지 "이 프로젝트가 바뀌었다"가
아니고, 앱이 모르는 경로까지 울린다. 우리는 **모든 쓰기가 API 를 지난다.**

그래서 목은 하나다 — 요청이 성공적으로 끝나는 자리. 쓰기 코드를 찾아다니며
호출을 심으면 **반드시 하나를 빠뜨리고**, 빠뜨린 것은 조용하다.

## 이 목이 못 잡는 것

진행 표시가 SSE 인 긴 작업(인제스천·승격)은 **GET 으로 열려서 그 안에서 쓴다.**
요청 메서드로는 안 잡힌다. 그런 자리는 작업이 끝나는 지점에서 `store.bump` 를
직접 부른다 — 목록은 `router.py` 옆 주석에 둔다.
"""

from __future__ import annotations

from typing import Optional

from api.features.collab import store

# 이 경로들은 프로젝트 graph 를 안 건드린다(Postgres 직결·진단·스트림 자신).
# 여기서 판을 올리면 스트림이 자기 심장박동에 반응해 무한히 울린다.
_SKIP_PREFIXES = (
    "/api/collab/",
    "/api/auth/",
    "/api/accounts/",
    "/api/health",
)

_WRITE_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})


def graph_of(headers, bound) -> Optional[str]:
    """이 요청이 쓴 graph. 세션이 정한 것이 헤더보다 세다.

    바인딩이 켜져 있으면 클라이언트가 보낸 값은 이미 무시됐다 — 알림도 같은
    값을 따라가야 한다. 안 그러면 **바뀐 프로젝트와 울린 프로젝트가 다르다.**
    """
    if bound is not None and getattr(bound, "database", None):
        return bound.database
    return (headers.get("x-project-graph") or headers.get("x-neo4j-database") or "").strip() or None


def should_notify(method: str, path: str, status_code: int) -> bool:
    if method.upper() not in _WRITE_METHODS:
        return False
    # 실패한 쓰기는 아무것도 안 바꿨다. 울리면 모두가 헛되이 다시 읽는다.
    if status_code >= 400:
        return False
    return not path.startswith(_SKIP_PREFIXES)


def after_request(headers, bound, method: str, path: str, status_code: int,
                  actor_uid: str | None = None) -> None:
    """응답이 정해진 뒤 1회. **던지지 않는다** — 알림 때문에 쓰기가 깨지면 안 된다."""
    if not should_notify(method, path, status_code):
        return
    try:
        graph = graph_of(headers, bound)
        if not graph:
            return
        store.bump(graph, actor_uid=actor_uid, reason=f"{method} {path}"[:64])
    except Exception:
        # `store.bump` 안에도 가드가 있지만, 표가 아예 없거나 헤더가 예상 밖일
        # 때는 그 앞에서 터진다. 여기서 새면 **성공한 쓰기가 500 으로 뒤집힌다.**
        return
