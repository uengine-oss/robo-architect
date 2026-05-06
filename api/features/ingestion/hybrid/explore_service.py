"""User-triggered exploration service for the hybrid pipeline.

§11 cost optimization: per-task agentic retrieval is no longer auto-run for
every task during ingestion. The user triggers it on demand — either for a
single task (Inspector "🔍 탐색하기" button) or for an entire process
(Navigator "🔍 전체 탐색" button). This module hosts the shared logic so the
router only handles HTTP/SSE plumbing.

Three primitives:
- `explore_task`        — single task; cache-hit if REALIZED_BY exists & not force
- `explore_process`     — batch over a process's tasks (parallel, bounded)
- `post_explore_arbitration` — detect competing rule claims session-wide,
  resolve via cross_process_arbitrator, delete losing edges. Cheap when there
  are no conflicts.
"""

from __future__ import annotations

import asyncio
from typing import Any, Awaitable, Callable, Optional

from api.features.ingestion.hybrid.contracts import (
    ActivityRuleMapping,
    BpmActor,
    BpmProcess,
    BpmSkeleton,
    BpmTaskDTO,
    RuleDTO,
)
from api.features.ingestion.hybrid.mapper.agentic_retriever import run_agentic_retrieval
from api.features.ingestion.hybrid.mapper.condition_extractor import (
    extract_conditions_for_task,
)
from api.features.ingestion.hybrid.mapper.cross_process_arbitrator import (
    ClaimEntry,
    arbitrate_rule_home,
)
from api.features.ingestion.hybrid.mapper.rule_context import build_rule_contexts
from api.features.ingestion.hybrid.ontology.neo4j_ops import (
    delete_task_rule_mapping,
    fetch_session_snapshot,
    save_mappings,
    save_task_conditions,
)
from api.platform.neo4j import get_session
from api.platform.observability.smart_logger import SmartLogger


Sink = Callable[[dict], Awaitable[None]]


# =============================================================================
# Snapshot helpers — turn a session_id into the DTOs explore code expects
# =============================================================================


def _build_session_dtos(session_id: str) -> tuple[
    dict[str, dict],     # task_dict_by_id (raw snapshot dicts, includes 'rules' for cache check)
    dict[str, BpmProcess],
    dict[str, list[BpmActor]],   # actors per process
    list[RuleDTO],
    dict[str, BpmTaskDTO],       # BpmTaskDTO objects
    dict[str, str],              # task_id → process_id
]:
    snap = fetch_session_snapshot(session_id)
    actors_by_id = {a["id"]: a for a in snap.get("actors", [])}
    task_dict_by_id = {t["id"]: t for t in snap.get("tasks", [])}

    process_by_id: dict[str, BpmProcess] = {}
    process_actors: dict[str, list[BpmActor]] = {}
    task_to_process: dict[str, str] = {}
    for p in snap.get("processes", []):
        proc = BpmProcess(
            id=p["id"],
            name=p.get("name") or "",
            domain_keywords=p.get("domain_keywords") or [],
            source_pdf_name=p.get("source_pdf_name"),
            session_id=session_id,
            actor_ids=p.get("actor_ids") or [],
            task_ids=p.get("task_ids") or [],
        )
        process_by_id[proc.id] = proc
        process_actors[proc.id] = [
            BpmActor(id=ad["id"], name=ad.get("name", ""), description=ad.get("description"))
            for aid in proc.actor_ids
            if (ad := actors_by_id.get(aid))
        ]
        for tid in proc.task_ids:
            task_to_process[tid] = proc.id

    task_dto_by_id: dict[str, BpmTaskDTO] = {}
    for td in task_dict_by_id.values():
        pid = task_to_process.get(td["id"])
        task_dto_by_id[td["id"]] = BpmTaskDTO(
            id=td["id"],
            name=td.get("name", ""),
            description=td.get("description"),
            sequence_index=td.get("sequence_index", 0),
            actor_ids=td.get("actor_ids", []),
            source_page=td.get("source_page"),
            source_section=td.get("source_section"),
            process_id=pid,
        )

    rules = [RuleDTO(**{k: v for k, v in r.items() if k != "_hidden"})
             for r in snap.get("rules", [])]
    return task_dict_by_id, process_by_id, process_actors, rules, task_dto_by_id, task_to_process


