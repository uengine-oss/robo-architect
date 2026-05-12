"""Lint the PRD↔CLAUDE / PRD↔.cursorrules content split (FR-022, research D9).

The contract: ``PRD.md`` is purely compositional (project name, stack
table, BC inventory, file index, deployment view, pointers). The
prescriptive constitution (read-order, DDD principles, EARS rules, GWT
obligation, "🚨 CRITICAL"-style imperative blocks) lives in
``CLAUDE.md`` (when ``ai_assistant=claude``) or ``.cursorrules`` (when
``ai_assistant=cursor``). The split is enforced at zip-build time —
violation is a hard abort (HTTP 500 with ``prd_split_lint_failed``), not
a warning. Soft warning would let drift accumulate silently.

The boundary heuristic:

- ``PRD.md`` body MUST NOT contain prescriptive imperatives outside
  fenced code blocks and markdown table cells. Imperatives inside
  triple-backtick fenced code (e.g. example EARS lines) and inside table
  rows (``| MUST ... |``) are allowed because they document downstream
  *contracts*, not directly-prescribed engineer behaviour.
- ``CLAUDE.md`` / ``.cursorrules`` MUST NOT restate the ``## Technology
  Stack`` table or the ``## Bounded Contexts`` inventory — they may
  *reference* PRD.md via pointer lines.

If either rule is violated, raise :class:`PrdSplitLintError` and the
caller aborts the zip with ``prd_split_lint_failed``.
"""
from __future__ import annotations

import re

from api.platform.observability.smart_logger import SmartLogger


# Imperative regex. ``\b`` boundaries + case-insensitive. Hits the keywords
# the user named as "constitution-like" content the split is supposed to
# move out of PRD.md.
_IMPERATIVE_RE = re.compile(
    r"\b(MUST NOT|SHALL NOT|MUST|SHALL|REQUIRED|Before starting|🚨|CRITICAL)\b",
    flags=re.IGNORECASE,
)

# Table-header regex for the inventory tables CLAUDE.md / .cursorrules
# MUST NOT restate.
_INVENTORY_TABLE_RE = re.compile(
    r"^##\s+(Technology Stack|Bounded Contexts)\s*$",
    flags=re.MULTILINE,
)


class PrdSplitLintError(Exception):
    """Raised when the PRD↔CLAUDE / PRD↔.cursorrules contract is violated."""

    def __init__(
        self,
        code: str,
        offending_file: str,
        offending_substring: str,
        offset: int,
        message: str | None = None,
    ) -> None:
        self.code = code
        self.offending_file = offending_file
        self.offending_substring = offending_substring
        self.offset = offset
        super().__init__(
            message
            or f"{code}: {offending_file!r} contains {offending_substring!r} at offset {offset}."
        )


def _strip_safe_zones(text: str) -> str:
    """Replace fenced code blocks and markdown table rows with whitespace
    of the same length so offsets in the *original* text remain valid for
    error reporting, but the imperative regex can't trip on contents that
    were placed in those zones deliberately (example EARS lines, contract
    tables documenting downstream MUST/SHALL behaviour).
    """
    # Fenced code blocks: ```...``` (greedy across newlines).
    def _blank(m: re.Match) -> str:
        return " " * (m.end() - m.start())

    text = re.sub(r"```.*?```", _blank, text, flags=re.DOTALL)
    # Markdown table rows: a line starting with `|` and containing at
    # least one more `|`. Each is replaced with spaces so any imperative
    # word inside a table cell is ignored.
    text = re.sub(r"^\|.*\|.*$", _blank, text, flags=re.MULTILINE)
    return text


def _lint_prd_md(prd_text: str, filename: str = "PRD.md") -> None:
    """Reject prescriptive imperatives in PRD.md body."""
    stripped = _strip_safe_zones(prd_text)
    m = _IMPERATIVE_RE.search(stripped)
    if m is None:
        return
    # Report the offending substring + offset in the *original* text so the
    # user can grep to find it.
    offset = m.start()
    raise PrdSplitLintError(
        code="prd_split_lint_failed",
        offending_file=filename,
        offending_substring=prd_text[offset : offset + len(m.group(0))],
        offset=offset,
        message=(
            f"PRD.md contains prescriptive imperative {m.group(0)!r} at offset {offset}; "
            f"move it to CLAUDE.md / .cursorrules."
        ),
    )


def _lint_constitution(text: str, filename: str) -> None:
    """Reject inventory/stack-table restatement in CLAUDE.md / .cursorrules."""
    m = _INVENTORY_TABLE_RE.search(text)
    if m is None:
        return
    offset = m.start()
    raise PrdSplitLintError(
        code="prd_split_lint_failed",
        offending_file=filename,
        offending_substring=m.group(0),
        offset=offset,
        message=(
            f"{filename} restates the {m.group(1)!r} section that belongs in PRD.md; "
            f"reference PRD.md instead of duplicating."
        ),
    )


def lint_disjoint(
    prd_text: str,
    constitution_text: str,
    *,
    constitution_filename: str,
    prd_filename: str = "PRD.md",
) -> None:
    """Run the full disjointness lint. Raises :class:`PrdSplitLintError` on failure.

    Args:
        prd_text: rendered ``PRD.md`` body.
        constitution_text: rendered ``CLAUDE.md`` or ``.cursorrules`` body.
        constitution_filename: ``"CLAUDE.md"`` or ``".cursorrules"`` for
            error reporting.
        prd_filename: defaults to ``"PRD.md"``; override only for testing.
    """
    _lint_prd_md(prd_text, filename=prd_filename)
    _lint_constitution(constitution_text, filename=constitution_filename)
    SmartLogger.log(
        "INFO",
        "PRD↔constitution split lint passed.",
        category="prd.split_lint.passed",
        params={
            "prd_file": prd_filename,
            "constitution_file": constitution_filename,
            "prd_chars": len(prd_text),
            "constitution_chars": len(constitution_text),
        },
    )
