import httpx
import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from api.features.ingestion import ingestion_sessions as sessions
from api.features.ingestion import server_proxy
from api.features.ingestion.server_scope import ExecutionScope, execution_scope


@pytest.fixture
def scope(monkeypatch):
    from api.features.ingestion import server_scope as module
    monkeypatch.setattr(module.accounts, 'require_initialized', lambda: None)
    monkeypatch.setattr(module.accounts, 'get_user', lambda uid: {'status':'approved','role':'member'})
    monkeypatch.setattr(module.projects, 'level_of', lambda *args:'write')
    return ExecutionScope('member','project-a','analysis-a','runtime','operator',True)


def test_member_writer_allowed_and_foreign_graph_denied(scope):
    scope.check('project-a')
    scope.check('analysis-a')
    with pytest.raises(HTTPException) as error:
        scope.check('project-b')
    assert error.value.status_code == 403


def test_revocation_checked_during_background_execution(scope, monkeypatch):
    from api.features.ingestion import server_scope as module
    scope.check('project-a')
    monkeypatch.setattr(module.projects, 'level_of', lambda *args:'read')
    with pytest.raises(HTTPException):
        scope.check('project-a')


def test_approval_revoke_denies(scope, monkeypatch):
    from api.features.ingestion import server_scope as module
    monkeypatch.setattr(module.accounts, 'get_user', lambda uid:{'status':'rejected'})
    with pytest.raises(HTTPException):
        scope.check('project-a')


def test_session_project_isolation(scope):
    token = execution_scope.set(scope)
    try:
        session = sessions.create_session('server-scope-test')
        assert session.project_graph == 'project-a'
        execution_scope.set(ExecutionScope('other','project-b',None,'runtime','operator',True))
        assert sessions.get_session(session.id) is None
        with pytest.raises(ValueError):
            sessions.create_session(session.id)
    finally:
        execution_scope.reset(token)
        sessions.delete_session('server-scope-test')


class Frames(httpx.AsyncByteStream):
    async def __aiter__(self):
        yield b'data: {"progress":10}\n\n'
        yield b'data: {"progress":100}\n\n'


def test_unset_ingestion_url_selects_local_execution(monkeypatch):
    monkeypatch.delenv('ROBO_INGESTION_URL', raising=False)
    assert server_proxy.ingestion_url() == ''


def test_proxy_forwards_sse_and_strips_db_credentials(monkeypatch):
    monkeypatch.setenv('ROBO_INGESTION_URL','https://server.example')
    seen = []
    def handler(request):
        seen.append(request)
        return httpx.Response(200, headers={'content-type':'text/event-stream'}, stream=Frames())
    original = httpx.AsyncClient
    monkeypatch.setattr(httpx,'AsyncClient', lambda **kwargs:original(**kwargs,transport=httpx.MockTransport(handler)))
    app = FastAPI()
    app.add_middleware(server_proxy.IngestionProxyMiddleware)
    @app.get('/api/ingest/hybrid/stream/test')
    def local():
        pytest.fail('PC workflow executed')
    response = TestClient(app).get('/api/ingest/hybrid/stream/test',headers={
        'authorization':'Bearer token','x-project-graph':'project-a','x-neo4j-password':'secret'})
    assert response.status_code == 200 and '100' in response.text
    assert seen[0].headers['x-project-graph'] == 'project-a'
    assert 'x-neo4j-password' not in seen[0].headers


def test_proxy_connection_failure_never_executes_locally(monkeypatch):
    monkeypatch.setenv('ROBO_INGESTION_URL','https://server.example')
    def handler(request):
        raise httpx.ConnectError('offline')
    original = httpx.AsyncClient
    monkeypatch.setattr(httpx,'AsyncClient',lambda **kwargs:original(**kwargs,transport=httpx.MockTransport(handler)))
    app = FastAPI()
    app.add_middleware(server_proxy.IngestionProxyMiddleware)
    @app.post('/api/ingest/hybrid/upload')
    def local():
        pytest.fail('local fallback')
    assert TestClient(app).post('/api/ingest/hybrid/upload').status_code == 503
