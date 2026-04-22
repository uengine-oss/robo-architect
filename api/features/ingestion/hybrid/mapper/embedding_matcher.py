"""Phase 3.2: embedding-based matcher.

Runs after the lexical pass on Tasks that still have no high-confidence match.
For each remaining Task, compute cosine similarity to all Rule contexts and
emit top-k matches above θ_review. Matches between θ_review and θ_auto go to
the review queue rather than being auto-accepted.
"""

from __future__ import annotations

import os

from api.features.ingestion.hybrid.contracts import (
    ActivityRuleMapping,
    BpmSkeleton,
    RuleContext,
)
from api.features.ingestion.hybrid.mapper.embeddings import EmbeddingCache, cosine


def _theta_auto() -> float:
    # text-embedding-3-small produces ~0.45-0.55 cosines for genuinely related
    # Korean↔Korean GWT pairs in this codebase, so anything above 0.5 is a
    # reasonably solid signal. Tune down further if embedding still produces 0
    # auto-matches in your dataset.
    return float(os.getenv("HYBRID_EMBED_THETA_AUTO", "0.5"))


def _theta_review() -> float:
    return float(os.getenv("HYBRID_EMBED_THETA_REVIEW", "0.4"))


def _top_k() -> int:
    return int(os.getenv("HYBRID_EMBED_TOP_K", "3"))


def _task_text(task, actor_names: dict[str, str]) -> str:
    actors = ", ".join(actor_names.get(aid, "") for aid in (task.actor_ids or []))
    parts = [task.name, task.description or ""]
    if actors.strip(", "):
        parts.append(f"[Actor: {actors}]")
    return "\n".join(p for p in parts if p)


def _rule_text(ctx: RuleContext) -> str:
    parts: list[str] = []
    if ctx.context_cluster:
        # Phase 2.5 tag: surfacing the business domain at the top of the prompt
        # gives embedding models a much stronger disambiguator between rules
        # that share surface tokens but live in different contexts.
        parts.append(f"[업무범주: {ctx.context_cluster}]")
    # Parent-node context: module + direct callers. Helps the embedding
    # distinguish rules that live in the same BC but belong to different
    # calling flows (multi-module codebases).
    if ctx.parent_module:
        parts.append(f"[모듈: {ctx.parent_module}]")
    if ctx.callers:
        parts.append(f"[호출자: {', '.join(ctx.callers[:3])}]")
    parts.extend([
        f"GIVEN: {ctx.given}",
        f"WHEN: {ctx.when}",
        f"THEN: {ctx.then}",
    ])
    if ctx.function_summary:
        parts.append(f"Summary: {ctx.function_summary}")
    if ctx.source_function:
        parts.append(f"Function: {ctx.source_module or ''}.{ctx.source_function}")
    if ctx.reads_tables or ctx.writes_tables:
        parts.append(f"Tables: reads={ctx.reads_tables} writes={ctx.writes_tables}")
    return "\n".join(parts)


def match_embedding(
    skeleton: BpmSkeleton,
    contexts: list[RuleContext],
    exclude_task_ids: set[str] | None = None,
    cache: EmbeddingCache | None = None,
) -> tuple[list[ActivityRuleMapping], list[ActivityRuleMapping]]:
    """Returns (auto_matches, review_matches). Both use method='embedding'."""
    exclude = exclude_task_ids or set()
    auto: list[ActivityRuleMapping] = []
    review: list[ActivityRuleMapping] = []

    target_tasks = [t for t in skeleton.tasks if t.id not in exclude]
    if not target_tasks or not contexts:
        return auto, review

    cache = cache or EmbeddingCache()
    actor_name_by_id = {a.id: a.name for a in skeleton.actors}

    task_texts = [_task_text(t, actor_name_by_id) for t in target_tasks]
    rule_texts = [_rule_text(c) for c in contexts]
    try:
        task_vecs = cache.embed_many(task_texts)
        rule_vecs = cache.embed_many(rule_texts)
    except Exception:
        # If embeddings fail (no API key, offline) we simply emit nothing here.
        return auto, review

    theta_auto = _theta_auto()
    theta_review = _theta_review()
    top_k = _top_k()

    for t, tv in zip(target_tasks, task_vecs):
        if not tv:
            continue
        scored = [
            (c.rule_id, cosine(tv, rv))
            for c, rv in zip(contexts, rule_vecs)
            if rv
        ]
        scored.sort(key=lambda x: x[1], reverse=True)
        for rule_id, score in scored[:top_k]:
            if score >= theta_auto:
                auto.append(ActivityRuleMapping(
                    task_id=t.id, rule_id=rule_id, score=float(score), method="embedding",
                ))
            elif score >= theta_review:
                review.append(ActivityRuleMapping(
                    task_id=t.id, rule_id=rule_id, score=float(score), method="embedding",
                ))
    return auto, review
