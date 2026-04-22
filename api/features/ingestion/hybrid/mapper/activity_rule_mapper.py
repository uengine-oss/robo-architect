"""Phase 3 orchestrator — Hierarchical Agentic Retrieval (§2.B).

Previously this ran a layered lexical→embedding→structural→dedupe pipeline.
That pipeline produced ~13 rules per Task and couldn't distinguish
"계좌등록 입력값 검증" from "결제승인 입력값 검증". The re-architected
pipeline (개선&재구조화.md §2.B) replaces it with:

  Step 1  module retrieval        (process.domain_keywords + task.name → MODULE top-k)
  Step 2  BL filter within modules
  Step 3  agentic validator       (LLM judges each candidate w/ Cypher-fetched parent chain)

Phase 3.0 (glossary) is retained as ancillary context. 3.1 / 3.2 / 3.3 / 3.4
are retired — the agent absorbs their responsibilities.

The function keeps the `Phase3Result` shape so the runner + Neo4j save path
don't change. `review_matches` is now empty by design: the agent either
accepts (high confidence) or rejects (we don't surface the noise to the
user — "사람 인지 부하 최소화").
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from api.features.ingestion.hybrid.contracts import (
    ActivityRuleMapping,
    BpmProcess,
    BpmSkeleton,
    GlossaryTerm,
    RuleContext,
    RuleDTO,
)
from api.features.ingestion.hybrid.mapper.agentic_retriever import (
    AgentEventSink,
    run_agentic_retrieval,
)
from api.features.ingestion.hybrid.mapper.cross_process_arbitrator import (
    SINGLE_CLAIM_ARBITRATION_THRESHOLD,
    ClaimEntry,
    arbitrate_rule_home,
)
from api.features.ingestion.hybrid.mapper.embeddings import EmbeddingCache
from api.features.ingestion.hybrid.mapper.glossary_extractor import extract_glossary
from api.features.ingestion.hybrid.mapper.rule_context import build_rule_contexts
from api.platform.observability.smart_logger import SmartLogger


@dataclass
class Phase3Result:
    glossary: list[GlossaryTerm] = field(default_factory=list)
    rule_contexts: list[RuleContext] = field(default_factory=list)
    auto_matches: list[ActivityRuleMapping] = field(default_factory=list)
    # Kept for shape compat with the save path; agentic pipeline never
    # produces a review queue (accept-or-reject only). Populated only when
    # legacy fallback path runs.
    review_matches: list[ActivityRuleMapping] = field(default_factory=list)
    table_edges: list[tuple[str, str, str]] = field(default_factory=list)
    # Process → list[(module_fqn, confidence)] for §2.F persistence.
    process_modules: dict[str, list[tuple[str, float]]] = field(default_factory=dict)


def _group_tasks_by_process(
    skeleton: BpmSkeleton,
    processes: list[BpmProcess],
) -> list[tuple[BpmProcess, list]]:
    """Return [(process, [tasks, ...])] pairs honoring task.process_id.

    Tasks whose process_id isn't in the provided process list are grouped
    under a synthetic fallback process so they still get processed.

    Tasks within each process are sorted by `sequence_index` so the per-task
    spinner in the Navigator (§8.7) advances in the same order the user sees
    on the BPMN canvas — not in whatever order skeleton.tasks happened to be
    built in.
    """
    by_id: dict[str, list] = {p.id: [] for p in processes}
    orphan_tasks: list = []
    for task in skeleton.tasks:
        pid = task.process_id
        if pid and pid in by_id:
            by_id[pid].append(task)
        else:
            orphan_tasks.append(task)
    for pid in by_id:
        by_id[pid].sort(key=lambda t: (t.sequence_index or 0, t.name or ""))
    orphan_tasks.sort(key=lambda t: (t.sequence_index or 0, t.name or ""))
    pairs: list[tuple[BpmProcess, list]] = [
        (p, by_id.get(p.id, [])) for p in processes
    ]
    if orphan_tasks:
        fallback = BpmProcess(
            id="proc_fallback", name="(프로세스 미지정)",
            domain_keywords=[], session_id="",
        )
        pairs.append((fallback, orphan_tasks))
    return pairs


async def map_tasks_to_rules(
    skeleton: BpmSkeleton,
    rules: list[RuleDTO],
    document_text: str = "",
    *,
    processes: Optional[list[BpmProcess]] = None,
    event_sink: Optional[AgentEventSink] = None,
) -> Phase3Result:
    """Runs hierarchical agentic retrieval for each process in the document."""
    result = Phase3Result()
    if not skeleton.tasks or not rules:
        return result

    # Shared across tasks: rule context enrichment + glossary.
    contexts = build_rule_contexts(rules)
    result.rule_contexts = contexts
    result.glossary = await extract_glossary(document_text, skeleton)

    # If caller didn't provide processes, synthesize one that owns every task.
    if not processes:
        processes = [BpmProcess(
            id="proc_default",
            name=skeleton.tasks[0].name if skeleton.tasks else "Process",
            domain_keywords=[],
            session_id="",
        )]
        for t in skeleton.tasks:
            t.process_id = processes[0].id

    cache = EmbeddingCache()

    # Collect every process's accepted mappings first, then dedup globally.
    # Each run_agentic_retrieval already dedups WITHIN a process; this outer
    # pass removes the common multi-process contamination where a single rule
    # gets accepted independently by 3~5 processes (see §2.B — Step 3 agent
    # is LLM-based so same-function rules can look valid across domains).
    all_accepted: list[tuple["BpmProcess", object]] = []  # (process, AcceptedMapping)
    pairs = _group_tasks_by_process(skeleton, processes)
    for process, tasks in pairs:
        if not tasks:
            continue
        retrieval = await run_agentic_retrieval(
            process=process,
            tasks=tasks,
            actors=skeleton.actors,
            rules=rules,
            contexts=contexts,
            cache=cache,
            event_sink=event_sink,
        )
        for m in retrieval.accepted:
            all_accepted.append((process, m))
        if process.id != "proc_fallback":
            result.process_modules[process.id] = retrieval.process_modules.get(
                process.id, [],
            )
        # §8.7 UX — let the runner persist this process's accepted mappings
        # immediately so the Navigator's R count badges light up per-process,
        # long before Step 4 arbitration runs. Losing claims (if any) will
        # be DELETEd when arbitration resolves them below.
        if event_sink:
            await event_sink({
                "type": "ProcessMappingsPartial",
                "process_id": process.id,
                "mappings": [
                    {
                        "task_id": m.task_id,
                        "rule_id": m.rule_id,
                        "score": float(m.score),
                        "rationale": m.rationale,
                        "evidence_refs": list(m.evidence_refs or []),
                        "evidence_path": list(m.evidence_path or []),
                    }
                    for m in retrieval.accepted
                ],
            })

    # Group accepts by rule for cross-process arbitration.
    claims_by_rule: dict[str, list[tuple[BpmProcess, object]]] = {}
    for proc, m in all_accepted:
        claims_by_rule.setdefault(m.rule_id, []).append((proc, m))

    # Build lookup for rule DTO + context to feed the arbitrator.
    rule_by_id = {r.id: r for r in rules}
    ctx_by_rule = {c.rule_id: c for c in contexts}
    # Build task_id → BpmTaskDTO map (agent's AcceptedMapping only has task_id).
    task_by_id = {t.id: t for t in skeleton.tasks}

    # §2.B P3 — precompute each process's top-module confidence so we can
    # attach it to every ClaimEntry. A low top-1 confidence means Step 1
    # barely found anything implementing this process → arbitrator should
    # second-guess even single claims.
    module_conf_by_proc: dict[str, float] = {}
    for pid, entries_list in result.process_modules.items():
        module_conf_by_proc[pid] = float(entries_list[0][1]) if entries_list else 0.0

    # §8.7 UX — surface arbitration progress. A claim is "contested" if either
    # (a) ≥ 2 processes accepted the same rule, or (b) the only process that
    # accepted it has low module_confidence (forces single-claim re-judgment).
    # Frontend highlights all task_ids in contested claims so users see which
    # mappings are under cross-process review.
    contested_claims_payload = []
    for rule_id, claim_pairs in claims_by_rule.items():
        if len(claim_pairs) > 1:
            for proc, m in claim_pairs:
                contested_claims_payload.append({
                    "rule_id": rule_id,
                    "task_id": m.task_id,
                    "process_id": proc.id,
                })
        elif len(claim_pairs) == 1:
            proc, m = claim_pairs[0]
            if module_conf_by_proc.get(proc.id, 1.0) < SINGLE_CLAIM_ARBITRATION_THRESHOLD:
                contested_claims_payload.append({
                    "rule_id": rule_id,
                    "task_id": m.task_id,
                    "process_id": proc.id,
                })
    if event_sink and contested_claims_payload:
        await event_sink({
            "type": "ArbitrationStart",
            "contested_claims": contested_claims_payload,
        })

    arbitration_rejected = 0
    for rule_id, claim_pairs in claims_by_rule.items():
        rule_dto = rule_by_id.get(rule_id)
        if rule_dto is None:
            continue
        # Build entries up-front so we can inspect module_confidence below.
        entries = []
        for proc, m in claim_pairs:
            t = task_by_id.get(m.task_id)
            if t is None:
                continue
            entries.append(ClaimEntry(
                process=proc, task=t,
                rationale=m.rationale, score=float(m.score),
                module_confidence=module_conf_by_proc.get(proc.id, 1.0),
            ))
        if not entries:
            continue

        # Single high-confidence claim: trust the per-process validator,
        # skip an extra LLM call. Anything else (multi-claim OR single
        # claim with low module_confidence) goes through arbitration.
        if (
            len(entries) == 1
            and entries[0].module_confidence >= SINGLE_CLAIM_ARBITRATION_THRESHOLD
        ):
            proc, m = claim_pairs[0]
            result.auto_matches.append(ActivityRuleMapping(
                task_id=m.task_id, rule_id=m.rule_id,
                score=float(m.score), method="agentic", reviewed=False,
                rationale=m.rationale,
                evidence_refs=list(m.evidence_refs or []),
                evidence_path=list(m.evidence_path or []),
                agent_verdict="accept",
            ))
            continue

        all_claim_task_ids = [e.task.id for e in entries]
        try:
            verdict = await arbitrate_rule_home(
                rule_dto, ctx_by_rule.get(rule_id), entries,
            )
        except Exception as e:
            SmartLogger.log(
                "WARN", "Arbitration LLM failed — falling back to highest score",
                category="ingestion.hybrid.arbitration",
                params={"rule_id": rule_id, "error": str(e)},
            )
            entries.sort(key=lambda c: c.score, reverse=True)
            best = entries[0]
            result.auto_matches.append(ActivityRuleMapping(
                task_id=best.task.id, rule_id=rule_id,
                score=float(best.score), method="agentic", reviewed=False,
                rationale=best.rationale,
                agent_verdict="accept",
            ))
            if event_sink:
                await event_sink({
                    "type": "ArbitrationDecision",
                    "rule_id": rule_id,
                    "winning_task_id": best.task.id,
                    "losing_task_ids": [tid for tid in all_claim_task_ids if tid != best.task.id],
                    "rejected": False,
                    "fallback": True,
                })
            continue

        if verdict.reject:
            arbitration_rejected += 1
            if event_sink:
                await event_sink({
                    "type": "ArbitrationDecision",
                    "rule_id": rule_id,
                    "winning_task_id": None,
                    "losing_task_ids": all_claim_task_ids,
                    "rejected": True,
                    "rationale": verdict.rationale,
                })
            continue

        # Find the original mapping entry matching the chosen (proc, task).
        chosen = next(
            (e for e in entries
             if e.process.id == verdict.home_process_id
             and e.task.id == verdict.home_task_id),
            None,
        )
        if chosen is None:
            continue
        # Locate the AcceptedMapping for evidence_refs / evidence_path carry-over.
        evidence_src = next(
            (m for proc, m in claim_pairs
             if proc.id == chosen.process.id and m.task_id == chosen.task.id),
            None,
        )
        result.auto_matches.append(ActivityRuleMapping(
            task_id=chosen.task.id, rule_id=rule_id,
            score=float(chosen.score), method="agentic", reviewed=False,
            rationale=verdict.rationale,
            evidence_refs=list(evidence_src.evidence_refs) if evidence_src else [],
            evidence_path=list(evidence_src.evidence_path) if evidence_src else [],
            agent_verdict="accept",
        ))
        if event_sink:
            await event_sink({
                "type": "ArbitrationDecision",
                "rule_id": rule_id,
                "winning_task_id": chosen.task.id,
                "losing_task_ids": [tid for tid in all_claim_task_ids if tid != chosen.task.id],
                "rejected": False,
                "rationale": verdict.rationale,
            })

    if event_sink and contested_claims_payload:
        await event_sink({"type": "ArbitrationEnd"})

    if arbitration_rejected:
        SmartLogger.log(
            "INFO", "Arbitration rejected cross-cutting rules",
            category="ingestion.hybrid.arbitration",
            params={"rejected_rule_count": arbitration_rejected},
        )

    SmartLogger.log(
        "INFO", "Phase 3 agentic retrieval complete",
        category="ingestion.hybrid.mapping",
        params={
            "glossary_terms": len(result.glossary),
            "rules": len(rules),
            "processes": len(processes),
            "auto_matches": len(result.auto_matches),
            "process_modules": sum(len(v) for v in result.process_modules.values()),
        },
    )
    return result