# =============================================================================
# Single-task explore (with cache-hit short-circuit)
# =============================================================================


async def explore_task(
    session_id: str,
    task_id: str,
    *,
    force: bool = False,
    sink: Sink,
) -> dict:
    """Run agentic retrieval for one task. Returns {cached, mapping_count}.

    `force=False` (default): if the task already has REALIZED_BY mappings,
    return immediately without an LLM call (cache hit) — the persisted
    mappings serve as the cache.

    `force=True`: replace any existing mappings via fresh agentic retrieval.
    """
    (
        task_dict_by_id, process_by_id, process_actors,
        rules, task_dto_by_id, task_to_process,
    ) = _build_session_dtos(session_id)

    task_dict = task_dict_by_id.get(task_id)
    if not task_dict:
        await sink({"type": "AgentError", "task_id": task_id, "error": "Task not found"})
        return {"cached": False, "mapping_count": 0, "error": "Task not found"}

    # Fire BEFORE any work so the FE spinner lights up the moment this task's
    # turn comes in the sequential queue — even for tasks that finish in <100ms
    # (no candidates after Step 2 filter).
    await sink({
        "type": "TaskExploreStart",
        "task_id": task_id,
        "task_name": task_dict.get("name", ""),
    })

    existing_mappings = task_dict.get("rules") or []

    # Cache hit — the snapshot already loads REALIZED_BY edges as task.rules.
    if not force and existing_mappings:
        await sink({
            "type": "AgentCacheHit",
            "task_id": task_id,
            "task_name": task_dict.get("name", ""),
            "mapping_count": len(existing_mappings),
        })
        return {"cached": True, "mapping_count": len(existing_mappings)}

    # Cache miss — run the agent.
    pid = task_to_process.get(task_id)
    process = process_by_id.get(pid) if pid else None
    if not process:
        # Synthesize a single-task fallback so the agent still runs.
        process = BpmProcess(
            id="proc_fallback",
            name=task_dict.get("name") or "Process",
            domain_keywords=[],
            session_id=session_id,
            actor_ids=task_dict.get("actor_ids", []),
            task_ids=[task_id],
        )

    task_dto = task_dto_by_id.get(task_id)
    actors = process_actors.get(process.id, [])
    contexts = build_rule_contexts(rules)

    try:
        retrieval = await run_agentic_retrieval(
            process=process, tasks=[task_dto], actors=actors,
            rules=rules, contexts=contexts, event_sink=sink,
            # Per-task re-explore: the parent process already passed the batch
            # gate at ingestion time; re-evaluating from this single task's
            # module score would falsely reject legitimate tasks (§8 P1).
            skip_process_gate=True,
        )
    except Exception as e:
        await sink({"type": "AgentError", "task_id": task_id, "error": str(e)})
        return {"cached": False, "mapping_count": 0, "error": str(e)}

    new_mappings = [
        ActivityRuleMapping(
            task_id=m.task_id, rule_id=m.rule_id,
            score=float(m.score), method="agentic", reviewed=False,
            rationale=m.rationale,
            evidence_refs=list(m.evidence_refs or []),
            evidence_path=list(m.evidence_path or []),
            agent_verdict="accept",
        )
        for m in retrieval.accepted
    ]

    # Atomic replace: drop old REALIZED_BY + ActivityMapping rows for this task,
    # then insert. If retrieval came back empty it's a real "no matches" — we
    # still drop old mappings so stale data doesn't survive a re-explore.
    with get_session() as s:
        s.run(
            "MATCH (t:BpmTask {id: $tid, session_id: $sid})"
            "-[rel:REALIZED_BY]->() DELETE rel",
            tid=task_id, sid=session_id,
        )
        s.run(
            "MATCH (am:ActivityMapping {session_id: $sid, task_id: $tid}) "
            "DETACH DELETE am",
            sid=session_id, tid=task_id,
        )
    if new_mappings:
        save_mappings(session_id, new_mappings)

    # Phase 4.2 lazy: regenerate this task's conditions now that mappings settled.
    if new_mappings:
        try:
            await _refresh_task_conditions(session_id, task_dto, new_mappings, rules)
        except Exception as e:
            SmartLogger.log(
                "WARN", "Per-task conditions refresh failed (continuing)",
                category="ingestion.hybrid.explore.conditions",
                params={"task_id": task_id, "error": str(e)},
            )

    await sink({
        "type": "AgentPersisted",
        "task_id": task_id,
        "task_name": task_dict.get("name", ""),
        "mapping_count": len(new_mappings),
    })
    return {"cached": False, "mapping_count": len(new_mappings)}


