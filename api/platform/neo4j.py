from __future__ import annotations

"""
Neo4j connectivity shared across business capabilities.

This module intentionally centralizes:
- dotenv loading
- Neo4j connection configuration
- driver lifecycle
- session creation

So feature modules can focus on their domain behavior and Cypher, without
re-implementing connection plumbing.
"""

import time
from typing import Optional

from neo4j import GraphDatabase
from neo4j import Driver

from api.platform.neo4j_context import get_override
from api.platform.observability.smart_logger import SmartLogger
from api.platform.env import (
    get_analyzer_neo4j_database,
    get_neo4j_database,
    get_neo4j_password,
    get_neo4j_uri,
    get_neo4j_user,
)

# Neo4j Configuration
NEO4J_URI = get_neo4j_uri()
NEO4J_USER = get_neo4j_user()
NEO4J_PASSWORD = get_neo4j_password()
NEO4J_DATABASE = get_neo4j_database()
ANALYZER_NEO4J_DATABASE = get_analyzer_neo4j_database()

_driver: Optional[Driver] = None


def init_neo4j_driver(*, log: bool = True) -> Driver:
    """
    Initialize a singleton Neo4j driver if needed.
    Safe to call multiple times.
    """
    global _driver
    if _driver is not None:
        return _driver

    t0 = time.perf_counter()
    _driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))

    if log:
        SmartLogger.log(
            "INFO",
            "Neo4j driver created.",
            category="platform.neo4j.driver.init",
            params={
                "neo4j_uri": NEO4J_URI,
                "neo4j_user": NEO4J_USER,
                "neo4j_database": NEO4J_DATABASE,
                "duration_ms": int((time.perf_counter() - t0) * 1000),
            },
        )
    return _driver


def close_neo4j_driver(*, log: bool = True) -> None:
    """Close and reset the singleton Neo4j driver."""
    global _driver
    if _driver is None:
        return
    try:
        _driver.close()
    finally:
        _driver = None
        if log:
            SmartLogger.log(
                "INFO",
                "Neo4j driver closed.",
                category="platform.neo4j.driver.close",
                params={"neo4j_uri": NEO4J_URI},
            )


def get_driver() -> Driver:
    """Get the singleton Neo4j driver, initializing lazily if needed."""
    return init_neo4j_driver(log=False)


# Electron override 용 드라이버 캐시 — 연결(uri/user/password)별 1개.
_override_drivers: dict[tuple[str, str, str], Driver] = {}


def _driver_for(uri: str, user: str, password: str) -> Driver:
    key = (uri, user, password)
    driver = _override_drivers.get(key)
    if driver is None:
        driver = GraphDatabase.driver(uri, auth=(user, password))
        _override_drivers[key] = driver
    return driver


def get_session(database: str | None = None):
    """Get a Neo4j session.

    연결 출처: 요청에 Neo4j override(Electron ``X-Neo4j-*`` 헤더)가 있으면 그 연결을,
    없으면 ``.env`` 를 쓴다 — analyzer / catalog / data-fabric 과 동일 계약.

    Args:
        database: 지정 시 해당 DB. None이면 NEO4J_DATABASE. override 가 DB 를 지정하면
            그쪽이 우선 — Electron 이 고른 DB 하나에 설계·분석 그래프가 함께 있기 때문.
    """
    override = get_override()
    if override is not None:
        db = override.database or database or NEO4J_DATABASE
        driver = _driver_for(override.uri, override.user, override.password)
    else:
        db = database or NEO4J_DATABASE
        driver = get_driver()

    if db:
        return driver.session(database=db)
    return driver.session()


