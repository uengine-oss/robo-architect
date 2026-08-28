"""
Change Planning Runtime (LLM / embeddings / Neo4j access)

Business capability: provide the integrations needed by change planning nodes.
Kept local to the change planning feature implementation.
"""

from __future__ import annotations

from api.platform.env import (
    get_neo4j_database as get_env_neo4j_database,
)
from api.platform.env import (
    get_neo4j_password,
    get_neo4j_uri,
    get_neo4j_user,
)
from api.platform.llm import get_llm as _platform_get_llm


def get_llm():
    """Get the configured LLM instance."""
    return _platform_get_llm()


def get_embeddings():
    """Get the embeddings model.

    임베딩 endpoint/key 는 Chat 라우팅과 분리해서 해석한다 — 사내 게이트웨이가
    임베딩을 제공하지 않는 경우가 있다.
    """
    from api.platform.embeddings import get_embeddings as _platform_get_embeddings

    return _platform_get_embeddings()


def get_neo4j_driver():
    """Get Neo4j driver."""
    from neo4j import GraphDatabase

    uri = get_neo4j_uri()
    user = get_neo4j_user()
    password = get_neo4j_password()
    return GraphDatabase.driver(uri, auth=(user, password))


def get_neo4j_database() -> str | None:
    """Get target Neo4j database name (multi-database support)."""
    return get_env_neo4j_database()


def neo4j_session(driver):
    """Create a session for the configured database (or default)."""
    db = get_neo4j_database()
    return driver.session(database=db) if db else driver.session()


