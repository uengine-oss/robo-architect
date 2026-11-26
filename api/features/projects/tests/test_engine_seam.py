"""엔진 이음매 — ROBO_GRAPH_ENGINE 이 권한 행 · graph 조작을 고른다 (2026-11-26, AGE 판)."""

import pytest

from api.features.projects import engine


class _Cur:
    def __init__(self, owner="robo"):
        self.sql = []
        self._owner = owner

    def execute(self, q, params=None):
        self.sql.append((q if isinstance(q, str) else q.as_string(None), params))
        return self

    def fetchone(self):
        return {"owner": self._owner} if self._owner else None

    def fetchall(self):
        return []


def _texts(cur):
    return " | ".join(s for s, _ in cur.sql)


def test_default_is_ontological(monkeypatch):
    monkeypatch.delenv("ROBO_GRAPH_ENGINE", raising=False)
    assert engine.engine_name() == "ontological"
    assert str(engine.GRANTEE) == "og_catalog.grantee"
    cur = _Cur()
    engine.create_graph(cur, "prj_x")
    engine.grant(cur, "p_1", "admin", "prj_x")
    engine.revoke(cur, "p_1", "prj_x")
    engine.drop_graph(cur, "prj_x")
    t = _texts(cur)
    assert "og_create_graph" in t and "og_grant" in t and "og_revoke" in t and "og_drop_graph" in t
    assert "ag_catalog" not in t and "app_project_members" not in t


def test_unknown_engine_is_refused(monkeypatch):
    monkeypatch.setenv("ROBO_GRAPH_ENGINE", "neo4j")
    with pytest.raises(RuntimeError):
        engine.engine_name()


def test_age_uses_app_table_and_ag_catalog(monkeypatch):
    monkeypatch.setenv("ROBO_GRAPH_ENGINE", "age")
    assert str(engine.GRANTEE) == "public.app_project_members"
    cur = _Cur()
    engine.ensure_schema(cur)
    engine.create_graph(cur, "prj_x")
    engine.grant(cur, "p_1", "read", "prj_x")
    t = _texts(cur)
    assert "CREATE TABLE IF NOT EXISTS public.app_project_members" in t
    assert "ag_catalog.create_graph" in t
    assert "INSERT INTO public.app_project_members" in t
    # read 격리를 DB 가 지키게 — 스키마 USAGE · SELECT · 앞으로 생길 라벨 표까지
    assert 'GRANT USAGE ON SCHEMA "prj_x" TO "p_1"' in t
    assert 'GRANT SELECT ON ALL TABLES IN SCHEMA "prj_x" TO "p_1"' in t
    assert 'ALTER DEFAULT PRIVILEGES FOR ROLE "robo" IN SCHEMA "prj_x" GRANT SELECT ON TABLES TO "p_1"' in t
    assert "og_" not in t


def test_age_revoke_takes_db_grants_back(monkeypatch):
    monkeypatch.setenv("ROBO_GRAPH_ENGINE", "age")
    cur = _Cur()
    engine.revoke(cur, "p_1", "prj_x")
    engine.drop_graph(cur, "prj_x")
    t = _texts(cur)
    assert 'REVOKE ALL ON ALL TABLES IN SCHEMA "prj_x" FROM "p_1"' in t
    assert 'REVOKE ALL ON SCHEMA "prj_x" FROM "p_1"' in t
    assert "DELETE FROM public.app_project_members" in t
    assert "ag_catalog.drop_graph" in t


def test_age_grant_without_graph_only_touches_row(monkeypatch):
    """graph 가 이미 없는 경우(orphan) — 스키마 GRANT 는 건너뛰고 행만."""
    monkeypatch.setenv("ROBO_GRAPH_ENGINE", "age")
    cur = _Cur(owner=None)
    engine.grant(cur, "p_1", "write", "prj_gone")
    t = _texts(cur)
    assert "INSERT INTO public.app_project_members" in t
    assert "GRANT USAGE" not in t
