"""Server-only graph boundary inherited by workflow tasks."""
from contextvars import ContextVar
from dataclasses import dataclass

from fastapi import HTTPException

from api.features.accounts import store as accounts
from api.features.projects import store as projects
from api.platform import pg


@dataclass(frozen=True)
class ExecutionScope:
    uid: str
    graph: str
    analyzer: str | None
    runtime_dsn: str
    operator_dsn: str
    write: bool

    def check(self, database: str | None) -> None:
        if database not in {self.graph, self.analyzer} or not database:
            raise HTTPException(403, '요청한 프로젝트 범위를 벗어난 그래프입니다.')
        # Recheck before every graph session, including background workflow tasks.
        with pg.using_dsn(self.runtime_dsn):
            accounts.require_initialized()
            if not accounts.is_approved(accounts.get_user(self.uid)):
                raise HTTPException(403, '사용자 승인이 해제됐습니다.')
        with pg.using_dsn(self.operator_dsn):
            level = projects.level_of(self.uid, self.graph)
        allowed = ('write', 'admin') if self.write else ('read', 'write', 'admin')
        if level not in allowed:
            raise HTTPException(403, '프로젝트 권한이 해제됐습니다.')


execution_scope: ContextVar[ExecutionScope | None] = ContextVar('ingestion_execution_scope', default=None)
