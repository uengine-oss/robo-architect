"""프로젝트 = graph.

기준 구현(local-msaez)은 프로젝트를 `definitions` 표의 한 행으로 두고 권한을 그
행 안의 JSON 으로 관리한다. 우리는 graph 하나가 프로젝트 하나이고 권한은
Postgres 가 강제한다 — 그쪽 인가는 앱 미들웨어에만 있어 DB 직결 경로가 통과한다
(`data-gateway/src/authz.js` 주석에 명시). 그 구멍을 들여오지 않으려는 것이다.

```
프로젝트 만들기   og_create_graph(graph) + og_grant(소유자 role, 'admin', graph)
공유              og_grant(role, level, graph)          한 줄
회수              og_revoke(role, graph)                한 줄
목록              og_catalog.grantee 에서 내 role 것만
```

graph 이름은 **사람이 지은 이름과 분리한다.** 프로젝트 이름은 한글일 수 있고
바뀔 수도 있는데, graph 이름은 식별자라 둘을 같게 두면 이름을 바꿀 수 없다.
`public.app_projects` 가 그 대응표다.
"""

from __future__ import annotations

import json
import re
import secrets
from datetime import datetime, timezone
from typing import Any, Optional

from api.features.projects import roles
from api.platform import pg

__all__ = [
    "ensure_schema", "create_project", "adopt_graph", "list_projects",
    "get_project", "share", "unshare", "members", "graph_exists",
    "LEVELS", "LEVEL_BY_ROLE_NAME",
]

# og_grant 가 받는 등급. 화면에서 쓰는 이름과의 대응을 한 곳에 둔다.
LEVELS = ("read", "write", "admin")
LEVEL_BY_ROLE_NAME = {"VIEWER": "read", "EDITOR": "write", "OWNER": "admin"}

_SCHEMA = """
CREATE TABLE IF NOT EXISTS public.app_projects (
    graph       TEXT PRIMARY KEY,
    value       JSONB NOT NULL DEFAULT '{}'::jsonb,
    owner_uid   TEXT GENERATED ALWAYS AS (value->>'ownerUid') STORED,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_app_projects_owner ON public.app_projects (owner_uid);
"""

_GRAPH_NAME = re.compile(r"^[a-z][a-z0-9_]{0,62}$")


def ensure_schema() -> None:
    with pg.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(_SCHEMA)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _new_graph_name() -> str:
    """graph 이름을 만든다.

    사람이 지은 이름에서 만들지 않는다 — 한글이면 남는 게 없고, 영문이라도
    겹치거나 예약어와 부딪친다. 이름은 `app_projects` 가 들고 있으면 된다.
    """
    for _ in range(8):
        candidate = "prj_" + secrets.token_hex(5)
        if not graph_exists(candidate):
            return candidate
    raise RuntimeError("graph 이름을 만들지 못했다")


def graph_exists(graph: str) -> bool:
    rows = pg.query("SELECT 1 FROM og_catalog.graph WHERE name = %s", (graph,))
    return bool(rows)


# ── 프로젝트 ──────────────────────────────────────────────────────────

def _row_to_project(row: dict[str, Any]) -> dict[str, Any]:
    value = dict(row.get("value") or {})
    out = {"graph": row["graph"], **value}
    if "level" in row:
        out["level"] = row["level"]
    return out


def create_project(name: str, owner_uid: str) -> dict[str, Any]:
    """graph 를 만들고 소유자에게 admin 을 준다.

    셋이 함께 되거나 함께 안 돼야 한다 — graph 만 생기고 권한이 없으면 아무도
    못 쓰는 graph 가 남고, 권한만 있고 graph 가 없으면 목록에 유령이 뜬다.
    """
    label = (name or "").strip()
    if not label:
        raise ValueError("프로젝트 이름이 비었다")
    if not owner_uid:
        raise ValueError("소유자를 알 수 없다")

    role = roles.ensure_role(owner_uid)
    graph = _new_graph_name()
    value = {
        "displayName": label,
        "ownerUid": owner_uid,
        "created": _now(),
    }
    with pg.connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT og_create_graph(%s)", (graph,))
            cur.execute("SELECT og_grant(%s, %s, %s)", (role, "admin", graph))
            cur.execute(
                "INSERT INTO public.app_projects (graph, value) VALUES (%s, %s::jsonb)",
                (graph, json.dumps(value, ensure_ascii=False)),
            )
    return {"graph": graph, **value, "level": "admin"}


def adopt_graph(graph: str, name: str, owner_uid: str) -> dict[str, Any]:
    """이미 있는 graph 를 프로젝트로 등록한다.

    전환 전부터 쓰던 `robo` 같은 graph 를 목록에 올리기 위한 길이다. **graph 를
    만들지 않는다** — 없는 이름을 주면 거부한다. 안 그러면 오타로 빈 프로젝트가
    생기고, 그건 지금 런처가 가진 문제와 같다.
    """
    if not _GRAPH_NAME.match(graph or ""):
        raise ValueError("graph 이름이 형식에 맞지 않는다")
    if not graph_exists(graph):
        raise ValueError(f"그런 graph 가 없다: {graph}")
    role = roles.ensure_role(owner_uid)
    value = {"displayName": (name or graph).strip(), "ownerUid": owner_uid,
             "created": _now(), "adopted": True}
    with pg.connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT og_grant(%s, %s, %s)", (role, "admin", graph))
            cur.execute(
                "INSERT INTO public.app_projects (graph, value) VALUES (%s, %s::jsonb) "
                "ON CONFLICT (graph) DO UPDATE SET value = EXCLUDED.value, updated_at = now()",
                (graph, json.dumps(value, ensure_ascii=False)),
            )
    return {"graph": graph, **value, "level": "admin"}


