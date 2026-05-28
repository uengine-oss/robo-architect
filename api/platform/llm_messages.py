"""
Shared SystemMessage builder (feature 031 chokepoint).

Single sanctioned construction site for `langchain_core.messages.SystemMessage`
inside `api/features/`. Every feature module MUST build its system messages
via `build_system_message(content)` — direct `SystemMessage(content=...)`
calls are forbidden in `api/features/` and enforced by the AST regression
test at `api/tests/regression/test_language_chokepoint.py`.

Why centralized: the spec's per-request output-language policy (FR-005…FR-009)
appends a "Respond in {tag}" directive to every system message. Doing this
in one place — instead of 70+ call sites — means new generation features
inherit the policy with zero language-handling code, and a wording tweak
later happens in one file.
"""

from __future__ import annotations

from langchain_core.messages import SystemMessage

from api.platform.language import get_request_language


# Centralised directive wording. Edit here to change the instruction across
# every generation path system-wide. Kept short (~25 tokens) to minimise
# per-call token overhead.
LANGUAGE_DIRECTIVE_TEMPLATE = (
    "Respond in {tag} for all natural-language content. "
    "Preserve verbatim any domain identifiers and user-supplied labels."
)


def build_system_message(
    content: str,
    *,
    _skip_language_directive: bool = False,
) -> SystemMessage:
    """Construct a SystemMessage with the per-request language directive appended.

    The caller's `content` is preserved verbatim at the front of the message;
    the directive trails after a blank line so it cannot displace the caller's
    primary instructions.

    Args:
        content: The feature's own system prompt (a string).
        _skip_language_directive: Test-only escape hatch for fixtures that
            need byte-deterministic system-message strings. **Forbidden in
            `api/features/` code** — the AST regression test fails the build
            if it spots this kwarg outside `api/tests/`.

    Returns:
        A `langchain_core.messages.SystemMessage` ready to pass into any
        provider-agnostic `llm.invoke([...])` call.
    """
    if _skip_language_directive:
        return SystemMessage(content=content)

    tag = get_request_language()
    directive = LANGUAGE_DIRECTIVE_TEMPLATE.format(tag=tag)
    return SystemMessage(content=f"{content}\n\n{directive}")
