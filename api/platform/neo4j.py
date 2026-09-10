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


def analyzer_database() -> Optional[str]:
    """이 요청이 읽어야 할 분석 graph.

    프로젝트가 정한 값이 있으면 그것을, 없으면 `.env` 를 쓴다. 모듈 상수를 그대로
    쓰면 **프로세스가 뜰 때 정해진 하나**라, 프로젝트를 바꿔도 분석 결과는 안
    바뀐다 — 설계는 다른 프로젝트인데 추적성만 이전 분석을 가리키게 된다.
    """
    override = get_override()
    if override is not None:
        if override.analyzer_database:
            return override.analyzer_database
        if not override.analyzer_pinned:
            # Electron 이 고른 연결이다. 그쪽은 **DB 하나에 설계·분석이 함께** 있어
            # 분석 graph 를 따로 보내지 않는다. 그 하나를 그대로 쓴다 — 여기서
            # `.env` 로 떨어지면 런처가 고른 것과 다른 곳을 읽는다.
            return override.database or ANALYZER_NEO4J_DATABASE
        if override.analyzer_pinned:
            # 프로젝트가 분석 짝을 정하지 않았다. **`.env` 로 떨어뜨리지 않는다** —
            # 분석 없이 문서만 올린 프로젝트가 정상 상태이고, 거기서 `.env` 를
            # 보면 남의 프로젝트 분석이 이 프로젝트의 추적성으로 나온다.
            return None
    return ANALYZER_NEO4J_DATABASE


def analyzer_session():
    """분석 graph 세션. **분석 짝이 없으면 None** 을 돌려준다.

    `get_session(database=None)` 은 설계 graph 로 떨어지므로 그대로 쓸 수 없다.
    호출부가 "분석 없음"을 명시로 다루게 강제하는 것이 이 함수의 목적이다.
    """
    db = analyzer_database()
    if not db:
        return None
    return get_session(database=db)


def design_database() -> Optional[str]:
    """이 요청이 보고 있는 설계 graph — 곧 **프로젝트의 식별자**다.

    `get_session()` 이 안에서 같은 계산을 하지만 그건 세션을 열어야 알 수 있다.
    스냅샷은 그래프가 아니라 Postgres 에 쌓이므로 이름만 따로 필요하다.
    """
    override = get_override()
    if override is not None and override.database:
        return override.database
    return NEO4J_DATABASE


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
        database: 지정 시 **그 DB 가 이긴다.** None 이면 override 의 DB, 그것도
            없으면 `NEO4J_DATABASE`.
    """
    override = get_override()
    if override is not None:
        # **명시한 graph 가 이긴다.** 예전에는 override 가 이겼는데, 프로젝트마다
        # 설계·분석 graph 가 갈리면서 그 우선순위가 조용한 오답을 만들었다 —
        # `get_session(database="analyzer_run")` 이 설계 graph 를 열어, 분석
        # 174건이 한 번도 안 읽히고 0건으로 나왔다. 오류는 나지 않는다.
        #
        # Electron 경로는 `analyzer_database()` 가 override 의 graph 를 돌려주므로
        # 명시 값과 override 가 같아져 동작이 바뀌지 않는다.
        db = database or override.database or NEO4J_DATABASE
        driver = _driver_for(override.uri, override.user, override.password)
    else:
        db = database or NEO4J_DATABASE
        driver = get_driver()

    if db:
        return driver.session(database=db)
    return driver.session()


