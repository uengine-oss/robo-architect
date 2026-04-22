"""Hierarchical Agentic Retrieval — Step 1: Module top-k.

Given a `BpmProcess` (name + domain_keywords) and a target `BpmTask`
(name + description), narrow the rule-search space by first identifying
which analyzer MODULEs are likely to host rules implementing this
process's tasks (docs/legacy-ingestion/개선&재구조화.md §B).

Pipeline: `Process.name + domain_keywords + Task.name` → vector query →
MODULE.summary cosine → top-k (default 5).

MODULE embeddings are cached per-session via `EmbeddingCache` to avoid
re-embedding the analyzer graph on each Task. For large graphs a future
migration can promote the cache to `MODULE.embedding` on the analyzer
side (see §B "MODULE 임베딩 캐싱").
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from api.features.ingestion.hybrid.contracts import BpmProcess, BpmTaskDTO
from api.features.ingestion.hybrid.mapper.embeddings import EmbeddingCache, cosine
from api.platform.neo4j import ANALYZER_NEO4J_DATABASE, get_session


@dataclass
class ModuleCandidate:
    fqn: str                            # analyzer-side fully-qualified name
    name: str
    summary: str
    stereotype: Optional[str] = None
    score: float = 0.0


def _module_rows() -> list[dict]:
    """Fetch MODULE (or FILE fallback) rows from the analyzer DB.

    Returns rows with {fqn, name, summary, stereotype}. `summary` is the
    primary vector target — §B in the doc confirms it's populated in Korean.
    """
    with get_session(database=ANALYZER_NEO4J_DATABASE) as s:
        rows = list(s.run(
            """
            MATCH (m:MODULE)
            WHERE m.summary IS NOT NULL AND m.summary <> ''
            RETURN m.fqn AS fqn, m.name AS name,
                   m.summary AS summary, m.moduleStereotype AS stereotype
            """,
        ))
        if not rows:
            # Fallback: some test fixtures store the same data under :FILE.
            rows = list(s.run(
                """
                MATCH (f:FILE)
                WHERE f.summary IS NOT NULL AND f.summary <> ''
                RETURN f.fqn AS fqn, f.name AS name,
                       f.summary AS summary, f.moduleStereotype AS stereotype
                """,
            ))
    return [
        {
            "fqn": r["fqn"] or r["name"],
            "name": r["name"] or r["fqn"],
            "summary": r["summary"] or "",
            "stereotype": r.get("stereotype"),
        }
        for r in rows
        if r["summary"]
    ]


def _build_query(process: BpmProcess, task: BpmTaskDTO) -> str:
    """Compose the vector query text. Intentionally verbose — `domain_keywords`
    carry the business-domain signal that disambiguates tasks with identical
    names across processes (e.g., "입력값 검증" in 계좌등록 vs 결제승인).
    """
    parts: list[str] = []
    if process.name:
        parts.append(process.name)
    if process.domain_keywords:
        parts.extend(process.domain_keywords)
    if task.name:
        parts.append(task.name)
    if task.description:
        parts.append(task.description)
    return " ".join(parts).strip() or (task.name or "")


# §2.B P1 — PROCESS-level threshold (applied by the orchestrator, not here).
# Below this cosine (on the max task-level score for a process), the analyzer
# code is assumed to NOT implement this process. Prevents contamination when
# the analyzer DB only contains code for a subset of the document's processes
# (e.g., 해지 프로세스에 대응하는 구현이 없는데 신청 모듈이 "가장 가깝다" 고 끌려들어오는 케이스).
#
# Task-level scores can be much lower than the process max because a single
# module summary aggregates many functions while a task query is narrow —
# filtering at task level over-rejects legitimate mappings (e.g., "입력값
# 검증" task scored 0.53 even though a000_input_validation is its exact
# implementation). So: we rank here without cutoff, and
# `run_agentic_retrieval` applies the cutoff once per process.
MIN_MODULE_CONFIDENCE = 0.55

# Per-module inclusion floor. A module with score below this is almost
# certainly noise — including it injects its (50~) BLs into the Step 2
# candidate pool for no upside. This matters at scale (large systems with
# 1000+ modules): top_k alone would let a long tail of rank 18, 19, 20
# modules with score 0.30~0.40 leak BLs into Step 2.
#
# Relationship to MIN_MODULE_CONFIDENCE:
#   - MIN_MODULE_CONFIDENCE (0.55) = process-level gate: kills whole process
#     if no module reaches this bar.
#   - MIN_MODULE_INCLUSION   (0.45) = per-module floor: inside a passing
#     process, still drop modules that individually score below this floor.
MIN_MODULE_INCLUSION = 0.45


async def retrieve_top_modules(
    process: BpmProcess,
    task: BpmTaskDTO,
    *,
    top_k: int = 20,
    min_inclusion_score: float = MIN_MODULE_INCLUSION,
    cache: Optional[EmbeddingCache] = None,
    module_rows: Optional[list[dict]] = None,
) -> list[ModuleCandidate]:
    """Run one Step-1 retrieval for (process, task) → top-k module candidates.

    `module_rows` may be supplied by the orchestrator when it has already
    fetched the analyzer MODULE catalog once per session (avoids re-query
    on every Task). Pass `cache` to share embeddings across tasks.

    Two-stage scoring:
      1. rank all modules by query cosine
      2. drop scores below `min_inclusion_score` (long-tail noise floor)
      3. keep the top-k of what's left

    The PROCESS-level gate (MIN_MODULE_CONFIDENCE) is applied separately in
    `run_agentic_retrieval` against the max task score.
    """
    cache = cache or EmbeddingCache()
    rows = module_rows if module_rows is not None else _module_rows()
    if not rows:
        return []

    query = _build_query(process, task)
    if not query:
        return []

    summaries = [r["summary"] for r in rows]
    module_vecs = cache.embed_many(summaries)
    query_vec = cache.embed(query)
    if not query_vec:
        return []

    scored: list[ModuleCandidate] = []
    for row, vec in zip(rows, module_vecs):
        score = cosine(query_vec, vec)
        if score < min_inclusion_score:
            continue
        scored.append(ModuleCandidate(
            fqn=row["fqn"], name=row["name"],
            summary=row["summary"], stereotype=row.get("stereotype"),
            score=score,
        ))

    scored.sort(key=lambda c: c.score, reverse=True)
    return scored[: max(1, int(top_k))] if scored else []


def fetch_all_modules() -> list[dict]:
    """Public helper so the orchestrator can fetch MODULE rows once per run."""
    return _module_rows()
