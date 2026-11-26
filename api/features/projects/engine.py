"""그래프 엔진별 **카탈로그 · 권한** — 프로젝트 층이 엔진을 직접 부르지 않게 하는 이음매.

프로젝트 = graph 하나, 권한 = (role, graph, level) 한 행. 이 모양은 엔진과 상관없이 같다.
엔진마다 다른 것은 셋뿐이다 — graph 를 만들고 · 지우고 · 있는지 보는 법, 그리고 권한 행이 어디 있고
DB 가 그것을 어떻게 강제하는가.

```
ROBO_GRAPH_ENGINE=ontological (기본)   권한 행 = og_catalog.grantee · og_grant / og_revoke 가 DB 권한까지
ROBO_GRAPH_ENGINE=age                  권한 행 = public.app_project_members (앱 표)
                                       graph = ag_catalog.create_graph / drop_graph (스키마 하나)
                                       read 격리 = 그 스키마에 대한 PostgreSQL GRANT (게이트웨이는 로그인한 role 로 붙는다)
```

AGE 에는 `og_catalog.grantee` 같은 권한 카탈로그가 없다(2026-11-23 분석 §3-2). 그래서 권한 행은 앱 표로 두고,
**읽기 격리는 여전히 DB 가 지킨다** — AGE 의 graph 는 PostgreSQL 스키마이고 Bolt 게이트웨이는 드라이버가 준
자격을 그대로 PostgreSQL role 로 쓴다(`ontological-db` `bolt/README.md` — "Permissions, RLS and audit stay
PostgreSQL's"). read 사용자는 자기 role 로 붙으므로(`connection_binding`) SELECT 만 받은 스키마만 읽힌다.

쓰기 · 관리 등급은 두 엔진 모두 소유자 자격으로 붙는다(라벨을 만들어야 해서 — `connection_binding` 머리말).
"""

from __future__ import annotations

import os
from typing import Any, Optional

from psycopg import sql

from api.platform import pg

__all__ = [
    "engine_name", "is_age", "GRANTEE", "ensure_schema",
    "graph_exists", "graph_names", "create_graph", "drop_graph",
    "grant", "revoke", "level", "grants_of_graph", "graphs_of_role", "orphan_grants", "forget_grant",
]


def engine_name() -> str:
    name = (os.environ.get("ROBO_GRAPH_ENGINE") or "ontological").strip().lower()
    if name not in ("ontological", "age"):
        raise RuntimeError(f"ROBO_GRAPH_ENGINE 는 ontological | age — 받은 값: {name!r}")
    return name


def is_age() -> bool:
    return engine_name() == "age"


def grantee() -> str:
    """(role, graph, level) 권한 행이 있는 관계 — SQL 에 그대로 넣는다(식별자 고정값, 사용자 입력 아님)."""
    return "public.app_project_members" if is_age() else "og_catalog.grantee"


# 모듈 상수처럼 쓰는 자리를 위해(함수 호출을 잊는 실수를 줄인다). 값은 부를 때마다 엔진을 본다.
class _Grantee:
    def __str__(self) -> str:  # f-string 안에서 쓴다
        return grantee()


GRANTEE = _Grantee()

_AGE_SCHEMA = """
CREATE TABLE IF NOT EXISTS public.app_project_members (
    role        TEXT NOT NULL,
    graph       TEXT NOT NULL,
    level       TEXT NOT NULL CHECK (level IN ('read', 'write', 'admin')),
    granted_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (role, graph)
);
CREATE INDEX IF NOT EXISTS idx_app_project_members_graph ON public.app_project_members (graph);
"""


def ensure_schema(cur) -> None:
    """엔진별 표. Ontological 은 엔진이 들고 있으므로 할 일이 없다."""
    if is_age():
        cur.execute(_AGE_SCHEMA)


# ── graph ─────────────────────────────────────────────────────────────

def graph_exists(name: str) -> bool:
    if is_age():
        return bool(pg.query("SELECT 1 FROM ag_catalog.ag_graph WHERE name = %s", (name,)))
    return bool(pg.query("SELECT 1 FROM og_catalog.graph WHERE name = %s", (name,)))


def graph_names() -> set[str]:
    if is_age():
        return {r["name"] for r in pg.query("SELECT name::text AS name FROM ag_catalog.ag_graph")}
    return {r["name"] for r in pg.query("SELECT name FROM og_catalog.graph")}


def create_graph(cur, name: str) -> None:
    if is_age():
        cur.execute("SELECT ag_catalog.create_graph(%s)", (name,))
    else:
        cur.execute("SELECT og_create_graph(%s)", (name,))


