"""
Shared environment variable helpers and commonly-used flags.

Goal: centralize env parsing rules (truthy handling, stripping, fallbacks) so
feature modules can import consistent behavior instead of duplicating logic.

LLM configuration (used via `api.platform.llm`):
- LLM_PROVIDER: openai | anthropic | google (aliases: gemini, google-genai, google_genai)
- LLM_MODEL: required for anthropic/google; optional for openai (defaults to gpt-4.1-2025-04-14)
- API keys: OPENAI_API_KEY | ANTHROPIC_API_KEY | GOOGLE_API_KEY
"""

from __future__ import annotations

import ast
import json
import os
from typing import Any, Iterable

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


def env_json(key: str, default: Any = None) -> Any:
    """
    Read an environment variable and parse it as JSON.

    Notes:
    - Primarily expects valid JSON (e.g. {"temperature": 0.3}).
    - Falls back to Python literals via ast.literal_eval for convenience
      (e.g. {'temperature': 0.3}) if JSON parsing fails.
    """
    raw = env_str(key, default=None, strip=True)
    if raw is None:
        return default

    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        try:
            return ast.literal_eval(raw)
        except Exception as e:  # noqa: BLE001 - we re-raise as ValueError with context
            raise ValueError(
                f"Environment variable '{key}' must be valid JSON (or a Python literal). "
                f"Got: {raw!r}"
            ) from e


def env_dict(key: str, default: dict[str, Any] | None = None) -> dict[str, Any]:
    """Read an environment variable and parse it into a dictionary."""
    val = env_json(key, default=None)
    if val is None:
        return dict(default or {})
    if not isinstance(val, dict):
        raise ValueError(f"Environment variable '{key}' must be a JSON object/dict. Got: {type(val).__name__}")
    return val


# =============================================================================
# Common cross-feature configuration getters
# =============================================================================

def get_llm_provider(default: str = "openai") -> str:
    """Get configured LLM provider (e.g. 'openai', 'anthropic')."""
    return env_str("LLM_PROVIDER", default) or default


def get_llm_model(default: str = "gpt-4.1-2025-04-14") -> str:
    """Get configured LLM model name."""
    return env_str("LLM_MODEL", default) or default


def get_llm_provider_model(
    provider_default: str = "openai",
    model_default: str = "gpt-4.1-2025-04-14",
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

# Ingestion workflow: optional phase toggles
# - If True, skip Neo4j UI node creation + LLM wireframe generation phase.
IS_SKIP_UI_PHASE = env_flag("IS_SKIP_UI_PHASE", False)


