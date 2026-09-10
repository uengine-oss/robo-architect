"""요청의 신원으로 그래프 연결 자격을 고른다.

**여기가 실제 구멍이었다.** 지금까지 연결은 이렇게 정해졌다.

```
X-Neo4j-* 헤더가 있으면   그 자격으로 붙는다      (Electron)
없으면                    .env 로 붙는다          (브라우저) ← 소유자 자격이다
```

브라우저 경로에는 헤더가 없으므로 `.env` 의 `dev` 로 붙는다. `dev` 는 모든 graph
를 볼 수 있는 소유자다. 로그인해서 누구인지 알아도 **연결은 여전히 소유자**라,
graph 격리가 요청 경로에서 성립하지 않는다.

세션이 있으면 그 사람의 role 로 붙게 바꾼다.

```
role       p_<사번>
비밀번호    HMAC 로 유도 (api/features/projects/roles.py)
graph      요청이 고른 프로젝트
```

**경계는 Postgres 다.** 권한이 없으면 그 role 로는 애초에 읽히지 않는다. 아래의
등급 확인은 보안 장치가 아니라 **말이 통하는 오류**를 주기 위한 것이고, 그래서
짧게 캐시해도 안전하다 — 캐시가 낡아도 Postgres 가 거부한다.

## 등급으로 가른다

범위를 지정한 role 은 **자기 graph 에도 라벨을 만들지 못한다.** 라벨 생성이
`og_catalog.type` 삽입과 `og_data` 스키마 CREATE 를 요구하는데 `og_grant` 는
범위를 지정하면 그 둘을 주지 않는다(엔진 `catalog/privileges.rs`, "스키마 변경은
admin 쪽 선에 남긴다"). 우리 파이프라인은 인제스천마다 라벨을 새로 만들므로,
쓰는 사람을 그 role 에 묶으면 인제스천이 통째로 막힌다.

그래서 이렇게 가른다.

```
read 등급        그 사람 role 로 붙는다      graph 격리와 읽기 전용을 DB 가 보장
write · admin    소유자 자격으로 붙는다      graph 는 앱이 고정, 등급은 앱이 확인
권한 없음         403
```

**뒤쪽은 DB 보장이 없다.** 앱이 통과시키면 쓸 수 있다. 다만 그 사람은 이미 이
프로젝트에 쓰기 권한이 있다고 확인된 사람이고, 남의 프로젝트를 고르면 여기까지
오지 못한다. 데이터가 새는 쪽(읽기)은 DB 가 막는다.

> 이 절충은 엔진이 범위 지정 role 에게 자기 graph 의 스키마를 만들게 해 주면
> 사라진다. `og_data` 스키마 CREATE 를 graph 단위로 좁히는 설계가 필요해 별건이다.

기본은 꺼짐(`AUTH_BIND_CONNECTION`)이다. 켜는 순간 사용자에게 권한이 없는 graph
는 안 보이게 되므로, 프로젝트 배선이 끝난 뒤에 켠다.
"""

from __future__ import annotations

import os
import time
from typing import Optional

from api.features.auth.tokens import TokenError, verify_token
from api.features.projects import roles, store as projects
from api.platform import pg
from api.platform.neo4j_context import Neo4jOverride
from api.platform.observability.smart_logger import SmartLogger

__all__ = ["binding_enabled", "resolve_for_request", "BindingDenied", "invalidate",
           "needs_graph", "NO_GRAPH_PREFIXES"]

# graph 를 안 쓰는 경로. 이것들은 Postgres 로만 간다.
#
# **여기 없으면 새 사용자가 아무것도 시작할 수 없다.** 프로젝트가 하나도 없는
# 사람은 `X-Project-Graph` 를 보낼 수 없고, 그러면 바인딩이 `.env` 의 graph 로
# 떨어져 403 이 난다 — 첫 프로젝트를 만들러 가는 길 자체가 막힌다. 실제로
# 두 번째 계정을 만들자마자 이 막다른 길에 걸렸다.
NO_GRAPH_PREFIXES = (
    "/api/auth",       # 로그인·세션
    "/api/accounts",   # 사용자 관리
    "/api/projects",   # 프로젝트 목록·생성·공유 — 전부 Postgres 다
    "/api/health",
    "/docs", "/openapi.json", "/redoc",
)


def needs_graph(path: str) -> bool:
    """이 경로가 graph 연결을 필요로 하는가."""
    return not str(path or "").startswith(NO_GRAPH_PREFIXES)

_TRUE = ("1", "true", "yes", "on")
_CACHE: dict[tuple[str, str], tuple[float, Optional[str]]] = {}


