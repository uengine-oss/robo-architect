from __future__ import annotations

import uuid

from neo4j import GraphDatabase

from api.platform.env import (
    get_llm_provider_model,
    get_neo4j_database,
    get_neo4j_password,
    get_neo4j_uri,
    get_neo4j_user,
)

def get_llm():
    provider, model = get_llm_provider_model()

    if provider == "anthropic":
        from langchain_anthropic import ChatAnthropic

        return ChatAnthropic(model=model, temperature=0)

    from langchain_openai import ChatOpenAI

    return ChatOpenAI(model=model, temperature=0)


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


