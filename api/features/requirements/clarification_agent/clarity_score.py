"""Clarity scoring for the radar chart (030 — aligned with SKILL.md).

Now uses the SpecKit `/speckit-clarify` skill's prescribed 4-state model
(`.claude/skills/speckit-clarify/SKILL.md` step 8) instead of a binary
flagged-or-not signal.

For each category, the score is derived from the most recent agent
coverage row for the scope, weighted as:

  Clear        → 1.0   "already sufficient"        (no gap surfaced)
  Resolved     → 1.0   "was Partial/Missing → addressed in this session"
  Deferred     → 0.5   "exceeds quota OR better for planning phase"
                       — the gap exists but is on-deck, not unknown
  Outstanding  → 0.0   "still Partial/Missing but low impact" — worst

When no scan has run yet for a scope, we fall back to the in-memory flag
tracker + the persisted clarification log (anything flagged → 0.0
Outstanding, anything answered → 1.0 Resolved).

**No signal at all is "unknown", not "clear"** (lite ⑯): such a category is
returned with ``scanned=False`` and ``score=None`` — never 1.0. Earlier it got
a neutral 1.0, so a project that was never scanned (or whose in-memory scan
results were lost on a backend restart) drew a full polygon at 100%. The
same holds for an empty scope (no UserStories): every axis is unscanned.

The category-level radar polygon thus reflects the same model the agent
itself reports in its end-of-session summary — single source of truth.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from api.features.requirements.clarification_agent.clarification_coverage import (
    get_coverage,
)
from api.features.requirements.clarification_agent.clarification_flags import (
    snapshot as snapshot_flags,
)
from api.features.requirements.clarification_agent.clarification_log import (
    read_scope_log_with_story_ids,
)
from api.features.requirements.clarification_contracts import (
    AmbiguityCategory,
    ClarificationLogEntry,
    CoverageStatus,
)


# SKILL.md step-8 weights. Single source of truth — change here only.
STATUS_WEIGHT: dict[CoverageStatus, float] = {
    CoverageStatus.clear: 1.0,
    CoverageStatus.resolved: 1.0,
    CoverageStatus.deferred: 0.5,
    CoverageStatus.outstanding: 0.0,
}


@dataclass
class CategoryScore:
    category: AmbiguityCategory
    # None = unknown (never scanned / no signal) — NOT the same as 1.0 (clear).
    score: float | None
    status: CoverageStatus | None  # None = no scan yet for this scope
    flaggedCount: int
    # Number of answered clarification *questions* (sessionId:questionId) —
    # not a UserStory count.
    resolvedCount: int
    scanned: bool = False


@dataclass
class ClarityScores:
    totalUserStories: int
    flaggedUserStories: int
    # Distinct in-scope UserStories that received at least one applied
    # (non-reverted) clarification. (Earlier this was the number of distinct
    # *sessions* under this name.)
    resolvedUserStories: int
    # Distinct clarification sessions with at least one applied answer.
    resolvedSessions: int = 0
    scores: list[CategoryScore] = field(default_factory=list)

    @property
    def scanned(self) -> bool:
        """True when at least one category has a real signal."""
        return any(s.scanned for s in self.scores)


def _flagged_count_by_category(
    user_story_ids: set[str], flags: dict | None = None
) -> dict[AmbiguityCategory, int]:
    """For each category, count in-scope UserStories currently flagged."""
    # 플래그는 이제 그래프에서 읽는다(D-4 ①) — 호출마다 조회가 들므로 한 번 읽은 것을 넘겨받는다.
    flags = snapshot_flags() if flags is None else flags
    by_cat: dict[AmbiguityCategory, set[str]] = {c: set() for c in AmbiguityCategory}
    for us_id, info in flags.items():
        if us_id not in user_story_ids:
            continue
        for cat_name in info.categories or []:
            try:
                cat = AmbiguityCategory(cat_name)
            except (ValueError, TypeError):
                continue
            by_cat[cat].add(us_id)
    return {c: len(s) for c, s in by_cat.items()}


def _entry_category(entry: ClarificationLogEntry) -> AmbiguityCategory | None:
    if isinstance(entry.category, AmbiguityCategory):
        return entry.category
    try:
        return AmbiguityCategory(str(entry.category))
    except (ValueError, TypeError):
        return None


def _resolved_count_by_category(
    applied: list[tuple[str, ClarificationLogEntry]],
) -> dict[AmbiguityCategory, int]:
    """For each category, count applied (non-reverted) clarification questions."""
    by_cat: dict[AmbiguityCategory, set[str]] = {c: set() for c in AmbiguityCategory}
    for _us_id, entry in applied:
        cat = _entry_category(entry)
        if cat is None:
            continue
        by_cat[cat].add(f"{entry.sessionId}:{entry.questionId}")
    return {c: len(s) for c, s in by_cat.items()}


def _fallback_score(
    category: AmbiguityCategory, flagged_count: int, resolved_count: int
) -> tuple[float | None, CoverageStatus | None]:
    """When no scan coverage exists for the scope, infer a status from the
    flag tracker + log. Conservative — does not invent Clear; returns
    ``(None, None)`` for "unknown" so the radar can render it differently."""
    if flagged_count > 0:
        return 0.0, CoverageStatus.outstanding
    if resolved_count > 0:
        return 1.0, CoverageStatus.resolved
    return None, None  # unknown — no signal at all


def _unscanned(cat: AmbiguityCategory, flagged: int = 0, resolved: int = 0) -> CategoryScore:
    return CategoryScore(
        category=cat, score=None, status=None,
        flaggedCount=flagged, resolvedCount=resolved, scanned=False,
    )


def compute_clarity_scores(user_story_ids: list[str]) -> ClarityScores:
    """Compute per-category clarity scores for an in-scope set of UserStories.

    Score sources, in precedence order:
      1. Cached coverage from the most recent agent scan (4-state weighted)
         — overlaid by `compute_clarity_scores_for_scope`.
      2. Flag tracker + log (fallback, binary).
      3. Nothing → unscanned (score None).

    Inputs:
      user_story_ids: ids of UserStories considered in-scope (caller resolves
                      scope via tree_service).
    """
    id_set = {x for x in user_story_ids if x}
    total = len(id_set)
    if total == 0:
        # "대상 요구사항 없음" — nothing to be clear or unclear about.
        return ClarityScores(
            totalUserStories=0,
            flaggedUserStories=0,
            resolvedUserStories=0,
            resolvedSessions=0,
            scores=[_unscanned(c) for c in AmbiguityCategory],
        )

    flags = snapshot_flags()
    applied = [
        (us_id, e) for us_id, e in read_scope_log_with_story_ids(id_set) if not e.reverted
    ]
    flagged_n = _flagged_count_by_category(id_set, flags)
    resolved_n = _resolved_count_by_category(applied)
    flagged_total = sum(1 for us_id in id_set if us_id in flags)
    resolved_us_total = len({us_id for us_id, _e in applied})
    resolved_sessions = len({e.sessionId for _us_id, e in applied})

    scores: list[CategoryScore] = []
    for cat in AmbiguityCategory:
        score, status = _fallback_score(cat, flagged_n[cat], resolved_n[cat])
        if status is None:
            scores.append(_unscanned(cat, flagged_n[cat], resolved_n[cat]))
            continue
        scores.append(
            CategoryScore(
                category=cat,
                score=round(score, 3) if score is not None else None,
                status=status,
                flaggedCount=flagged_n[cat],
                resolvedCount=resolved_n[cat],
                scanned=True,
            )
        )

    return ClarityScores(
        totalUserStories=total,
        flaggedUserStories=flagged_total,
        resolvedUserStories=resolved_us_total,
        resolvedSessions=resolved_sessions,
        scores=scores,
    )


def compute_clarity_scores_for_scope(
    user_story_ids: list[str], scope_type: str, scope_id: str
) -> ClarityScores:
    """Scope-aware variant: looks up cached coverage for `(scope_type, scope_id)`
    and overlays the 4-state weighted scores on top of the flag-based fallback.

    This is what the `/clarification/clarity` route uses.
    """
    base = compute_clarity_scores(user_story_ids)
    if base.totalUserStories == 0:
        # An empty scope stays "no target requirements" even if a stale
        # coverage row is cached for it.
        return base
    coverage = get_coverage(scope_type, scope_id)
    if coverage is None:
        return base

    # Overlay agent-reported statuses (single source of truth per SKILL.md).
    overlay: list[CategoryScore] = []
    for s in base.scores:
        agent_status = coverage.rows.get(s.category)
        if agent_status is None:
            overlay.append(s)
            continue
        weighted = STATUS_WEIGHT.get(agent_status, s.score)
        overlay.append(
            CategoryScore(
                category=s.category,
                score=round(weighted, 3) if weighted is not None else None,
                status=agent_status,
                flaggedCount=s.flaggedCount,
                resolvedCount=s.resolvedCount,
                scanned=True,
            )
        )

    return ClarityScores(
        totalUserStories=base.totalUserStories,
        flaggedUserStories=base.flaggedUserStories,
        resolvedUserStories=base.resolvedUserStories,
        resolvedSessions=base.resolvedSessions,
        scores=overlay,
    )


def overall_clarity(scores: ClarityScores) -> float | None:
    """Header %: unscanned axes count as 0 (same as their radar area), so a
    partly scanned scope is not reported as fully clear. None when nothing
    is scanned or the scope is empty — the UI shows "스캔 안 함"/"대상 없음"."""
    if scores.totalUserStories == 0 or not scores.scanned or not scores.scores:
        return None
    total = sum(s.score or 0.0 for s in scores.scores if s.scanned)
    return round(total / len(scores.scores), 3)
