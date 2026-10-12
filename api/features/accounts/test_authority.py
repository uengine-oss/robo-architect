"""권한 회귀 및 실제 PG 경쟁/롤백. AUTH_TEST_PG_DSN은 격리 DB에서만 공급한다."""
from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi import HTTPException
from starlette.requests import Request

from api.features.accounts import guard, store
from api.platform import pg


def test_missing_account_is_not_approved():
    assert not store.is_approved(None)
    assert not store.is_approved({"role": "admin"})


@pytest.mark.parametrize("status", ["pending", "rejected"])
def test_unapproved_admin_denied(monkeypatch, status):
    request = Request({"type": "http", "headers": []})
    request.state.auth_claims = {"sub": "a"}
    monkeypatch.setattr(store, "require_initialized", lambda: None)
    monkeypatch.setattr(store, "get_user", lambda uid: {"role": "admin", "status": status})
    with pytest.raises(HTTPException) as exc:
        guard.require_admin(request)
    assert exc.value.status_code == 403


def test_admin_store_failure_denied(monkeypatch):
    request = Request({"type": "http", "headers": []})
    request.state.auth_claims = {"sub": "a"}
    monkeypatch.setattr(store, "require_initialized", lambda: (_ for _ in ()).throw(RuntimeError()))
    with pytest.raises(HTTPException) as exc:
        guard.require_admin(request)
    assert exc.value.status_code == 503


@pytest.fixture
def database(monkeypatch):
    dsn = os.environ.get("AUTH_TEST_PG_DSN")
    if not dsn:
        pytest.skip("격리 PostgreSQL에서 실행하는 검사")
    monkeypatch.setenv("OG_PG_DSN", dsn)
    # 운영 DB를 실수로 공급하면 초기화하지 않는다.
    assert pg.query("SELECT current_database() AS name")[0]["name"] == "auth_test"
    store.ensure_schema()
    pg.execute("TRUNCATE public.app_account_audit, public.app_users")
    pg.execute("UPDATE public.app_auth_policy SET initialized=false, approval_required=true, revision=0")
    return None


def grant(uid="a"):
    return store.operator_grant(uid, operator_id="test-operator", reason="isolated test")


def login(uid="b", **kwargs):
    return store.upsert_from_sso({"empno": uid, "name": "test", **kwargs})


def test_environment_cannot_bootstrap_or_disable_approval(database, monkeypatch):
    monkeypatch.setenv("ADMIN_EMPLOYEE_NOS", "b")
    monkeypatch.setenv("AUTH_APPROVAL_REQUIRED", "0")
    with pytest.raises(store.AuthorityNotInitialized):
        login()
    assert store.get_user("b") is None
    grant()
    user = login()
    assert user["role"] == "member" and user["status"] == "pending"
    assert store.approval_enabled()
    store.set_status("b", "approved", actor_uid="a")
    store.set_role("b", "admin", actor_uid="a")
    store.set_role("b", "member", actor_uid="a")
    assert login()["role"] == "member"


def test_initial_grant_revokes_unverified_legacy_admin(database):
    pg.execute("INSERT INTO public.app_users (uid, value) VALUES "
               "('legacy', '{\"role\":\"admin\",\"status\":\"approved\"}')")
    grant()
    assert store.get_user("legacy")["role"] == "member"
    assert pg.query("SELECT count(*) AS n FROM public.app_account_audit")[0]["n"] == 2


def test_last_admin_and_cross_revocation(database):
    grant()
    with pytest.raises(store.AccountChangeDenied):
        store.operator_revoke("a", operator_id="ops", reason="test")
    grant("b")
    def revoke(pair):
        actor, target = pair
        try:
            store.set_role(target, "member", actor_uid=actor)
            return True
        except store.AccountChangeDenied:
            return False
    with ThreadPoolExecutor(2) as pool:
        result = list(pool.map(revoke, [("a", "b"), ("b", "a")]))
    assert sorted(result) == [False, True]
    assert len([u for u in store.list_users() if store.is_admin(u) and store.is_approved(u)]) == 1


def test_audit_failure_rolls_back(database):
    grant()
    login()
    pg.execute("ALTER TABLE public.app_account_audit ADD CONSTRAINT test_reject_audit "
               "CHECK (target_uid IS DISTINCT FROM 'b')")
    try:
        with pytest.raises(Exception):
            store.set_status("b", "approved", actor_uid="a")
        assert store.get_user("b")["status"] == "pending"
    finally:
        pg.execute("ALTER TABLE public.app_account_audit DROP CONSTRAINT test_reject_audit")


