"""Project authority credential scope and fail-closed PC delegation."""
import asyncio
import os

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from api import authority
from api.features.accounts.authority_client import delegated_path
from api.features.projects import store as projects
from api.platform import pg


def test_project_proxy_boundary():
    assert delegated_path('/api/projects')
    assert delegated_path('/api/projects/p/members')
    assert not delegated_path('/api/projects-malicious')


def test_credential_scope_is_task_local_and_restored(monkeypatch):
    monkeypatch.setenv('OG_PG_DSN', 'runtime')
    async def run():
        async def worker(dsn):
            with pg.using_dsn(dsn):
                await asyncio.sleep(0)
                assert pg.pg_dsn() == dsn
            assert pg.pg_dsn() == 'runtime'
        await asyncio.gather(worker('operator-a'), worker('operator-b'))
    asyncio.run(run())
    with pytest.raises(ValueError), pg.using_dsn('operator'):
        raise ValueError('rollback')
    assert pg.pg_dsn() == 'runtime'


def test_auth_checked_before_operator_scope(monkeypatch):
    monkeypatch.setenv('OG_PG_DSN', 'runtime')
    monkeypatch.setenv('ROBO_PROJECT_OPERATOR_DSN', 'operator')
    def denied(request):
        assert pg.pg_dsn() == 'runtime'
        raise HTTPException(403, 'not approved')
    monkeypatch.setattr(authority, 'current_claims', denied)
    monkeypatch.setattr(projects, 'ensure_schema', lambda: pytest.fail('privileged route reached'))
    assert TestClient(authority.app).get('/api/projects').status_code == 403
    assert pg.pg_dsn() == 'runtime'


def test_project_request_scope_and_missing_config(monkeypatch):
    monkeypatch.setenv('OG_PG_DSN', 'runtime')
    monkeypatch.delenv('ROBO_PROJECT_OPERATOR_DSN', raising=False)
    monkeypatch.setattr(authority, 'current_claims', lambda request: {'sub':'a'})
    client = TestClient(authority.app)
    assert client.post('/api/projects/adopt', json={'graph':'existing'}).status_code == 403
    assert client.get('/api/projects').status_code == 503
    monkeypatch.setenv('ROBO_PROJECT_OPERATOR_DSN', 'operator')
    monkeypatch.setattr(projects, 'ensure_schema', lambda: None)
    def listing(uid):
        assert uid == 'a' and pg.pg_dsn() == 'operator'
        return []
    monkeypatch.setattr(projects, 'list_projects', listing)
    assert client.get('/api/projects').status_code == 200
    assert pg.pg_dsn() == 'runtime'


def test_real_project_routes_use_server_operator(monkeypatch):
    dsn = os.environ.get('AUTH_TEST_PG_DSN')
    if not dsn:
        pytest.skip('Disposable DB required')
    monkeypatch.setenv('OG_PG_DSN', dsn)
    assert pg.query('SELECT current_database() AS name')[0]['name'] == 'auth_test'
    monkeypatch.delenv('ROBO_AUTHORITY_SERVER', raising=False)
    projects.ensure_schema()
    monkeypatch.setenv('ROBO_AUTHORITY_SERVER', '1')
    monkeypatch.setenv('ROBO_PROJECT_OPERATOR_DSN', dsn)
    monkeypatch.setenv('AUTH_ROLE_SECRET', 'isolated-project-role-secret-32-characters')
    # An unusable default proves project DB operations use the server scope.
    monkeypatch.setenv('OG_PG_DSN', 'host=127.0.0.1 port=1 dbname=invalid connect_timeout=1')
    monkeypatch.setattr(authority, 'current_claims', lambda request: {'sub':'central-project-a'})
    client = TestClient(authority.app)
    created = client.post('/api/projects', json={'name':'isolated server project'})
    assert created.status_code == 200, created.text
    graph = created.json()['graph']
    assert graph in {p['graph'] for p in client.get('/api/projects').json()['projects']}
    monkeypatch.setattr(authority, 'current_claims', lambda request: {'sub':'central-project-b'})
    assert graph not in {p['graph'] for p in client.get('/api/projects').json()['projects']}
    assert client.get(f'/api/projects/{graph}/members').status_code == 403
