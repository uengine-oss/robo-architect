"""Rank Analyzer code containers for one business task."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Optional

from api.features.ingestion.hybrid.contracts import BpmProcess, BpmTaskDTO
from api.features.ingestion.hybrid.mapper.embeddings import EmbeddingCache, cosine
from api.platform.neo4j import ANALYZER_NEO4J_DATABASE, get_session


@dataclass
class ContainerCandidate:
    id: str
    name: str
    summary: str
    stereotype: Optional[str] = None
    score: float = 0.0


def _container_rows() -> list[dict]:
    """Fetch source containers that can narrow routine retrieval."""
    with get_session(database=ANALYZER_NEO4J_DATABASE) as session:
        rows = list(
            session.run(
                """
                MATCH (container {_owner: 'analyzer'})
                WHERE (container:FILE OR container:CLASS OR container:INTERFACE OR container:RECORD)
                  AND container.summary IS NOT NULL AND container.summary <> ''
                RETURN container._id AS id, container.name AS name,
                       container.summary AS summary, container.stereotype AS stereotype
                """
            )
        )
    return [
        {
            "id": row["id"],
            "name": row["name"] or row["id"],
            "summary": row["summary"],
            "stereotype": row.get("stereotype"),
        }
        for row in rows
        if row["id"] and row["summary"]
    ]


def _build_query(process: BpmProcess, task: BpmTaskDTO) -> str:
    parts = [process.name, *(process.domain_keywords or []), task.name]
    if task.description:
        parts.append(task.description)
    return " ".join(part for part in parts if part).strip()


MIN_CONTAINER_CONFIDENCE = 0.55
MIN_CONTAINER_INCLUSION = 0.45


async def retrieve_top_containers(
    process: BpmProcess,
    task: BpmTaskDTO,
    *,
    top_k: int = 20,
    min_inclusion_score: float = MIN_CONTAINER_INCLUSION,
    cache: Optional[EmbeddingCache] = None,
    container_rows: Optional[list[dict]] = None,
) -> list[ContainerCandidate]:
    """Return the most relevant FILE/CLASS-like containers."""
    cache = cache or EmbeddingCache()
    rows = container_rows if container_rows is not None else _container_rows()
    query = _build_query(process, task)
    if not rows or not query:
        return []

    vectors = await asyncio.to_thread(cache.embed_many, [row["summary"] for row in rows])
    query_vector = await asyncio.to_thread(cache.embed, query)
    if not query_vector:
        return []

    candidates = [
        ContainerCandidate(
            id=row["id"],
            name=row["name"],
            summary=row["summary"],
            stereotype=row.get("stereotype"),
            score=cosine(query_vector, vector),
        )
        for row, vector in zip(rows, vectors)
    ]
    candidates = [item for item in candidates if item.score >= min_inclusion_score]
    candidates.sort(key=lambda item: item.score, reverse=True)
    return candidates[: max(1, int(top_k))]


def fetch_all_containers() -> list[dict]:
    """Fetch the container corpus once for a retrieval run."""
    return _container_rows()
