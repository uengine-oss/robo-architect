"""Tests for the PRD↔CLAUDE / PRD↔.cursorrules split lint (T057, US6)."""
from __future__ import annotations

import pytest

from api.features.prd_generation.prd_split_lint import (
    PrdSplitLintError,
    lint_disjoint,
)


_CLEAN_PRD = """# my-project

## Technology Stack

| Component | Choice |
|-----------|--------|
| Language  | Python |

## Bounded Contexts

| BC | Aggregates |
|----|------------|
| Order | 3 |

See `CLAUDE.md` for the engineering constitution.
"""

_CLEAN_CLAUDE = """# CLAUDE.md - AI Assistant Constitution

> The engineering rules for this project. See `PRD.md` for the project composition.

## Read Order

Reference these skills before writing any code:
- `.claude/skills/ddd-principles.md`
- `.claude/skills/eventstorming-implementation.md`
"""


def test_clean_disjoint_files_pass():
    lint_disjoint(_CLEAN_PRD, _CLEAN_CLAUDE, constitution_filename="CLAUDE.md")
    # No exception → pass.


def test_imperative_in_prd_body_fails():
    bad_prd = _CLEAN_PRD + "\n## How to Implement\n\nYou MUST read CLAUDE.md before starting.\n"
    with pytest.raises(PrdSplitLintError) as exc_info:
        lint_disjoint(bad_prd, _CLEAN_CLAUDE, constitution_filename="CLAUDE.md")
    err = exc_info.value
    assert err.code == "prd_split_lint_failed"
    assert err.offending_file == "PRD.md"
    # The match returned could be MUST or "Before starting" depending on
    # which the regex saw first — both are valid imperatives.
    assert err.offending_substring.upper() in {"MUST", "BEFORE STARTING", "SHALL", "🚨", "CRITICAL"}


def test_imperative_inside_fenced_code_block_allowed():
    """Fenced code blocks can document downstream contracts using MUST/SHALL."""
    prd_with_code = _CLEAN_PRD + """

## EARS Examples

```
WHEN customer confirms IF cart is not empty THEN system SHALL create order
```
"""
    lint_disjoint(prd_with_code, _CLEAN_CLAUDE, constitution_filename="CLAUDE.md")


def test_imperative_inside_table_cell_allowed():
    """Table cells documenting contracts can carry MUST/SHALL."""
    prd_with_table = _CLEAN_PRD + """

## Endpoint Contracts

| Endpoint | Behaviour |
|----------|-----------|
| `/api/x` | MUST return 200 on success |
"""
    lint_disjoint(prd_with_table, _CLEAN_CLAUDE, constitution_filename="CLAUDE.md")


def test_inventory_table_in_claude_fails():
    bad_claude = _CLEAN_CLAUDE + "\n## Technology Stack\n\n| Component | Choice |\n|-----------|--------|\n"
    with pytest.raises(PrdSplitLintError) as exc_info:
        lint_disjoint(_CLEAN_PRD, bad_claude, constitution_filename="CLAUDE.md")
    err = exc_info.value
    assert err.code == "prd_split_lint_failed"
    assert err.offending_file == "CLAUDE.md"
    assert "Technology Stack" in err.offending_substring


def test_inventory_table_in_cursorrules_fails():
    bad_cursorrules = "## Bounded Contexts\n\n| BC | Aggregates |\n|----|------------|\n"
    with pytest.raises(PrdSplitLintError) as exc_info:
        lint_disjoint(_CLEAN_PRD, bad_cursorrules, constitution_filename=".cursorrules")
    err = exc_info.value
    assert err.offending_file == ".cursorrules"
    assert "Bounded Contexts" in err.offending_substring


def test_pointer_lines_allowed_in_both_files():
    """Both files can reference each other via plain pointer lines."""
    prd = "# my-project\n\nSee `CLAUDE.md` for the constitution.\n"
    claude = "# CLAUDE.md\n\nSee `PRD.md` for the inventory.\n"
    lint_disjoint(prd, claude, constitution_filename="CLAUDE.md")


def test_critical_marker_in_prd_fails():
    bad_prd = _CLEAN_PRD + "\n## 🚨 CRITICAL: Before Starting Implementation\n\nRead this first.\n"
    with pytest.raises(PrdSplitLintError):
        lint_disjoint(bad_prd, _CLEAN_CLAUDE, constitution_filename="CLAUDE.md")
