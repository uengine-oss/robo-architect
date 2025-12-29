"""
Shared environment variable helpers and commonly-used flags.

Goal: centralize env parsing rules (truthy handling, stripping, fallbacks) so
feature modules can import consistent behavior instead of duplicating logic.
"""

from __future__ import annotations

import os
from typing import Iterable

_TRUE_VALUES = {"1", "true", "yes", "y", "on"}


def env_str(key: str, default: str | None = None, *, strip: bool = True) -> str | None:
    """Read an environment variable as string with optional stripping."""
    val = os.getenv(key)
    if val is None:
        return default
    if strip:
        val = val.strip()
    return val if val != "" else default


def env_first(keys: Iterable[str], default: str | None = None, *, strip: bool = True) -> str | None:
    """Return the first non-empty environment variable value from keys."""
    for key in keys:
        val = env_str(key, None, strip=strip)
        if val is not None:
            return val
    return default


def env_flag(key: str, default: bool = False) -> bool:
    """Read an environment variable as a boolean flag."""
    val = (os.getenv(key) or "").strip().lower()
    if not val:
        return default
    return val in _TRUE_VALUES


# =============================================================================
# Common cross-feature configuration getters
# =============================================================================

def get_llm_provider(default: str = "openai") -> str:
    """Get configured LLM provider (e.g. 'openai', 'anthropic')."""
    return env_str("LLM_PROVIDER", default) or default


def get_llm_model(default: str = "gpt-4o") -> str:
    """Get configured LLM model name."""
    return env_str("LLM_MODEL", default) or default


def get_llm_provider_model(
    provider_default: str = "openai",
    model_default: str = "gpt-4o",
) -> tuple[str, str]:
    """Get configured LLM (provider, model) tuple."""
    return get_llm_provider(provider_default), get_llm_model(model_default)


def get_neo4j_uri(default: str = "bolt://localhost:7687") -> str:
    return env_str("NEO4J_URI", default) or default


def get_neo4j_user(default: str = "neo4j") -> str:
    return env_str("NEO4J_USER", default) or default


def get_neo4j_password(default: str = "12345msaez") -> str:
    return env_str("NEO4J_PASSWORD", default) or default


def get_neo4j_database() -> str | None:
    """Get target Neo4j database name (supports legacy 'neo4j_database')."""
    db = env_first(["NEO4J_DATABASE", "neo4j_database"], default=None)
    return (db or "").strip() or None


# =============================================================================
# Common cross-feature flags
# =============================================================================

# LLM Audit Logging (prompt/output + performance)
AI_AUDIT_LOG_ENABLED = env_flag("AI_AUDIT_LOG_ENABLED", True)
AI_AUDIT_LOG_FULL_PROMPT = env_flag("AI_AUDIT_LOG_FULL_PROMPT", False)
AI_AUDIT_LOG_FULL_OUTPUT = env_flag("AI_AUDIT_LOG_FULL_OUTPUT", False)