async def _refresh_task_conditions(
    session_id: str,
    task: BpmTaskDTO,
    mappings: list[ActivityRuleMapping],
    rules: list[RuleDTO],
) -> None:
    """Re-run Phase 4.2 condition extraction for one task using its current mappings."""
    rule_by_id = {r.id: r for r in rules}
    task_rules = [rule_by_id[m.rule_id] for m in mappings if m.rule_id in rule_by_id]
    if not task_rules:
        return

    # Pull this task's passages from snapshot (Phase 4.1 already ran in pipeline).
    snap = fetch_session_snapshot(session_id)
    task_dict = next((t for t in snap.get("tasks", []) if t["id"] == task.id), None)
    if not task_dict:
        return
    passages = task_dict.get("document_passages") or []
    if not passages:
        return

    # extract_conditions_for_task expects DocumentPassage objects.
    from api.features.ingestion.hybrid.contracts import DocumentPassage
    passage_objs = [DocumentPassage(**{k: v for k, v in p.items() if k in DocumentPassage.model_fields})
                    for p in passages]
    conds = await extract_conditions_for_task(task, passage_objs, task_rules)
    if conds:
        save_task_conditions(session_id, {task.id: conds})


# =============================================================================
# Process batch explore (parallel, bounded concurrency)
# =============================================================================


# Sequential — task 한 개씩 순서대로. 병렬(N=3)도 가능했지만:
#   - 단일 spinner ref (`activeExploringTaskId`) 라 동시 진행 중인 다른 task 들이 시각적으로 묻힘
#   - "왜 4번부터 시작하지?" 처럼 사용자 멘탈 모델과 어긋남 (cache hit + 빠른 LLM 이 먼저 끝나는 효과)
# UX 가 비용보다 우선 — task당 LLM ~5~10s × N tasks 면 1~3분, 사용자가 진행 시각화 보면서 기다리는 게 자연스러움.
_PROCESS_EXPLORE_CONCURRENCY = 1


async def explore_process(
    session_id: str,
    process_id: str,
    *,
    force: bool = False,
    sink: Sink,
    max_concurrency: int = _PROCESS_EXPLORE_CONCURRENCY,
) -> dict:
    """Explore every task in a process. Skips tasks that already have mappings unless force=True.

    Sequential by default (concurrency=1) so per-task SSE events arrive in
    `sequence_index` order — matches user's mental model of "task 1 → 2 → 3 ...".
    """
    snap = fetch_session_snapshot(session_id)
    process_dict = next((p for p in snap.get("processes", []) if p["id"] == process_id), None)
    if not process_dict:
        await sink({"type": "AgentError", "error": f"Process {process_id} not found"})
        return {"explored": 0, "cached": 0, "errors": 0, "error": "Process not found"}

    task_ids = list(process_dict.get("task_ids") or [])
    if not task_ids:
        await sink({
            "type": "ProcessExploreEmpty",
            "process_id": process_id,
            "process_name": process_dict.get("name", ""),
        })
        return {"explored": 0, "cached": 0, "errors": 0}

    # Sort by sequence_index so the cascade visually matches canvas order.
    tasks_in_order = sorted(
        (t for t in snap.get("tasks", []) if t["id"] in task_ids),
        key=lambda t: t.get("sequence_index", 0) or 0,
    )

    await sink({
        "type": "ProcessExploreStart",
        "process_id": process_id,
        "process_name": process_dict.get("name", ""),
        "total_tasks": len(tasks_in_order),
    })

    sem = asyncio.Semaphore(max_concurrency)
    counters = {"explored": 0, "cached": 0, "errors": 0, "total_mappings": 0}

    async def _one(task_id: str):
        async with sem:
            try:
                r = await explore_task(session_id, task_id, force=force, sink=sink)
                if r.get("error"):
                    counters["errors"] += 1
                elif r.get("cached"):
                    counters["cached"] += 1
                    counters["total_mappings"] += int(r.get("mapping_count") or 0)
                else:
                    counters["explored"] += 1
                    counters["total_mappings"] += int(r.get("mapping_count") or 0)
            except Exception as e:
                counters["errors"] += 1
                await sink({"type": "AgentError", "task_id": task_id, "error": str(e)})

    await asyncio.gather(*[_one(t["id"]) for t in tasks_in_order])

    await sink({
        "type": "ProcessExploreEnd",
        "process_id": process_id,
        **counters,
    })
    return counters