def test_profile_update_does_not_restore_role_or_status(database):
    grant()
    grant("b")
    def profile(_):
        return login("b", name="changed")
    with ThreadPoolExecutor(3) as pool:
        tasks = [pool.submit(profile, i) for i in range(10)]
        tasks.append(pool.submit(store.set_role, "b", "member", actor_uid="a"))
        tasks.append(pool.submit(store.set_status, "b", "rejected", actor_uid="a"))
        for task in tasks:
            task.result()
    assert login("b")["role"] == "member"
    assert store.get_user("b")["status"] == "rejected"


def test_policy_is_explicit_and_audited(database, monkeypatch):
    grant()
    store.set_policy(False, operator_id="ops", reason="test policy")
    monkeypatch.setenv("AUTH_APPROVAL_REQUIRED", "1")
    assert not store.approval_enabled()
    assert login()["status"] == "approved"
    rows = pg.query("SELECT action FROM public.app_account_audit ORDER BY id")
    assert rows[-1]["action"] == "policy_changed"


def test_database_access_separation(database, monkeypatch):
    import psycopg

    from api.features.accounts.access import configure
    from api.features.code_templates import store as templates
    with pg.connection() as conn, conn.cursor() as cur:
        cur.execute(templates._SCHEMA)
        cur.execute("CREATE ROLE auth_server_test NOLOGIN")
        cur.execute("CREATE ROLE auth_pc_test NOLOGIN")
        cur.execute("GRANT UPDATE(value) ON public.app_users TO auth_pc_test")
    configure("auth_server_test", "auth_pc_test")
    grant()
    with pg.connection() as conn, conn.cursor() as cur:
        cur.execute("SET ROLE auth_server_test")
        cur.execute("SELECT * FROM public.app_auth_policy FOR UPDATE")
        cur.execute("INSERT INTO public.app_account_audit "
                    "(actor_type, actor_id, action, reason) VALUES ('user','a','test','test')")
    for statement in (
        "UPDATE public.app_users SET value='{}'",
        "DELETE FROM public.app_auth_policy",
        "TRUNCATE public.app_account_audit",
        "INSERT INTO public.app_code_templates(set_name,relative_path,body) VALUES ('x','x','x')",
        "CREATE TABLE public.auth_escalation (id int)",
        "SET ROLE auth_server_test",
    ):
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            with pg.connection() as conn, conn.cursor() as cur:
                cur.execute("SET SESSION AUTHORIZATION auth_pc_test")
                cur.execute(statement)


def test_central_api_with_restricted_runtime(database, monkeypatch):
    from contextlib import contextmanager

    from fastapi.testclient import TestClient

    from api.authority import app
    from api.features.accounts.access import configure
    from api.features.auth.tokens import issue_token
    from api.features.code_templates import store as templates

    monkeypatch.delenv("ROBO_AUTHORITY_URL", raising=False)
    monkeypatch.setenv("AUTH_JWT_SECRET", "isolated-test-secret-which-is-not-a-production-credential")
    monkeypatch.setenv("AUTH_PROVIDER", "swp")
    monkeypatch.setenv("ROBO_AUTHORITY_SERVER", "1")
    monkeypatch.setenv("AUTH_ENFORCE", "0")
    monkeypatch.setenv("AUTH_DEV_LOGIN_ENABLED", "true")
    with pg.connection() as conn, conn.cursor() as cur:
        cur.execute(templates._SCHEMA)
        cur.execute("CREATE ROLE authority_runtime_api NOLOGIN")
        cur.execute("CREATE ROLE authority_pc_api NOLOGIN")
    configure("authority_runtime_api", "authority_pc_api")
    grant()
    grant("b")
    token_a = issue_token(store.get_user("a"))
    token_b = issue_token(store.get_user("b"))
    connection = pg.connection
    @contextmanager
    def runtime_connection():
        with connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SET ROLE authority_runtime_api")
            yield conn
    monkeypatch.setattr(pg, "connection", runtime_connection)
    with TestClient(app) as browser:
        assert browser.get("/api/accounts").status_code == 401
        assert browser.post("/api/auth/dev-login", data={"loginId": "test", "password": "test"}).status_code == 404
        provider = browser.get("/api/auth/provider").json()
        assert provider["enforce"] and not provider["devLogin"]["enabled"]
        assert browser.post("/api/auth/introspect", headers={"Authorization": "Bearer " + token_b}).json()["role"] == "admin"
        assert browser.post("/api/accounts/b/role", json={"role": "member"},
                            headers={"Authorization": "Bearer " + token_a}).status_code == 200
        assert browser.get("/api/accounts", headers={"Authorization": "Bearer " + token_b}).status_code == 403
        assert browser.post("/api/accounts/b/status", json={"status": "rejected"},
                            headers={"Authorization": "Bearer " + token_a}).status_code == 200
        assert browser.post("/api/auth/introspect", headers={"Authorization": "Bearer " + token_b}).status_code == 403
        assert not browser.get("/api/auth/me", headers={"Authorization": "Bearer " + token_b}).json()["authenticated"]
