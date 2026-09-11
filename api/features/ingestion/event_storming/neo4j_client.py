"""
Neo4j Client for Event Storming Graph Operations

This client is organized by business concept (UserStory / BoundedContext / Aggregate / Command / Event / Policy),
while keeping a single stable access point (`get_neo4j_client`) for the ingestion workflow.
"""

from __future__ import annotations

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
            self._driver = GraphDatabase.driver(self.config.uri, auth=(self.config.user, self.config.password))
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
        if self.config == Neo4jConfig():
            from api.platform.neo4j import get_session as platform_session

            with platform_session() as session:
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


