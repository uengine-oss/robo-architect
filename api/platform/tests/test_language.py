"""Unit tests for api.platform.language (feature 031)."""

from __future__ import annotations

import asyncio

import pytest

from api.platform.language import (
    ENV_DEFAULT_LANGUAGE_KEY,
    HARDCODED_FALLBACK_LANGUAGE,
    clear_request_language,
    get_request_language,
    set_request_language,
)


@pytest.fixture(autouse=True)
def _isolate_contextvar(monkeypatch):
    """Reset both the ContextVar and the env var around each test."""
    monkeypatch.delenv(ENV_DEFAULT_LANGUAGE_KEY, raising=False)
    clear_request_language()
    yield
    clear_request_language()


def test_get_returns_hardcoded_fallback_when_unset():
    assert get_request_language() == HARDCODED_FALLBACK_LANGUAGE  # "en-US"


def test_get_returns_env_default_when_var_unset(monkeypatch):
    monkeypatch.setenv(ENV_DEFAULT_LANGUAGE_KEY, "ko-KR")
    assert get_request_language() == "ko-KR"


def test_get_returns_var_when_set_even_with_env(monkeypatch):
    """Per-request value wins over the deployment default."""
    monkeypatch.setenv(ENV_DEFAULT_LANGUAGE_KEY, "ko-KR")
    set_request_language("ja-JP")
    assert get_request_language() == "ja-JP"


def test_clear_falls_back_to_env(monkeypatch):
    monkeypatch.setenv(ENV_DEFAULT_LANGUAGE_KEY, "ko-KR")
    set_request_language("en-US")
    clear_request_language()
    assert get_request_language() == "ko-KR"


def test_clear_falls_back_to_hardcoded():
    set_request_language("fr-FR")
    clear_request_language()
    assert get_request_language() == HARDCODED_FALLBACK_LANGUAGE


def test_empty_env_default_uses_hardcoded(monkeypatch):
    monkeypatch.setenv(ENV_DEFAULT_LANGUAGE_KEY, "   ")  # whitespace-only
    assert get_request_language() == HARDCODED_FALLBACK_LANGUAGE


def test_contextvar_isolation_between_async_tasks():
    """Concurrent async tasks must not leak language values into each other.

    Each task sets its own tag, awaits a yield point so they interleave, and
    then reads back its tag. Mutations made inside one task's context don't
    propagate to the parent or to sibling tasks — that's the property the
    request middleware depends on.
    """
    import contextvars

    observed: dict[str, str] = {}

    async def task(name: str, tag: str):
        set_request_language(tag)
        await asyncio.sleep(0)  # interleave with other tasks
        observed[name] = get_request_language()

    async def run_with_fresh_context(coro):
        # Each "request" gets a fresh ContextVar copy, like Starlette does.
        ctx = contextvars.copy_context()
        await asyncio.create_task(coro, context=ctx)

    async def driver():
        await asyncio.gather(
            run_with_fresh_context(task("a", "ko-KR")),
            run_with_fresh_context(task("b", "ja-JP")),
            run_with_fresh_context(task("c", "en-US")),
        )

    asyncio.run(driver())
    assert observed == {"a": "ko-KR", "b": "ja-JP", "c": "en-US"}
    # And the driver's own context was never mutated by any task:
    assert get_request_language() == HARDCODED_FALLBACK_LANGUAGE
