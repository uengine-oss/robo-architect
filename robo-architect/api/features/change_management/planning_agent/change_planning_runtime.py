"""
Change Planning Runtime (LLM / embeddings / Neo4j access)

Business capability: provide the integrations needed by change planning nodes.
Kept local to the change planning feature implementation.
"""

from __future__ import annotations

from api.platform.env import (
    get_llm_provider_model,
    get_neo4j_database as get_env_neo4j_database,
    get_neo4j_password,
    get_neo4j_uri,
    get_neo4j_user,
)


def get_llm():
    """Get the configured LLM instance."""
    provider, model = get_llm_provider_model()

    if provider == "anthropic":
        from langchain_anthropic import ChatAnthropic

        return ChatAnthropic(model=model, temperature=0)
    else:
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(model=model, temperature=0)


def get_embeddings():
    """Get the embeddings model."""
    from langchain_openai import OpenAIEmbeddings

    return OpenAIEmbeddings(model="text-embedding-3-small")


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


