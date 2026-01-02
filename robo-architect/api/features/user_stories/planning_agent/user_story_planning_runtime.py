from __future__ import annotations

import uuid

from neo4j import GraphDatabase

from api.platform.env import (
    get_neo4j_database,
    get_neo4j_password,
    get_neo4j_uri,
    get_neo4j_user,
)
from api.platform.llm import get_llm as _platform_get_llm


def get_llm():
    return _platform_get_llm()


def get_neo4j_driver():
    uri = get_neo4j_uri()
    user = get_neo4j_user()
    password = get_neo4j_password()
    return GraphDatabase.driver(uri, auth=(user, password))


def get_neo4j_session(driver):
    db = get_neo4j_database()
    if db:
        return driver.session(database=db)
    return driver.session()


def generate_id(prefix: str) -> str:
    return f"{prefix}-{str(uuid.uuid4())[:8].upper()}"


