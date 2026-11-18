"""Tests for clarity scoring + SKILL.md-aligned 4-state weighting (030)."""

from __future__ import annotations

from unittest import mock

import pytest

from api.features.requirements.clarification_agent import clarification_coverage as cov
from api.features.requirements.clarification_agent import clarification_flags as flags
from api.features.requirements.clarification_agent import clarity_score as cs
from api.features.requirements.clarification_contracts import (
    AmbiguityCategory,
    ClarificationLogEntry,
    CoverageRow,
    CoverageStatus,
)


@pytest.fixture(autouse=True)
def _isolate(monkeypatch):
    """Each test starts with empty caches + log."""
    monkeypatch.setattr(flags, "_FLAGS", {})
    monkeypatch.setattr(cov, "_COVERAGE", {})
    monkeypatch.setattr(cs, "read_scope_log_with_story_ids", lambda _ids: [])
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
    assert by_cat[AmbiguityCategory.edge_cases].scanned is True
    # Categories not in the cache and without any flag/log signal are
    # *unknown* — not 1.0 (lite ⑯: "모름"을 "맑음"으로 그리지 않는다).
    assert by_cat[AmbiguityCategory.terminology].status is None
    assert by_cat[AmbiguityCategory.terminology].score is None
    assert by_cat[AmbiguityCategory.terminology].scanned is False
    # Header %: unscanned axes count as 0 → (1.0 + 0.5 + 0.0) / 10
    assert cs.overall_clarity(out) == 0.15


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
    # Categories not flagged have no signal → unscanned, score None (not 1.0).
    assert by_cat[AmbiguityCategory.functional_scope].status is None
    assert by_cat[AmbiguityCategory.functional_scope].score is None
    assert by_cat[AmbiguityCategory.functional_scope].scanned is False
    assert out.scanned is True
    assert out.flaggedUserStories == 1


def test_empty_scope_is_unscanned_not_full() -> None:
    """No target requirements → every axis unknown, no header % (was 100%)."""
    cov.record_coverage(
        session_id="s1", scope_type="project", scope_id="*",
        rows=[_row(AmbiguityCategory.functional_scope, CoverageStatus.clear)],
    )
    out = cs.compute_clarity_scores_for_scope([], "project", "*")
    assert out.totalUserStories == 0
    assert all(s.score is None for s in out.scores)
    assert all(s.status is None for s in out.scores)
    assert all(s.scanned is False for s in out.scores)
    assert out.scanned is False
    assert cs.overall_clarity(out) is None


def test_never_scanned_scope_is_unknown_not_clear() -> None:
    """Cold start (backend restarted, nothing scanned) must not read 100%."""
    out = cs.compute_clarity_scores_for_scope(["us-1", "us-2"], "project", "*")
    assert out.totalUserStories == 2
    assert all(s.score is None and s.scanned is False for s in out.scores)
    assert out.scanned is False
    assert cs.overall_clarity(out) is None


def _entry(session: str, question: str, cat: str, reverted: bool = False):
    snap = {"role": "", "action": "", "benefit": ""}
    return ClarificationLogEntry.model_validate({
        "sessionId": session, "questionId": question, "question": "q", "answer": "a",
        "category": cat, "before": snap, "after": snap, "at": "2026-11-16T00:00:00Z",
        "reverted": reverted,
    })


def test_resolved_counts_stories_sessions_and_questions(monkeypatch) -> None:
    """resolvedUserStories = distinct stories (was: distinct sessions)."""
    log = [
        ("us-1", _entry("s1", "q1", "edge_cases")),
        ("us-1", _entry("s1", "q2", "edge_cases")),
        ("us-2", _entry("s1", "q3", "terminology")),
        ("us-1", _entry("s2", "q1", "terminology")),
        ("us-2", _entry("s3", "q9", "edge_cases", reverted=True)),  # ignored
    ]
    monkeypatch.setattr(cs, "read_scope_log_with_story_ids", lambda _ids: log)
    out = cs.compute_clarity_scores_for_scope(["us-1", "us-2", "us-3"], "project", "*")
    assert out.resolvedUserStories == 2
    assert out.resolvedSessions == 2
    by_cat = {s.category: s for s in out.scores}
    # resolvedCount = answered questions (sessionId:questionId)
    assert by_cat[AmbiguityCategory.edge_cases].resolvedCount == 2
    assert by_cat[AmbiguityCategory.terminology].resolvedCount == 2
    assert by_cat[AmbiguityCategory.edge_cases].status == CoverageStatus.resolved
    assert by_cat[AmbiguityCategory.edge_cases].score == 1.0
    assert by_cat[AmbiguityCategory.edge_cases].scanned is True


def test_clear_scope_drops_cache() -> None:
    cov.record_coverage(
        session_id="s1", scope_type="feature", scope_id="f-1",
        rows=[_row(AmbiguityCategory.non_functional, CoverageStatus.outstanding)],
    )
    assert cov.get_coverage("feature", "f-1") is not None
    cov.clear_scope("feature", "f-1")
    assert cov.get_coverage("feature", "f-1") is None