def list_projects(uid: str) -> list[dict[str, Any]]:
    """내가 접근할 수 있는 프로젝트만.

    `og_catalog.grantee` 와 조인한다 — 권한의 원천이 거기이므로, 별도 멤버십
    표를 두고 두 곳이 어긋나는 상황을 만들지 않는다.
    """
    role = roles.role_name(uid)
    rows = pg.query(
        "SELECT p.graph, p.value, g.level "
        "FROM public.app_projects p "
        "JOIN og_catalog.grantee g ON g.graph = p.graph "
        "WHERE g.role = %s "
        "ORDER BY p.created_at DESC",
        (role,),
    )
    return [_row_to_project(r) for r in rows]


def get_project(graph: str) -> Optional[dict[str, Any]]:
    rows = pg.query("SELECT graph, value FROM public.app_projects WHERE graph = %s", (graph,))
    return _row_to_project(rows[0]) if rows else None


def level_of(uid: str, graph: str) -> Optional[str]:
    """이 사용자가 이 프로젝트에 가진 등급. 없으면 None."""
    rows = pg.query(
        "SELECT level FROM og_catalog.grantee WHERE role = %s AND graph = %s",
        (roles.role_name(uid), graph),
    )
    return rows[0]["level"] if rows else None


def _invalidate_binding(role: str, graph: str) -> None:
    """등급이 바뀌면 연결 바인딩 캐시를 즉시 버린다.

    캐시가 낡아도 Postgres 가 막아 주지만, 회수 직후 사용자가 몇 초 동안 붙는
    것처럼 보이는 창을 없앤다. 순환 import 를 피하려 여기서 늦게 들여온다.
    """
    try:
        from api.platform.identity import connection_binding
        connection_binding.invalidate(role, graph)
    except Exception:  # noqa: BLE001 — 캐시 무효화 실패가 공유를 막으면 안 된다
        pass


# ── 공유 ─────────────────────────────────────────────────────────────

def share(graph: str, uid: str, level: str) -> dict[str, Any]:
    """초대 — 호출 한 줄이다. 별도 멤버십 표가 필요 없는 것이 이 구조의 이점이다."""
    if level not in LEVELS:
        raise ValueError(f"알 수 없는 등급: {level}")
    if not get_project(graph):
        raise ValueError(f"그런 프로젝트가 없다: {graph}")
    role = roles.ensure_role(uid)
    pg.query("SELECT og_grant(%s, %s, %s)", (role, level, graph))
    _invalidate_binding(role, graph)
    return {"graph": graph, "uid": uid, "role": role, "level": level}


def unshare(graph: str, uid: str) -> dict[str, Any]:
    """회수. 소유자는 뺄 수 없다 — 빼면 아무도 관리할 수 없는 프로젝트가 남는다."""
    project = get_project(graph)
    if not project:
        raise ValueError(f"그런 프로젝트가 없다: {graph}")
    if project.get("ownerUid") == uid:
        raise ValueError("소유자의 권한은 회수할 수 없다")
    role = roles.role_name(uid)
    pg.query("SELECT og_revoke(%s, %s)", (role, graph))
    _invalidate_binding(role, graph)
    return {"graph": graph, "uid": uid, "role": role}


def members(graph: str) -> list[dict[str, Any]]:
    """참여자 목록.

    role 이름은 사번을 정규화한 값이라 **되짚을 수 없다**(대문자·특수문자가
    사라진다). 그래서 사용자 표에서 role 이름을 다시 만들어 맞춘다. 참여자가
    적어 비용이 문제되지 않고, 역변환 규칙을 따로 유지하지 않아도 된다.
    """
    grants = pg.query(
        "SELECT role, level FROM og_catalog.grantee WHERE graph = %s ORDER BY role",
        (graph,),
    )
    users = pg.query("SELECT uid, value FROM public.app_users")
    by_role = {roles.role_name(u["uid"]): u for u in users if u.get("uid")}
    out = []
    for g in grants:
        u = by_role.get(g["role"])
        out.append({
            "role": g["role"],
            "level": g["level"],
            "uid": u["uid"] if u else None,
            "displayName": (u["value"] or {}).get("displayName") if u else None,
        })
    return out


def drop_project(graph: str) -> None:
    """프로젝트를 지운다 — **graph 안의 데이터가 함께 사라진다.**

    라우터에서 직접 부르지 않는다. 지금은 검사 정리용으로만 쓴다.
    """
    with pg.connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM public.app_projects WHERE graph = %s", (graph,))
            cur.execute("SELECT og_drop_graph(%s)", (graph,))
