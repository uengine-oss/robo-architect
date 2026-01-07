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
from .neo4j_ops.policies import PolicyOps
from .neo4j_ops.properties import PropertyOps
from .neo4j_ops.references import ReferenceOps
from .neo4j_ops.readmodels import ReadModelOps
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
    PolicyOps,
    PropertyOps,
    ReferenceOps,
    ReadModelOps,
    UIWireframeOps,
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
        """Context manager for Neo4j sessions."""
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


