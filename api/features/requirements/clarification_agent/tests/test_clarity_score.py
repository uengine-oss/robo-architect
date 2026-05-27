"""Tests for clarity scoring + SKILL.md-aligned 4-state weighting (030)."""

from __future__ import annotations

from unittest import mock

import pytest

from api.features.requirements.clarification_agent import clarification_coverage as cov
from api.features.requirements.clarification_agent import clarification_flags as flags
from api.features.requirements.clarification_agent import clarity_score as cs
from api.features.requirements.clarification_contracts import (
    AmbiguityCategory,
    CoverageRow,
    CoverageStatus,
)


@pytest.fixture(autouse=True)
def _isolate(monkeypatch):
    """Each test starts with empty caches + log."""
    monkeypatch.setattr(flags, "_FLAGS", {})
    monkeypatch.setattr(cov, "_COVERAGE", {})
    monkeypatch.setattr(cs, "read_scope_log", lambda _ids: [])
    yield


def _row(cat: AmbiguityCategory, status: CoverageStatus) -> CoverageRow:
    return CoverageRow(category=cat, status=status)


# ── SKILL.md step-8 weight model ────────────────────────────────────────


def test_weights_match_skill_step_8() -> None:
    """Skill: Clear/Resolved = sufficient; Deferred = on-deck; Outstanding = worst."""
    assert cs.STATUS_WEIGHT[CoverageStatus.clear] == 1.0
    assert cs.STATUS_WEIGHT[CoverageStatus.resolved] == 1.0
    assert cs.STATUS_WEIGHT[CoverageStatus.deferred] == 0.5
    assert cs.STATUS_WEIGHT[CoverageStatus.outstanding] == 0.0


# ── Coverage cache lifecycle ────────────────────────────────────────────


def test_record_coverage_stores_per_scope() -> None:
    cov.record_coverage(
        session_id="s1", scope_type="project", scope_id="*",
        rows=[
            _row(AmbiguityCategory.non_functional, CoverageStatus.outstanding),
            _row(AmbiguityCategory.edge_cases, CoverageStatus.deferred),
        ],
    )
    snap = cov.get_coverage("project", "*")
    assert snap.rows[AmbiguityCategory.non_functional] == CoverageStatus.outstanding
    assert snap.rows[AmbiguityCategory.edge_cases] == CoverageStatus.deferred


def test_mark_resolved_upgrade_is_sticky() -> None:
    cov.record_coverage(
        session_id="s1", scope_type="project", scope_id="*",
        rows=[_row(AmbiguityCategory.non_functional, CoverageStatus.outstanding)],
    )
    cov.mark_resolved("project", "*", AmbiguityCategory.non_functional)
    # Now another scan reports Outstanding for the same category — must NOT
    # downgrade. (skill: Resolved is sticky for this scope.)
    cov.record_coverage(
        session_id="s2", scope_type="project", scope_id="*",
        rows=[_row(AmbiguityCategory.non_functional, CoverageStatus.outstanding)],
    )
    snap = cov.get_coverage("project", "*")
    assert snap.rows[AmbiguityCategory.non_functional] == CoverageStatus.resolved


# ── Scope-aware scoring overlays the cached coverage ───────────────────


def test_scope_scoring_uses_cached_coverage() -> None:
    cov.record_coverage(
        session_id="s1", scope_type="project", scope_id="*",
        rows=[
            _row(AmbiguityCategory.functional_scope, CoverageStatus.clear),
            _row(AmbiguityCategory.non_functional, CoverageStatus.deferred),
            _row(AmbiguityCategory.edge_cases, CoverageStatus.outstanding),
        ],
    )
    out = cs.compute_clarity_scores_for_scope(["us-1", "us-2"], "project", "*")
    by_cat = {s.category: s for s in out.scores}
    assert by_cat[AmbiguityCategory.functional_scope].score == 1.0
    assert by_cat[AmbiguityCategory.functional_scope].status == CoverageStatus.clear
    assert by_cat[AmbiguityCategory.non_functional].score == 0.5
    assert by_cat[AmbiguityCategory.non_functional].status == CoverageStatus.deferred
    assert by_cat[AmbiguityCategory.edge_cases].score == 0.0
    assert by_cat[AmbiguityCategory.edge_cases].status == CoverageStatus.outstanding
    # Categories not in the cache fall back to neutral (no flag → 1.0, status=None).
    assert by_cat[AmbiguityCategory.terminology].status is None
    assert by_cat[AmbiguityCategory.terminology].score == 1.0


def test_scope_scoring_no_cache_falls_back_to_flags() -> None:
    """Cold-start: no agent scan yet — score from in-memory flags only."""
    flags.record_flags(
        session_id="s1", scope_type="project", scope_id="*",
        questions=[{
            "questionId": "q-1",
            "category": "edge_cases",
            "referencedRequirementIds": ["us-1"],
        }],
    )
    out = cs.compute_clarity_scores_for_scope(["us-1", "us-2"], "project", "*")
    by_cat = {s.category: s for s in out.scores}
    # Flag-derived fallback uses status=Outstanding for any flagged category.
    assert by_cat[AmbiguityCategory.edge_cases].score == 0.0
    assert by_cat[AmbiguityCategory.edge_cases].status == CoverageStatus.outstanding
    # Categories not flagged stay at 1.0 with status=None (no signal).
    assert by_cat[AmbiguityCategory.functional_scope].status is None


def test_empty_scope_yields_max_scores() -> None:
    out = cs.compute_clarity_scores_for_scope([], "project", "*")
    assert out.totalUserStories == 0
    assert all(s.score == 1.0 for s in out.scores)
    assert all(s.status is None for s in out.scores)


def test_clear_scope_drops_cache() -> None:
    cov.record_coverage(
        session_id="s1", scope_type="feature", scope_id="f-1",
        rows=[_row(AmbiguityCategory.non_functional, CoverageStatus.outstanding)],
    )
    assert cov.get_coverage("feature", "f-1") is not None
    cov.clear_scope("feature", "f-1")
    assert cov.get_coverage("feature", "f-1") is None
