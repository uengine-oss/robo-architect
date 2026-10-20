"""
Neo4j Client for Event Storming Graph Operations

This client is organized by business concept (UserStory / BoundedContext / Aggregate / Command / Event / Policy),
while keeping a single stable access point (`get_neo4j_client`) for the ingestion workflow.
"""

from __future__ import annotations

import threading
from contextlib import contextmanager
from dataclasses import dataclass, field

from neo4j import Driver, GraphDatabase

from api.platform.env import (
    get_neo4j_database,
    get_neo4j_password,
    get_neo4j_uri,
    get_neo4j_user,
)

from .neo4j_ops.aggregates import AggregateOps
from .neo4j_ops.analysis import GraphAnalysisOps
from .neo4j_ops.bounded_contexts import BoundedContextOps
from .neo4j_ops.commands import CommandOps
from .neo4j_ops.events import EventOps
from .neo4j_ops.features import FeatureOps
from .neo4j_ops.gwt import GWTOps
from .neo4j_ops.invariants import InvariantOps
from .neo4j_ops.policies import PolicyOps
from .neo4j_ops.properties import PropertyOps
from .neo4j_ops.references import ReferenceOps
from .neo4j_ops.readmodels import ReadModelOps
from .neo4j_ops.ui_flow import UIFlowOps
from .neo4j_ops.ui_wireframes import UIWireframeOps
from .neo4j_ops.user_stories import UserStoryOps


# ── 일시적인 그래프 오류를 **다시 해 본다** (2026-10-20 · done15 §300) ──────
#
# 적재는 정책·속성을 `asyncio.gather` 로 **동시에** 건드린다. 2026-10-20 실측에서
# 그 한 번의 돌진(02:15:01 의 **150밀리초 안**)에 14건이 같이 터졌다:
#
#     8건  Neo.TransientError.Transaction.DeadlockDetected
#     6건  Neo.ClientError.Statement.ArgumentError
#          "duplicate key value violates unique constraint **pg_type_typname_nsp_index**"
#
# 둘 다 **같은 뿌리**다 — 라벨을 처음 쓸 때 그래프 엔진이 Postgres 쪽 타입과
# 테이블을 만드는데, 여럿이 동시에 만들면 카탈로그에서 부딪친다. 둘 다
# **다시 하면 통과하는** 종류다(2026-10-15 에도 같은 짝이 나왔다 — `pg_type` 11 ·
# 교착 13 · done12 §233).
#
# ⚠ 그런데 **드라이버는 앞의 것만 재시도한다.** `TransientError` 는 관리
#   트랜잭션이 알아서 다시 걸지만, `pg_type` 충돌은 `ClientError` 로 와서
#   **그냥 실패로 떨어진다.** 그래서 그 한 가지를 여기서 이름으로 집어 다시 한다.
#
# ⚠ **아무 ClientError 나 다시 하지 않는다.** ClientError 는 보통 "질의가 틀렸다"
#   는 뜻이고, 그걸 다시 하면 같은 실패를 반복하며 시간만 쓴다. 그래서 표식을
#   **이 한 줄로 좁혔다.** 늘릴 때는 "다시 하면 통과하는가" 를 재고 늘린다.
_RETRYABLE_MARKERS = ("pg_type_typname_nsp_index",)

# ── 다시 한 횟수를 **센다** (2026-10-20 · done15 §301) ────────────────
#
# 재시도를 넣고 나서 바로 알았다 — **성공한 재시도는 아무것도 안 남긴다.**
# 2026-10-20 적재에서 오류가 0 으로 나왔는데, 그게 **재시도가 삼켜서인지
# 애초에 안 난 것인지 가를 수가 없었다**(정책이 4개라 부딪힐 일이 적었다).
#
# 로그로는 안 된다 — 이 저장소는 **파일 최소 수준이 ERROR** 라 INFO·WARN 이
# 안 남는다. 그래서 적재 **요약에 싣는다**(화면엔 안 띄운다 · §296).
_retry_counts: dict[str, int] = {}
_retry_lock = threading.Lock()


def _retry_kind(exc: BaseException) -> str:
    """어떤 부딪침인가. **대소문자를 안 가린다** — 같은 일을
    두 가지로 부른다(코드는 `DeadlockDetected` · 메시지는 `deadlock detected`).
    """
    text = str(exc).lower()
    if "pg_type_typname_nsp_index" in text:
        return "pg_type"
    if "deadlock" in text:
        return "deadlock"
    return "other_transient"


def retry_stats_reset() -> None:
    """적재 한 판이 시작할 때 부른다."""
    with _retry_lock:
        _retry_counts.clear()


def retry_stats_snapshot() -> dict[str, int]:
    """지금까지 몇 번 다시 했나. 비었으면 빈 dict 다."""
    with _retry_lock:
        return dict(_retry_counts)


def _retry_bump(key: str) -> None:
    with _retry_lock:
        _retry_counts[key] = _retry_counts.get(key, 0) + 1


