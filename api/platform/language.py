"""
Per-request generation language (feature 031).

Holds the user-selected output language tag (BCP-47, e.g. "ko-KR") for the
duration of a single inbound HTTP request. Consumed by the shared
SystemMessage builder in `api.platform.llm_messages` so every LLM-generated
natural-language artifact comes back in the requested language without each
generation feature threading the value through its own call chain.

Set by `api.platform.middleware.language_middleware` at the request boundary;
read by `build_system_message` deep inside any feature module. ContextVar
isolation guarantees no leakage between concurrent requests.

Mirrors the pattern of `_request_id_var` in
`api.platform.observability.request_logging` — see that module for the
underlying motivation. Fallback when the var is unset comes from the
`GENERATION_LANGUAGE_DEFAULT` env var (default "en-US"), so calls outside
the HTTP request scope (e.g. one-off scripts) still get a deterministic value.
"""

from __future__ import annotations

import contextvars
import os

# Sentinel default for callers that bypass middleware (CLI scripts, MCP bridges,
# direct curl without Accept-Language). Resolved at read time so an operator
# can override per-deployment without code changes — see spec FR-010 / research D2.
ENV_DEFAULT_LANGUAGE_KEY = "GENERATION_LANGUAGE_DEFAULT"
HARDCODED_FALLBACK_LANGUAGE = "en-US"


_request_language_var: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "request_language", default=None
)


def set_request_language(tag: str | None) -> None:
    """Store the (already-normalized) language tag for the current async context.

    Pass `None` to clear. Called by the language middleware once per request.
    """
    _request_language_var.set(tag)


def get_request_language() -> str:
    """Return the active language tag.

    Resolution order:
      1. ContextVar value if set by middleware for the current request.
      2. `os.environ[GENERATION_LANGUAGE_DEFAULT]` if non-empty.
      3. Hard-coded fallback `"en-US"`.

    Always returns a non-empty string — never `None`. Callers can use the
    return value directly in prompt construction without further checks.
    """
    val = _request_language_var.get()
    if val:
        return val
    env_default = os.environ.get(ENV_DEFAULT_LANGUAGE_KEY, "").strip()
    if env_default:
        return env_default
    return HARDCODED_FALLBACK_LANGUAGE


def clear_request_language() -> None:
    """Convenience alias for `set_request_language(None)`."""
    _request_language_var.set(None)
