"""
LangChain cache toggling (feature-local).

This mirrors robo-architect's ability to speed up repeated extractions by enabling a SQLite cache.
"""

from __future__ import annotations

from pathlib import Path

_cache_enabled = False


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


