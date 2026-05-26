"""Per-scope coverage cache (030 — clarity radar fidelity).

The deep agent's `submit_clarification_questions` tool returns a `coverage`
list with `CoverageStatus` (Clear / Resolved / Deferred / Outstanding) per
category — the SpecKit `/speckit-clarify` skill's step-8 reporting model.

Before this module, that coverage was being thrown away after the route
displayed the question queue. We now cache the most-recent coverage per
scope so the clarity radar can score categories with the skill's intended
4-state weighting (Clear/Resolved=1.0, Deferred=0.5, Outstanding=0.0)
instead of the cruder "any flagged?" binary.

This is purely a derived/cache layer — no persistence. Same lifecycle as
the in-memory session store and the flag tracker.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

from api.features.requirements.clarification_contracts import (
    AmbiguityCategory,
    CoverageRow,
    CoverageStatus,
)


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class ScopeCoverage:
    """The most-recent coverage map the agent produced for one scope."""

    scopeType: str
    scopeId: str
    sessionId: str
    rows: dict[AmbiguityCategory, CoverageStatus] = field(default_factory=dict)
    capturedAt: str = field(default_factory=_utcnow)

    def merge_row(self, row: CoverageRow) -> None:
        """Upgrade-only merge: never *downgrade* a category to Outstanding
        once it has been Resolved. The skill's model treats Resolved as
        sticky for the current scope until a re-scan finds new gaps."""
        prev = self.rows.get(row.category)
        if prev == CoverageStatus.resolved and row.status in (
            CoverageStatus.outstanding,
            CoverageStatus.deferred,
        ):
            return
        self.rows[row.category] = row.status


# Cache keyed by `{scopeType}:{scopeId}`.
_COVERAGE: dict[str, ScopeCoverage] = {}
_LOCK = threading.Lock()


def _key(scope_type: str, scope_id: str) -> str:
    return f"{scope_type}:{scope_id}"


def record_coverage(
    *,
    session_id: str,
    scope_type: str,
    scope_id: str,
    rows: list[CoverageRow],
) -> None:
    """Cache the agent's coverage result for a scope.

    "Resolved" is sticky across sessions for the same scope (SKILL.md
    step 8 — `Resolved = was Partial/Missing and addressed`; a follow-up
    scan that re-detects Outstanding doesn't unmake the past resolution).
    Other statuses are overwritten by the most recent scan.
    """
    if not rows:
        return
    with _LOCK:
        k = _key(scope_type, scope_id)
        prev = _COVERAGE.get(k)
        # Preserve sticky Resolved entries when starting a fresh session
        # entry for this scope.
        carryover: dict[AmbiguityCategory, CoverageStatus] = {}
        if prev is not None:
            carryover = {
                c: s for c, s in prev.rows.items() if s == CoverageStatus.resolved
            }
        if prev is None or prev.sessionId != session_id:
            prev = ScopeCoverage(
                scopeType=scope_type, scopeId=scope_id, sessionId=session_id
            )
            # Re-seed with the sticky resolves from previous sessions.
            prev.rows.update(carryover)
            _COVERAGE[k] = prev
        for row in rows:
            prev.merge_row(row)
        prev.capturedAt = _utcnow()


def get_coverage(scope_type: str, scope_id: str) -> Optional[ScopeCoverage]:
    with _LOCK:
        return _COVERAGE.get(_key(scope_type, scope_id))


def mark_resolved(scope_type: str, scope_id: str, category: AmbiguityCategory) -> None:
    """Upgrade a category to Resolved after a successful `/apply` — sticky."""
    with _LOCK:
        k = _key(scope_type, scope_id)
        cov = _COVERAGE.get(k)
        if cov is None:
            return
        cov.rows[category] = CoverageStatus.resolved
        cov.capturedAt = _utcnow()


def clear_scope(scope_type: str, scope_id: str) -> None:
    with _LOCK:
        _COVERAGE.pop(_key(scope_type, scope_id), None)
