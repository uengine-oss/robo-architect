"""Server ingestion API. No DB credential is returned to the PC."""
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from starlette.responses import JSONResponse

from api.authority import current_claims, lifespan as account_lifespan
from api.features.ingestion.server_scope import ExecutionScope, execution_scope
from api.features.projects import store as projects
from api.platform import pg
from api.platform.neo4j_context import Neo4jOverride, set_override


@asynccontextmanager
async def lifespan(app):
    async with account_lifespan(app):
        if not os.environ.get('ROBO_PROJECT_OPERATOR_DSN') or not os.environ.get('NEO4J_PASSWORD'):
            raise RuntimeError('서버 전용 프로젝트 운영/그래프 자격이 필요합니다.')
        yield


app = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)


def read_only_path(path: str) -> bool:
    return path in ('/api/ingest/stats', '/api/ingest/runs', '/api/ingest/replacement-preview',
                    '/api/ingest/hybrid/sessions') or (
        path.startswith('/api/ingest/hybrid/session/') and
        path.endswith(('/snapshot', '/pipeline-status')))


@app.middleware('http')
async def execution_guard(request, call_next):
    if request.url.path == '/healthz':
        return JSONResponse({'status':'ok'})
    try:
        claims = current_claims(request)
        if claims.get('scope'):
            raise HTTPException(403, '일반 사용자 세션이 필요합니다.')
        graph = request.headers.get('x-project-graph', '').strip()
        if not graph:
            raise HTTPException(403, '프로젝트를 선택하세요.')
        runtime_dsn = pg.pg_dsn()
        operator_dsn = os.environ['ROBO_PROJECT_OPERATOR_DSN']
        with pg.using_dsn(operator_dsn):
            project = projects.get_project(graph)
            if not project:
                raise HTTPException(403, '프로젝트에 접근할 수 없습니다.')
            scope = ExecutionScope(str(claims['sub']), graph, project.get('analyzerGraph'),
                                   runtime_dsn, operator_dsn,
                                   not (request.method == 'GET' and read_only_path(request.url.path)))
            scope.check(graph)
            token = execution_scope.set(scope)
            set_override(Neo4jOverride(os.environ['NEO4J_URI'], os.environ['NEO4J_USER'],
                         os.environ['NEO4J_PASSWORD'], graph, scope.analyzer, True))
            request.state.auth_claims = claims
            try:
                return await call_next(request)
            finally:
                set_override(None)
                execution_scope.reset(token)
    except HTTPException as exc:
        return JSONResponse({'detail':exc.detail}, status_code=exc.status_code)
    except Exception:
        return JSONResponse({'detail':'서버 실행 권한 또는 저장소를 확인할 수 없습니다.'}, status_code=503)


from api.features.ingestion.router import router as ingestion_router  # noqa: E402
from api.features.ingestion.hybrid.router import router as hybrid_router  # noqa: E402
app.include_router(ingestion_router)
app.include_router(hybrid_router)