def is_retryable_graph_error(exc: BaseException) -> bool:
    """다시 해 볼 만한 일시적 오류인가."""
    if "TransientError" in type(exc).__name__:
        return True
    return any(m in str(exc) for m in _RETRYABLE_MARKERS)


def retry_on_transient(fn, *, attempts: int = 4, base_delay: float = 0.25):
    """`fn()` 을 돌리고, **일시적 오류면** 짧게 쉰었다 다시 한다.

    네 번 · 합쳐서 2초가 안 된다. 그보다 오래 걸리는 것은 일시적인 것이
    아니라 **설계가 부딪치는 것**이고, 그건 숨기면 안 된다.
    """
    import time as _t

    for i in range(attempts):
        try:
            return fn()
        except Exception as e:  # noqa: BLE001 — 아래에서 가려 낸다
            if not is_retryable_graph_error(e):
                raise
            if i == attempts - 1:
                _retry_bump("gave_up." + _retry_kind(e))
                raise
            _retry_bump(_retry_kind(e))
            _t.sleep(base_delay * (2 ** i))


@dataclass
class Neo4jConfig:
    """Neo4j connection configuration."""

    uri: str = field(default_factory=get_neo4j_uri)
    user: str = field(default_factory=get_neo4j_user)
    password: str = field(default_factory=get_neo4j_password)
    database: str | None = field(default_factory=get_neo4j_database)


class Neo4jClient(
    UserStoryOps,
    BoundedContextOps,
    AggregateOps,
    CommandOps,
    EventOps,
    FeatureOps,
    GWTOps,
    InvariantOps,
    PolicyOps,
    PropertyOps,
    ReferenceOps,
    ReadModelOps,
    UIWireframeOps,
    UIFlowOps,
    GraphAnalysisOps,
):
    """Neo4j client for Event Storming graph operations."""

    def __init__(self, config: Neo4jConfig | None = None):
        self.config = config or Neo4jConfig()
        self._driver: Driver | None = None

    @property
    def driver(self) -> Driver:
        if self._driver is None:
            # `max_transaction_retry_time` 을 **명시한다** (2026-10-20 · done15 §300).
            #
            # 관리 트랜잭션(`execute_write`)은 `TransientError` 를 만나면 드라이버가
            # 이 창 안에서 스스로 다시 건다. 기본은 **30초**인데, 우리 호출부는
            # 8초(`asyncio.wait_for`)·10초(`MAX_TIMEOUT`)에 끊는다. 그대로 두면
            # **우리 타임아웃이 먼저 터져서** 진짜 원인(교착)이 `TimeoutError` 로
            # 덮인다 — 되풀이해 온 "원인을 덮는" 부류다.
            # 그래서 창을 **12초**로 줄이고 호출부 쪽을 20초로 넓혔다.
            # 교착 재시도는 보통 1~2초 안에 통과한다.
            self._driver = GraphDatabase.driver(
                self.config.uri,
                auth=(self.config.user, self.config.password),
                max_transaction_retry_time=12.0,
            )
        return self._driver

    def close(self):
        if self._driver:
            self._driver.close()
            self._driver = None

    @contextmanager
    def session(self):
        """Context manager for Neo4j sessions.

        **요청이 고른 프로젝트를 따라간다.** 이 클라이언트는 프로세스 하나에
        싱글턴(`get_neo4j_client`)이고 `config.database` 는 프로세스가 뜰 때
        `.env` 로 정해진다. 그대로 두면 표준 인제스천(= `ES 승격`)이 어느
        프로젝트에서 시작하든 **`.env` 의 graph 한 곳**에 쓴다.

        실측으로 그랬다 — B 프로젝트에서 승격했더니 UserStory 12·Command 11 이
        전부 `robo` 로 갔고, 정작 그 프로젝트의 graph 에는 한 건도 안 생겼다.
        문서 업로드 1단계는 다른 코드라 제대로 갈렸기 때문에, 화면에서는
        "프로세스는 있는데 승격 결과만 안 보인다"로 나타난다.

        기본 설정 그대로일 때만 공용 진입점에 맡긴다 — 호출부가 연결을 명시해
        만든 클라이언트는 그 뜻을 그대로 지킨다.
        """
        from api.features.ingestion.server_scope import execution_scope
        server_scope = execution_scope.get()
        if self.config == Neo4jConfig() or server_scope is not None:
            from api.platform.neo4j import get_session as platform_session

            database = self.config.database if self.config != Neo4jConfig() else None
            with platform_session(database=database) as session:
                yield session
            return

        if self.config.database:
            session = self.driver.session(database=self.config.database)
        else:
            session = self.driver.session()
        try:
            yield session
        finally:
            session.close()

    def verify_connection(self) -> bool:
        """Verify Neo4j connection."""
        try:
            self.driver.verify_connectivity()
            with self.session() as session:
                session.run("RETURN 1").consume()
            return True
        except Exception:
            return False


_client: Neo4jClient | None = None


def get_neo4j_client() -> Neo4jClient:
    """Get the singleton Neo4j client instance."""
    global _client
    if _client is None:
        _client = Neo4jClient()
    return _client