class BindingDenied(Exception):
    """이 사용자는 이 graph 에 권한이 없다.

    **"고르지 않았다"와 "권한이 없다"를 가른다.** 둘을 같은 오류로 내보내면 화면이
    구별할 수 없고, 실제로 프로젝트를 안 고른 사용자에게 "서버 연결 실패"라고
    보여 줬다 — 백엔드가 멀쩡한데 죽은 것처럼 보인다.
    """

    def __init__(self, graph: str, *, selected: bool = True) -> None:
        if selected:
            super().__init__(f"이 프로젝트에 접근할 권한이 없습니다: {graph}")
        else:
            super().__init__("프로젝트를 먼저 고르세요.")
        self.graph = graph
        self.selected = selected

    @property
    def code(self) -> str:
        return "PROJECT_FORBIDDEN" if self.selected else "PROJECT_NOT_SELECTED"


def binding_enabled() -> bool:
    return (os.environ.get("AUTH_BIND_CONNECTION") or "").strip().lower() in _TRUE


def _cache_ttl() -> float:
    try:
        return float(os.environ.get("AUTH_BIND_CACHE_SECONDS", "15"))
    except ValueError:
        return 15.0


def invalidate(role: str | None = None, graph: str | None = None) -> None:
    """등급이 바뀌면 캐시를 버린다. 인자가 없으면 전부."""
    if role is None or graph is None:
        _CACHE.clear()
        return
    _CACHE.pop((role, graph), None)


def _level(role: str, graph: str) -> Optional[str]:
    key = (role, graph)
    hit = _CACHE.get(key)
    now = time.monotonic()
    if hit and hit[0] > now:
        return hit[1]
    rows = pg.query(
        "SELECT level FROM og_catalog.grantee WHERE role = %s AND graph = %s",
        (role, graph),
    )
    level = rows[0]["level"] if rows else None
    _CACHE[key] = (now + _cache_ttl(), level)
    return level


def _claims(headers) -> Optional[dict]:
    raw = headers.get("authorization") or ""
    token = raw[7:].strip() if raw[:7].lower() == "bearer " else None
    if not token:
        return None
    try:
        return verify_token(token)
    except TokenError:
        return None


def resolve_for_request(headers, fallback_database: Optional[str]) -> Optional[Neo4jOverride]:
    """이 요청이 쓸 연결. 세션이 없으면 `None`(= 지금까지의 동작).

    세션이 있으면 **클라이언트가 보낸 자격은 무시한다.** 그걸 존중하면 헤더를
    지어내서 소유자 자격으로 붙는 길이 그대로 남는다 — 막으려던 것이 그것이다.
    """
    if not binding_enabled():
        return None
    claims = _claims(headers)
    if not claims:
        return None

    uid = str(claims.get("sub") or "")
    if not uid:
        return None

    # 요청이 정한 것과 `.env` 폴백을 갈라 둔다 — 아래에서 오류 종류가 갈린다.
    asked = (headers.get("x-project-graph") or headers.get("x-neo4j-database") or "").strip()
    graph = asked or (fallback_database or "").strip()
    if not graph:
        raise BindingDenied("(프로젝트 없음)", selected=False)

    role = roles.role_name(uid)
    level = _level(role, graph)
    if level is None:
        if not asked:
            # 고르지 않아서 `.env` 로 떨어진 것뿐이다. 이 사람이 그 graph 에 권한이
            # 없는 건 당연하고, 잘못은 "권한"이 아니라 "아직 안 골랐다"에 있다.
            SmartLogger.log(
                "INFO", "프로젝트를 고르지 않은 요청.",
                category="auth.binding.unselected",
                params={"uid": uid, "fallback": graph},
            )
            raise BindingDenied(graph, selected=False)
        SmartLogger.log(
            "WARN", "권한 없는 graph 접근을 막았다.",
            category="auth.binding.denied",
            params={"uid": uid, "role": role, "graph": graph},
        )
        raise BindingDenied(graph)

    uri = os.environ.get("NEO4J_URI", "bolt://localhost:28687")
    # 설계와 분석은 한 세트다. 프로젝트가 정한 분석 graph 를 함께 실어야
    # 추적성이 이 프로젝트의 분석을 본다.
    analyzer = (projects.get_project(graph) or {}).get("analyzerGraph")
    if level == "read":
        # 읽기만 하는 사람은 그 사람 role 로 붙는다 — graph 격리와 읽기 전용을
        # Postgres 가 강제한다. 앱에 결함이 있어도 남의 데이터가 나오지 않는다.
        return Neo4jOverride(uri=uri, user=role, password=roles.role_password(uid),
                             database=graph, analyzer_database=analyzer,
                             analyzer_pinned=True)

    # 쓰는 사람은 소유자 자격으로 붙는다. 범위 지정 role 로는 라벨을 못 만들어
    # 인제스천이 통째로 막히기 때문이다. graph 는 여기서 고정하므로 클라이언트가
    # 다른 곳을 가리킬 수는 없다.
    return Neo4jOverride(
        uri=uri,
        user=os.environ.get("NEO4J_USER", "dev"),
        password=os.environ.get("NEO4J_PASSWORD", ""),
        database=graph,
        analyzer_database=analyzer,
        # 프로젝트가 정했다 — 비어 있으면 "분석 없음"이지 `.env` 가 아니다.
        analyzer_pinned=True,
    )
