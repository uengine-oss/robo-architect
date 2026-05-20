"""Deterministic GWT → EARS transform. Per research D3.

The transform is purely structural; an optional grammar-smoothing hook
(``smoother``) may rewrite connective prose but must preserve all
load-bearing tokens (numbers, ``WHEN``/``IF``/``THEN``/``SHALL``
keywords, and referenced names).
"""
from __future__ import annotations

import re
from typing import Callable, Iterable, Optional

from api.features.ddd_spec.projection import GwtCriterion


_GIVEN_RE = re.compile(r"^\s*given\s+", re.IGNORECASE)
_WHEN_RE = re.compile(r"^\s*when\s+", re.IGNORECASE)
_THEN_RE = re.compile(r"^\s*then\s+", re.IGNORECASE)


def _strip_keyword(clause: str, pattern: re.Pattern[str]) -> str:
    return pattern.sub("", clause or "").strip().rstrip(".,;")


def gwt_to_ears(criterion: GwtCriterion) -> list[str]:
    """One GWT criterion → one or more EARS lines.

    - ``Given X, When Y, Then Z``      → ``WHEN Y IF X THEN system SHALL Z``
    - ``When Y, Then Z`` (no Given)    → ``WHEN Y THEN system SHALL Z``
    - Multiple ``Given`` joined with ``AND``.
    - Multiple ``Then`` → one ``SHALL`` line each.
    """
    givens = [_strip_keyword(g, _GIVEN_RE) for g in (criterion.given or []) if g and g.strip()]
    when = _strip_keyword(criterion.when, _WHEN_RE)
    thens = [_strip_keyword(t, _THEN_RE) for t in (criterion.then or []) if t and t.strip()]

    if not thens:
        return []
    if not when:
        # Defensive: a criterion with no When is non-EARS; render the obligations
        # as unconditional THE-style lines without aggregate context.
        return [f"the system SHALL {t}" for t in thens]

    prefix_parts = [f"WHEN {when}"]
    if givens:
        prefix_parts.append(f"IF {' AND '.join(givens)}")
    prefix = " ".join(prefix_parts) + " THEN"
    return [f"{prefix} system SHALL {t}" for t in thens]


def unconditional_invariant(aggregate_name: str, invariant: str) -> str:
    """Aggregate-level unconditional invariant → ``THE <Aggregate> SHALL <C>``."""
    text = (invariant or "").strip().rstrip(".")
    return f"THE {aggregate_name} SHALL {text}"


def aggregate_invariant_lines(
    aggregate_name: str,
    *,
    unconditional: Iterable[str],
    commands_gwt: Iterable[GwtCriterion],
    smoother: Optional[Callable[[list[str]], list[str]]] = None,
) -> list[str]:
    """Numbered EARS lines for an Aggregate's "Enforced Invariants" section.

    Order: unconditional invariants first (in graph order), then GWT criteria
    flattened in their appearance order. Numbering is the renderer's job —
    this function returns the lines themselves.
    """
    lines: list[str] = []
    for inv in unconditional:
        if inv and inv.strip():
            lines.append(unconditional_invariant(aggregate_name, inv))
    for crit in commands_gwt:
        lines.extend(gwt_to_ears(crit))
    if smoother is not None:
        lines = smoother(lines)
    return lines


def story_acceptance_lines(
    *,
    acceptance_criteria: Iterable[GwtCriterion],
    smoother: Optional[Callable[[list[str]], list[str]]] = None,
) -> list[str]:
    """EARS acceptance criteria for one User Story."""
    lines: list[str] = []
    for crit in acceptance_criteria:
        lines.extend(gwt_to_ears(crit))
    if smoother is not None:
        lines = smoother(lines)
    return lines
