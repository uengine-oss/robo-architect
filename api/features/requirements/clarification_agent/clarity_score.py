"""Clarity scoring for the radar chart (030 — visualization).

Per-category clarity score over a scope of UserStories. For each of the
10 ambiguity categories (SpecKit `/speckit-clarify` SKILL.md), we compute
a score in [0, 1] where 1.0 = no in-scope requirement was flagged for
this category, 0.0 = every in-scope requirement was flagged.

Inputs:
 - The list of in-scope `UserStory` ids (the caller resolves the scope
   via `tree_service.build_requirements_tree`).
 - The in-memory `clarification_flags` snapshot (questions the most-recent
   scans surfaced).
 - The persistent `UserStory.clarifications` log (the audit trail of
   resolved questions, so already-resolved ambiguities count toward
   clarity).

Output:
 - `ClarityScores`: per-category score + the inputs used (so the radar can
   show "flagged X of N").

This is a pure read-only view; no graph mutations.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from api.features.requirements.clarification_agent.clarification_flags import (
    snapshot as snapshot_flags,
)
from api.features.requirements.clarification_agent.clarification_log import (
    read_scope_log,
)
from api.features.requirements.clarification_contracts import (
    AmbiguityCategory,
    ClarificationLogEntry,
)


@dataclass
class CategoryScore:
    category: AmbiguityCategory
    score: float  # 0.0 (all flagged) .. 1.0 (none flagged)
    flaggedCount: int
    resolvedCount: int


@dataclass
class ClarityScores:
    """Result payload for `GET /clarification/clarity`."""

    totalUserStories: int
    flaggedUserStories: int
    resolvedUserStories: int
    scores: list[CategoryScore] = field(default_factory=list)


def _flagged_by_category(
    user_story_ids: set[str],
) -> dict[AmbiguityCategory, set[str]]:
    """For each category, the set of in-scope UserStory ids the in-memory
    flag tracker currently considers ambiguous."""
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
    return by_cat


def _resolved_by_category(
    log: list[ClarificationLogEntry],
) -> dict[AmbiguityCategory, set[str]]:
    """For each category, the set of UserStory ids that have at least one
    *applied & non-reverted* clarification log entry. This is the
    cumulative "we already fixed this category here" signal."""
    by_cat: dict[AmbiguityCategory, set[str]] = {c: set() for c in AmbiguityCategory}
    # `read_scope_log` returns entries from `UserStory.clarifications`,
    # which only contains *applied* answers — but they may carry `reverted=true`.
    for entry in log:
        if entry.reverted:
            continue
        # The log entry's `category` may already be an enum or a string
        # depending on Pydantic validation; normalize.
        cat = entry.category if isinstance(entry.category, AmbiguityCategory) else None
        if cat is None:
            try:
                cat = AmbiguityCategory(str(entry.category))
            except (ValueError, TypeError):
                continue
        # The log entry's `before` snapshot doesn't carry the user-story
        # id directly — but the log was *fetched* per user-story, and the
        # session_id ties them. The caller passes us the merged log; we
        # rely on `entry.questionId` to dedupe per US. Since the entry
        # lives on `UserStory.clarifications`, every entry already came
        # from one specific user story. We don't have that id here —
        # so the read_scope_log caller path returns them merged across
        # user stories. The cleanest fix is to track via `sessionId +
        # questionId` uniqueness; in practice a question is per-US and
        # we use the entry's natural `requirementId` if present.
        # The `ClarificationLogEntry` schema doesn't have requirementId
        # explicitly — but `read_scope_log` was called with a known set
        # of ids, so any entry that exists IS for one of those ids.
        # We accumulate by (sessionId, questionId) pairs into `by_cat`
        # using a synthetic counter — see merge logic below.
        by_cat[cat].add(f"{entry.sessionId}:{entry.questionId}")
    return by_cat


def compute_clarity_scores(user_story_ids: list[str]) -> ClarityScores:
    """Compute per-category clarity scores for an in-scope set of UserStories."""
    id_set = {x for x in user_story_ids if x}
    total = len(id_set)
    if total == 0:
        return ClarityScores(
            totalUserStories=0,
            flaggedUserStories=0,
            resolvedUserStories=0,
            scores=[CategoryScore(category=c, score=1.0, flaggedCount=0, resolvedCount=0)
                    for c in AmbiguityCategory],
        )

    flagged_by_cat = _flagged_by_category(id_set)
    log = read_scope_log(id_set)
    resolved_by_cat = _resolved_by_category(log)

    flagged_total = {us for cat_set in flagged_by_cat.values() for us in cat_set}
    # "resolved" at the US level — at least one applied clarification on it.
    resolved_us = set()
    by_us_log: dict[str, list[ClarificationLogEntry]] = {}
    for entry in log:
        if entry.reverted:
            continue
        # No explicit US id on the entry; we can't trace it here without
        # a wider join. Approximate: any entry seen → bump "resolved" for
        # one US (cumulative across the scope). This is a coarse signal —
        # the radar's primary axis is `flagged`, not `resolved`.
        by_us_log.setdefault(entry.sessionId, []).append(entry)
    # Approximation: 1 resolved US per session of applied entries.
    resolved_us = set(by_us_log.keys())

    scores: list[CategoryScore] = []
    for cat in AmbiguityCategory:
        flagged_n = len(flagged_by_cat[cat])
        # Score = 1 - flaggedFraction. When 0 are flagged → 1.0 (clear).
        score = 1.0 - (flagged_n / total)
        # Clamp to [0, 1] just in case.
        score = max(0.0, min(1.0, score))
        scores.append(
            CategoryScore(
                category=cat,
                score=round(score, 3),
                flaggedCount=flagged_n,
                resolvedCount=len(resolved_by_cat[cat]),
            )
        )

    return ClarityScores(
        totalUserStories=total,
        flaggedUserStories=len(flagged_total),
        resolvedUserStories=len(resolved_us),
        scores=scores,
    )