# =============================================================================
# Post-explore arbitration — converge competing rule claims
# =============================================================================


async def post_explore_arbitration(session_id: str, *, sink: Sink) -> dict:
    """Find rules with REALIZED_BY edges to ≥2 (process, task) pairs and resolve.

    Reuses `cross_process_arbitrator.arbitrate_rule_home`. Cheap when there
    are no conflicts (typical case for a single-task explore that didn't
    overlap with prior mappings) — the conflict-detection query is one MATCH.
    """
    contested = _detect_contested_claims(session_id)
    if not contested:
        return {"contested": 0, "resolved": 0, "rejected": 0}

    await sink({
        "type": "ArbitrationStart",
        "contested_claims": [
            {"rule_id": rid, "claim_count": len(claims)} for rid, claims in contested
        ],
    })

    (
        _task_dict_by_id, process_by_id, _process_actors,
        rules, task_dto_by_id, _task_to_process,
    ) = _build_session_dtos(session_id)
    rule_by_id = {r.id: r for r in rules}
    contexts_by_rule = {c.rule_id: c for c in build_rule_contexts(rules)}

    resolved = 0
    rejected = 0
    for rule_id, claims in contested:
        rule = rule_by_id.get(rule_id)
        if not rule:
            continue
        ctx = contexts_by_rule.get(rule_id)
        claim_entries: list[ClaimEntry] = []
        for c in claims:
            proc = process_by_id.get(c["process_id"])
            tdto = task_dto_by_id.get(c["task_id"])
            if not proc or not tdto:
                continue
            claim_entries.append(ClaimEntry(
                process=proc,
                task=tdto,
                rationale=c.get("rationale") or "",
                score=float(c.get("score") or 0.0),
                module_confidence=1.0,  # post-hoc arbitration: trust persisted score
            ))
        if len(claim_entries) < 2:
            continue

        try:
            verdict = await arbitrate_rule_home(rule, ctx, claim_entries)
        except Exception as e:
            await sink({"type": "ArbitrationError", "rule_id": rule_id, "error": str(e)})
            continue

        if verdict.reject:
            for c in claim_entries:
                delete_task_rule_mapping(session_id, c.task.id, rule_id)
            await sink({
                "type": "ArbitrationDecision",
                "rule_id": rule_id,
                "winning_task_id": None,
                "losing_task_ids": [c.task.id for c in claim_entries],
                "rejected": True,
                "rationale": verdict.rationale,
            })
            rejected += 1
            resolved += 1
            continue

        winner_tid = verdict.home_task_id
        losers = [c.task.id for c in claim_entries if c.task.id != winner_tid]
        for ltid in losers:
            delete_task_rule_mapping(session_id, ltid, rule_id)
        await sink({
            "type": "ArbitrationDecision",
            "rule_id": rule_id,
            "winning_task_id": winner_tid,
            "losing_task_ids": losers,
            "rejected": False,
            "rationale": verdict.rationale,
        })
        resolved += 1

    await sink({"type": "ArbitrationEnd", "resolved": resolved, "rejected": rejected})
    return {"contested": len(contested), "resolved": resolved, "rejected": rejected}


def _detect_contested_claims(session_id: str) -> list[tuple[str, list[dict]]]:
    """Return rules that have ≥2 (process, task) REALIZED_BY claims in this session."""
    rows: list[tuple[str, list[dict]]] = []
    with get_session() as s:
        for r in s.run(
            """
            MATCH (t:BpmTask {session_id: $sid})-[rel:REALIZED_BY]->(rule:Rule {session_id: $sid})
            WITH rule.id AS rule_id,
                 collect({
                     task_id: t.id,
                     process_id: t.process_id,
                     score: rel.confidence,
                     rationale: rel.rationale
                 }) AS claims
            WHERE size(claims) > 1
            RETURN rule_id, claims
            """,
            sid=session_id,
        ):
            rows.append((r["rule_id"], list(r["claims"])))
    return rows
