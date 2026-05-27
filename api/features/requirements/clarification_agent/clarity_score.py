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
tracker (anything flagged → 0.0, else neutral 1.0). That preserves
backward behavior for cold-start dashboards.

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
    read_scope_log,
)
from api.features.requirements.clarification_contracts import (
    AmbiguityCategory,
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
    score: float
    status: CoverageStatus | None  # None = no scan yet for this scope
    flaggedCount: int
    resolvedCount: int


@dataclass
class ClarityScores:
    totalUserStories: int
    flaggedUserStories: int
    resolvedUserStories: int
    scores: list[CategoryScore] = field(default_factory=list)


def _flagged_count_by_category(user_story_ids: set[str]) -> dict[AmbiguityCategory, int]:
    """For each category, count in-scope UserStories currently flagged."""
    flags = snapshot_flags()
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


def _resolved_count_by_category(
    user_story_ids: set[str],
) -> dict[AmbiguityCategory, int]:
    """For each category, count applied (non-reverted) clarifications in scope."""
    log = read_scope_log(user_story_ids)
    by_cat: dict[AmbiguityCategory, set[str]] = {c: set() for c in AmbiguityCategory}
    for entry in log:
        if entry.reverted:
            continue
        cat = entry.category if isinstance(entry.category, AmbiguityCategory) else None
        if cat is None:
            try:
                cat = AmbiguityCategory(str(entry.category))
            except (ValueError, TypeError):
                continue
        by_cat[cat].add(f"{entry.sessionId}:{entry.questionId}")
    return {c: len(s) for c, s in by_cat.items()}


def _fallback_score(
    category: AmbiguityCategory, flagged_count: int, resolved_count: int
) -> tuple[float, CoverageStatus | None]:
    """When no scan coverage exists for the scope, infer a status from the
    flag tracker + log. Conservative — does not invent Clear; uses None to
    signal "unknown" so the radar can render it differently."""
    if flagged_count > 0:
        return 0.0, CoverageStatus.outstanding
    if resolved_count > 0:
        return 1.0, CoverageStatus.resolved
    return 1.0, None  # neutral — no signal at all


def compute_clarity_scores(user_story_ids: list[str]) -> ClarityScores:
    """Compute per-category clarity scores for an in-scope set of UserStories.

    Score sources, in precedence order:
      1. Cached coverage from the most recent agent scan (4-state weighted).
      2. Flag tracker + log (fallback, binary).

    Inputs:
      user_story_ids: ids of UserStories considered in-scope (caller resolves
                      scope via tree_service).
    """
    id_set = {x for x in user_story_ids if x}
    total = len(id_set)
    if total == 0:
        return ClarityScores(
            totalUserStories=0,
            flaggedUserStories=0,
            resolvedUserStories=0,
            scores=[
                CategoryScore(
                    category=c, score=1.0, status=None, flaggedCount=0, resolvedCount=0
                )
                for c in AmbiguityCategory
            ],
        )

    flagged_n = _flagged_count_by_category(id_set)
    resolved_n = _resolved_count_by_category(id_set)
    flagged_total = sum(
        1 for us_id in id_set if us_id in snapshot_flags()
    )
    resolved_us_total = len({
        e.sessionId for e in read_scope_log(id_set) if not e.reverted
    })

    scores: list[CategoryScore] = []
    for cat in AmbiguityCategory:
        # 1. Prefer the agent's reported coverage if we have it (any scope
        #    we have visibility to — start with the most-specific, but here
        #    the caller has already resolved the scope into ids, so we look
        #    up the cache that the route stored at scan time).
        # (The route stores under the scope it scanned; this helper is
        # called from the route too, so it knows the scope_type/scope_id —
        # but to keep this function pure we let `_coverage_for_category`
        # look up via the *scope_id*-less route by checking all known
        # caches and picking the first match for now. The route should
        # pass scope_type/scope_id; we accept it as None for testability.)
        score, status = _fallback_score(cat, flagged_n[cat], resolved_n[cat])
        scores.append(
            CategoryScore(
                category=cat,
                score=round(score, 3),
                status=status,
                flaggedCount=flagged_n[cat],
                resolvedCount=resolved_n[cat],
            )
        )

    return ClarityScores(
        totalUserStories=total,
        flaggedUserStories=flagged_total,
        resolvedUserStories=resolved_us_total,
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
                score=round(weighted, 3),
                status=agent_status,
                flaggedCount=s.flaggedCount,
                resolvedCount=s.resolvedCount,
            )
        )

    return ClarityScores(
        totalUserStories=base.totalUserStories,
        flaggedUserStories=base.flaggedUserStories,
        resolvedUserStories=base.resolvedUserStories,
        scores=overlay,
    )
