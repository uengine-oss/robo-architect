"""
LangChain cache toggling (feature-local).

This mirrors robo-architect's ability to speed up repeated extractions by enabling a SQLite cache.

Default behavior: cache is **on** by default during ingestion (env-flag overridable
via `INGESTION_CACHE_DEFAULT=0`). Call `ensure_default_cache_state()` once at
process startup (e.g. from FastAPI lifespan) so the default takes effect.
"""

from __future__ import annotations

from pathlib import Path
from api.platform.env import env_flag
from api.platform.observability.smart_logger import SmartLogger

_cache_enabled = False
_default_applied = False


def enable_langchain_cache() -> bool:
    """Enable LangChain SQLite cache for faster repeated LLM calls."""
    global _cache_enabled
    if _cache_enabled:
        return True

    try:
        from langchain_community.cache import SQLiteCache
        from langchain_core.globals import set_llm_cache
    except Exception:
        # Optional dependency; fail gracefully
        SmartLogger.log("ERROR", "Failed to enable LangChain cache", category="ingestion")
        return False

    try:
        cache_dir = Path(__file__).resolve().parent / ".cache"
        cache_dir.mkdir(exist_ok=True)
        cache_file = cache_dir / "langchain_cache.db"
        set_llm_cache(SQLiteCache(database_path=str(cache_file)))
        _cache_enabled = True
        return True
    except Exception:
        return False


def disable_langchain_cache() -> bool:
    """Disable LangChain cache."""
    global _cache_enabled
    try:
        from langchain_core.globals import set_llm_cache
    except Exception:
        _cache_enabled = False
        return True

    try:
        set_llm_cache(None)
        _cache_enabled = False
        return True
    except Exception:
        return False


def is_cache_enabled() -> bool:
    return _cache_enabled


def ensure_default_cache_state() -> bool:
    """Apply the env-driven default exactly once at process startup.

    Default: ON (cache enabled). Override with `INGESTION_CACHE_DEFAULT=0` in
    environment to start with cache off.

    Idempotent: subsequent calls are no-ops. Manual `enable_langchain_cache()` /
    `disable_langchain_cache()` calls (e.g. via the /api/ingest/cache/* router
    endpoints) take precedence after startup.
    """
    global _default_applied
    if _default_applied:
        return _cache_enabled
    _default_applied = True
    default_on = env_flag("INGESTION_CACHE_DEFAULT", True)
    if default_on:
        ok = enable_langchain_cache()
        SmartLogger.log(
            "INFO",
            f"Ingestion cache default state applied: enabled={ok}",
            category="ingestion.cache.default",
            params={"default": True, "enabled": _cache_enabled},
        )
        return ok
    SmartLogger.log(
        "INFO",
        "Ingestion cache default state applied: disabled (INGESTION_CACHE_DEFAULT=0)",
        category="ingestion.cache.default",
        params={"default": False, "enabled": False},
    )
    return False