def drop_graph(cur, name: str) -> None:
    if is_age():
        # cascade — 라벨 표까지. 권한 행은 부르는 쪽(drop_project)이 먼저 걷는다.
        cur.execute("SELECT ag_catalog.drop_graph(%s, true)", (name,))
    else:
        cur.execute("SELECT og_drop_graph(%s)", (name,))


# ── 권한 ──────────────────────────────────────────────────────────────

def _age_db_grants(cur, role: str, graph: str, give: bool) -> None:
    """AGE: read 격리를 PostgreSQL 이 지키게 한다 — graph 스키마의 USAGE + SELECT,
    그리고 **앞으로 생길 라벨 표**에도(라벨은 인제스천마다 새로 생긴다 — 기본 권한으로 따라가게).

    쓰기 권한은 주지 않는다 — write · admin 은 소유자 자격으로 붙는다(머리말).
    """
    schema, who = sql.Identifier(graph), sql.Identifier(role)
    owner = cur.execute(
        "SELECT pg_get_userbyid(nspowner) AS owner FROM pg_namespace WHERE nspname = %s", (graph,)
    ).fetchone()
    if not owner:
        return  # graph 가 없다 — 권한 행만 다룬다(orphan 정리 등)
    by = sql.Identifier(owner["owner"])
    if give:
        cur.execute(sql.SQL("GRANT USAGE ON SCHEMA {} TO {}").format(schema, who))
        cur.execute(sql.SQL("GRANT SELECT ON ALL TABLES IN SCHEMA {} TO {}").format(schema, who))
        cur.execute(sql.SQL("ALTER DEFAULT PRIVILEGES FOR ROLE {} IN SCHEMA {} GRANT SELECT ON TABLES TO {}")
                    .format(by, schema, who))
    else:
        cur.execute(sql.SQL("ALTER DEFAULT PRIVILEGES FOR ROLE {} IN SCHEMA {} REVOKE ALL ON TABLES FROM {}")
                    .format(by, schema, who))
        cur.execute(sql.SQL("REVOKE ALL ON ALL TABLES IN SCHEMA {} FROM {}").format(schema, who))
        cur.execute(sql.SQL("REVOKE ALL ON SCHEMA {} FROM {}").format(schema, who))


def grant(cur, role: str, level_name: str, graph: str) -> None:
    if is_age():
        cur.execute(
            "INSERT INTO public.app_project_members (role, graph, level) VALUES (%s, %s, %s) "
            "ON CONFLICT (role, graph) DO UPDATE SET level = EXCLUDED.level, granted_at = now()",
            (role, graph, level_name),
        )
        _age_db_grants(cur, role, graph, give=True)
    else:
        cur.execute("SELECT og_grant(%s, %s, %s)", (role, level_name, graph))


def revoke(cur, role: str, graph: str) -> None:
    if is_age():
        _age_db_grants(cur, role, graph, give=False)
        cur.execute("DELETE FROM public.app_project_members WHERE role = %s AND graph = %s", (role, graph))
    else:
        cur.execute("SELECT og_revoke(%s, %s)", (role, graph))


def forget_grant(role: str, graph: str) -> None:
    """권한 행만 지운다 — 엔진 쪽 객체가 이미 사라져 revoke 가 죽는 경우(orphan 정리)."""
    pg.execute(f"DELETE FROM {grantee()} WHERE role = %s AND graph = %s", (role, graph))


def level(role: str, graph: str) -> Optional[str]:
    rows = pg.query(f"SELECT level FROM {grantee()} WHERE role = %s AND graph = %s", (role, graph))
    return rows[0]["level"] if rows else None


def grants_of_graph(cur_or_none, graph: str) -> list[dict[str, Any]]:
    q = f"SELECT role, level FROM {grantee()} WHERE graph = %s ORDER BY role"
    if cur_or_none is None:
        return pg.query(q, (graph,))
    cur_or_none.execute(q, (graph,))
    return cur_or_none.fetchall()


def graphs_of_role(role: str) -> set[str]:
    return {r["graph"] for r in pg.query(f"SELECT graph FROM {grantee()} WHERE role = %s", (role,))}


def orphan_grants() -> list[dict[str, Any]]:
    graphs = "ag_catalog.ag_graph" if is_age() else "og_catalog.graph"
    return pg.query(
        f"SELECT role, graph FROM {grantee()} g "
        f"WHERE NOT EXISTS (SELECT 1 FROM {graphs} x WHERE x.name::text = g.graph)"
    )
