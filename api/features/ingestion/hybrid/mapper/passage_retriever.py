"""Phase 4.1-4.3: retrieve top-k document passages per Task by semantic similarity.

Always returns exactly `k` passages per task (0.5 threshold is used only as a
`low_confidence` flag — we don't filter). Rationale: Korean task names are
short; cosine against English-heavy code contexts routinely lands below 0.6
even for correct matches. Showing top-k with a confidence hint is more useful
than dropping to zero.
"""

from __future__ import annotations

import os

from api.features.ingestion.hybrid.contracts import (
    BpmSkeleton,
    DocumentPassage,
    TaskPassageLink,
)
from api.features.ingestion.hybrid.mapper.embeddings import EmbeddingCache, cosine


def _top_k() -> int:
    return int(os.getenv("HYBRID_PASSAGE_TOP_K", "2"))


def _theta() -> float:
    return float(os.getenv("HYBRID_PASSAGE_THETA", "0.5"))


def _task_text(task, actor_name_by_id: dict[str, str]) -> str:
    parts = [task.name, task.description or ""]
    actors = ", ".join(actor_name_by_id.get(aid, "") for aid in (task.actor_ids or []))
    if actors.strip(", "):
        parts.append(f"[Actor: {actors}]")
    return "\n".join(p for p in parts if p)


def _passage_text(p: DocumentPassage) -> str:
    head = p.heading or ""
    return f"{head}\n{p.text}".strip() if head else p.text


def retrieve_passages_per_task(
    skeleton: BpmSkeleton,
    passages: list[DocumentPassage],
    cache: EmbeddingCache | None = None,
) -> list[TaskPassageLink]:
    if not skeleton.tasks or not passages:
        return []

    cache = cache or EmbeddingCache()
    actor_name_by_id = {a.id: a.name for a in skeleton.actors}

    task_texts = [_task_text(t, actor_name_by_id) for t in skeleton.tasks]
    passage_texts = [_passage_text(p) for p in passages]

    try:
        task_vecs = cache.embed_many(task_texts)
        passage_vecs = cache.embed_many(passage_texts)
    except Exception:
        return []

    k = _top_k()
    theta = _theta()
    links: list[TaskPassageLink] = []

    for task, tv in zip(skeleton.tasks, task_vecs):
        if not tv:
            continue
        scored = [
            (p.id, cosine(tv, pv))
            for p, pv in zip(passages, passage_vecs)
            if pv
        ]
        scored.sort(key=lambda x: x[1], reverse=True)
        for rank, (passage_id, score) in enumerate(scored[:k]):
            links.append(TaskPassageLink(
                task_id=task.id,
                passage_id=passage_id,
                score=float(score),
                rank=rank,
                low_confidence=bool(score < theta),
            ))
    return links
