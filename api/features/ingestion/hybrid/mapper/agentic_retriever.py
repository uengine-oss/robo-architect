"""Hierarchical Agentic Retrieval — orchestrator (§2.B of 개선&재구조화.md).

Ties the 3-step pipeline together:

  Step 1 — module_retriever.retrieve_top_modules:    Process → top-k MODULE fqns
  Step 2 — BL filter within those modules + embedding fallback
  Step 3 — agent_validator.validate_candidates:      LLM + Cypher per Task

Result: for each Task of each Process, an AcceptedMapping list with 1-3
entries (ideally) + a per-rule rationale string. These replace Phase 3's
old lexical + embedding + structural booster + merge/dedup pipeline.

Design notes:
- One LLM call per Task (all candidates batched).
- Step 1 modules are cached per Process (all its Tasks share the same
  analyzer sub-graph cone).
- Optional SSE event sink so the Inspector (§2.C) can surface
  "retrieving → validating → done" progress in real time.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Awaitable, Callable, Optional

from api.features.ingestion.hybrid.contracts import (
    ActivityRuleMapping,
    BpmActor,
    BpmProcess,
    BpmSkeleton,
    BpmTaskDTO,
    RuleContext,
    RuleDTO,
)
from api.features.ingestion.hybrid.mapper.agent_validator import (
    CandidateBL,
    ValidationVerdict,
    validate_candidates,
)
from api.features.ingestion.hybrid.mapper.embeddings import EmbeddingCache, cosine
from api.features.ingestion.hybrid.mapper.module_retriever import (
    MIN_MODULE_CONFIDENCE,
    ModuleCandidate,
    fetch_all_modules,
    retrieve_top_modules,
)


# Per-BL inclusion floor for Step 2.
#
# Calibration (2026-04-23): with the lean rule_blob (title + GWT only), the
# cosine distribution against task queries has clear separation:
#   ≥ 0.50: high-confidence semantic match (typically validator-accepts)
#   0.45 ~ 0.50: near-miss / close call (validator may accept, sometimes reject)
#   < 0.45: stage- or domain-mismatch — validator essentially always rejects
# Floor at 0.45 keeps near-misses (so user can review them in the rejected
# panel) while excluding the long tail of obvious mismatches that previously
# inflated reject lists to 40+ entries per task.
MIN_BL_INCLUSION = 0.45

# Reject surfacing thresholds — emit only true near-miss rejects to the user.
# Per §9.1 calibration the cosine bands are:
#   ≥ 0.50      — validator usually accepts (already mapped)
#   0.45 ~ 0.50 — near-miss / close call (the band worth user review)
#   < 0.45      — already cut by MIN_BL_INCLUSION at Step 2
# Floor matches `MIN_BL_INCLUSION` (0.45) so the entire near-miss band is
# eligible to surface. `REJECT_VISIBLE_CAP` is the actual attention-budget
# control — only the top-N by score per task make it through.
REJECT_NEAR_MISS_FLOOR = 0.45
REJECT_VISIBLE_CAP = 3

from api.platform.observability.smart_logger import SmartLogger


AgentEvent = dict
AgentEventSink = Callable[[AgentEvent], Awaitable[None]]


@dataclass
class AcceptedMapping:
    """One agent-accepted Task↔Rule mapping with rationale attached."""

    task_id: str
    rule_id: str
    score: float
    rationale: str
    evidence_refs: list[str] = field(default_factory=list)
    evidence_path: list[str] = field(default_factory=list)


@dataclass
class RetrievalResult:
    accepted: list[AcceptedMapping] = field(default_factory=list)
    # Process → list[MODULE.fqn] (Step 1 result, for §2.F persistence)
    process_modules: dict[str, list[tuple[str, float]]] = field(default_factory=dict)
    # Mirrors accepted entries in the ActivityRuleMapping shape the rest of
    # Phase 3 expects (save_mappings takes this list).
    mappings: list[ActivityRuleMapping] = field(default_factory=list)


async def _noop_sink(ev: AgentEvent) -> None:
    return None


def _candidates_for_task(
    task: BpmTaskDTO,
    process: BpmProcess,
    rules: list[RuleDTO],
    contexts_by_rule: dict[str, RuleContext],
    module_fqns: list[str],
    *,
    top_k: int,
    cache: EmbeddingCache,
    actor_name_by_id: dict[str, str],
) -> list[CandidateBL]:
    """Step 2 — filter rules to those inside the Step-1 modules, then use
    embedding similarity to pick the top-k for this task.

    Module match is best-effort: a rule's `source_module` may be a bare name
    while `module_fqns` are fully-qualified; we compare on the trailing
    segment too. Rules with no module info fall through to embedding-only.
    """
    module_tails = {fqn.split(".")[-1] for fqn in module_fqns if fqn}
    module_set = set(module_fqns) | module_tails

    # Prefilter — keep rules whose source_module matches OR rules with no
    # module info (can't prove exclusion).
    in_scope: list[tuple[RuleDTO, RuleContext]] = []
    for r in rules:
        ctx = contexts_by_rule.get(r.id)
        if not ctx:
            continue
        sm = (r.source_module or ctx.source_module or "").strip()
        sm_tail = sm.split(".")[-1] if sm else ""
        if not sm:
            in_scope.append((r, ctx))
            continue
        if sm in module_set or sm_tail in module_tails:
            in_scope.append((r, ctx))

    if not in_scope:
        return []

    # Build embeddings for ranking. Query = Process keywords + Task name/desc.
    parts = [process.name, *(process.domain_keywords or []), task.name]
    if task.description:
        parts.append(task.description)
    actors = ", ".join(actor_name_by_id.get(aid, "") for aid in (task.actor_ids or []))
    if actors.strip(", "):
        parts.append(f"[Actor: {actors}]")
    query = " ".join(p for p in parts if p)

    # LEAN BLOB — title + GWT only.
    # Why drop function_summary / parent_module / callers from the embedding:
    # all rules in a single legacy module share the SAME function_summary
    # vocabulary ("자동납부", "인증", "결과반영" …). When we include it, every
    # cosine collapses into a tight 0.45~0.55 band — even rules that are
    # clearly stage-mismatched (an INSERT rule vs a 조회 task) score above
    # the 0.35 floor. Validator then has to LLM-reject 40+ obvious mismatches
    # per task, ballooning user-visible reject lists and validator cost.
    #
    # Measured (입력값 검증 task on test data, 52 rules):
    #   blob WITH summary:  43 rules ≥ 0.45  (pool too wide, mostly noise)
    #   blob lean (this):   15 rules ≥ 0.45  (real near-misses)
    # function_summary is still passed to the validator separately (see
    # agent_validator._format_candidate_for_prompt) so accept-side accuracy
    # is unaffected — only the embedding ranking gets sharper.
    rule_by_id = {r.id: r for r in rules}

    def _rule_blob(ctx: RuleContext) -> str:
        bits = []
        rule = rule_by_id.get(ctx.rule_id)
        if rule and rule.title:
            bits.append(f"규칙: {rule.title}")
        bits.append(f"GIVEN: {ctx.given}")
        bits.append(f"WHEN: {ctx.when}")
        bits.append(f"THEN: {ctx.then}")
        return "\n".join(bits)

    try:
        qv = cache.embed(query)
        rule_vecs = cache.embed_many([_rule_blob(ctx) for _, ctx in in_scope])
    except Exception:
        # No embeddings available — degrade to "return everything in scope"
        # and let the LLM validator do all the filtering.
        return [CandidateBL(rule=r, context=ctx, score=0.0)
                for r, ctx in in_scope][: top_k]

    scored = [
        (idx, cosine(qv, rv)) for idx, rv in enumerate(rule_vecs) if rv
    ]
    # Per-BL floor: drop rules obviously unrelated to the task before top-k.
    # At scale this prevents long-tail noise from consuming validator tokens.
    scored = [(i, s) for i, s in scored if s >= MIN_BL_INCLUSION]
    scored.sort(key=lambda x: x[1], reverse=True)
    picked = scored[: max(1, top_k)]
    score_by_idx = {i: s for i, s in picked}
    return [
        CandidateBL(
            rule=in_scope[i][0],
            context=in_scope[i][1],
            score=float(score_by_idx[i]),
        )
        for i, _ in picked
    ]


async def run_agentic_retrieval(
    process: BpmProcess,
    tasks: list[BpmTaskDTO],
    actors: list[BpmActor],
    rules: list[RuleDTO],
    contexts: list[RuleContext],
    *,
    # 한 프로세스가 실제로 쓰는 모듈은 보통 1~15 개 범위. 대형 시스템(1000+ 모듈)
    # 기준 safety margin 을 잡아 20. 낮게 잡아도 process-level gate + per-module
    # inclusion floor(0.45) 가 걸러주므로 과도한 노이즈는 나오지 않음.
    module_top_k: int = 20,
    # §2.B P1 — Step 1 코사인이 이 값 미만이면 "이 프로세스는 이 모듈을 구현하지
    # 않는다" 로 판단. 0.55 미만의 모듈로 Step 2 를 돌리면 노이즈 매칭이 발생.
    # NOTE: process-level gate 는 배치 실행(≥2 tasks) 전제로 설계됨. SSE 로 단일
    # task 를 재탐색할 때는 seen_fqns 가 그 한 task 점수만 갖게 되어 정당한 task
    # 도 gate 에 걸림 — 그런 경우는 호출자가 `skip_process_gate=True` 로 우회.
    min_module_score: float = MIN_MODULE_CONFIDENCE,
    skip_process_gate: bool = False,
    # 후보 cap — lean blob + 0.45 floor 적용 후 의미 있는 후보가 task 당
    # 평균 10~15 개로 수렴 (실측). 20 으로 설정하면 lean 분포의 자연 상한을
    # 살짝 넘게 두어 close-call 도 모두 들어옴. 대형 모듈(수백 BL)에서도
    # validator LLM 입력이 안정적 (~5k tokens / call).
    bl_top_k: int = 20,
    # 기본값은 "사실상 무제한" — 한 task 에 정당하게 5~10 개가 속하는 것이
    # 자연스러운 경우가 있음 (예: b000_main_proc 의 10 개 판정 분기).
    # 실제 limit 은 validator 가 의미 기준으로 판단. 아주 극단적 폭주 방지용 상한만 유지.
    per_task_cap: int = 20,
    cache: Optional[EmbeddingCache] = None,
    event_sink: Optional[AgentEventSink] = None,
) -> RetrievalResult:
    """Run Steps 1→2→3 for one Process. Returns accepted mappings + audit data."""
    sink = event_sink or _noop_sink
    cache = cache or EmbeddingCache()
    actor_name_by_id = {a.id: a.name for a in actors}
    ctx_by_rule = {c.rule_id: c for c in contexts}

    result = RetrievalResult()
    if not tasks:
        return result

    started = time.perf_counter()
    await sink({
        "type": "AgentStart",
        "process_id": process.id,
        "process_name": process.name,
        "task_count": len(tasks),
    })

    # ------ Step 1: module retrieval (per Task, but share the module corpus) ------
    module_rows = fetch_all_modules()
    per_task_modules: dict[str, list[ModuleCandidate]] = {}
    for task in tasks:
        cands = await retrieve_top_modules(
            process, task, top_k=module_top_k,
            cache=cache, module_rows=module_rows,
        )
        per_task_modules[task.id] = cands
        await sink({
            "type": "AgentStepModuleSearch",
            "process_id": process.id,
            "task_id": task.id,
            "query": f"{process.name} | {', '.join(process.domain_keywords or [])} | {task.name}",
            "candidates": [
                {"name": c.name, "fqn": c.fqn, "score": round(c.score, 4), "summary": c.summary[:200]}
                for c in cands
            ],
        })

    # Union of every module the agent considers relevant for this process
    # — persisted as Process.IMPLEMENTED_BY (§2.F).
    seen_fqns: dict[str, float] = {}
    for cands in per_task_modules.values():
        for c in cands:
            if c.fqn and (c.fqn not in seen_fqns or c.score > seen_fqns[c.fqn]):
                seen_fqns[c.fqn] = float(c.score)
    result.process_modules[process.id] = sorted(
        seen_fqns.items(), key=lambda x: x[1], reverse=True,
    )

    # §2.B P1 — process-level gate. The "does this process have code
    # implementing it" decision uses the MAX task-level module cosine (i.e.,
    # the strongest signal across all tasks). Task-level scores dip below
    # the threshold even for legitimate tasks because module summaries are
    # coarse-grained — so we gate per-process, not per-task.
    process_max_score = max(seen_fqns.values(), default=0.0)
    if not skip_process_gate and process_max_score < min_module_score:
        await sink({
            "type": "AgentDone",
            "process_id": process.id,
            "accepted": 0,
            "total_ms": int((time.perf_counter() - started) * 1000),
            "skipped": True,
            "reason": f"process_max_module_score={process_max_score:.3f} < {min_module_score}",
        })
        SmartLogger.log(
            "INFO", "Process skipped — no analyzer module exceeds threshold",
            category="ingestion.hybrid.agentic",
            params={
                "process_id": process.id,
                "process_name": process.name,
                "max_module_score": round(process_max_score, 4),
                "threshold": min_module_score,
            },
        )
        return result

    # ------ Step 2+3: per-task candidate filter + LLM validator ------
    for task in tasks:
        module_fqns = [c.fqn for c in per_task_modules.get(task.id, []) if c.fqn]
        candidates = _candidates_for_task(
            task=task, process=process, rules=rules,
            contexts_by_rule=ctx_by_rule, module_fqns=module_fqns,
            top_k=bl_top_k, cache=cache, actor_name_by_id=actor_name_by_id,
        )
        await sink({
            "type": "AgentStepBlSearch",
            "process_id": process.id,
            "task_id": task.id,
            "modules": module_fqns,
            "candidates": [
                {
                    "rule_id": c.rule.id,
                    "title": c.rule.title or "",
                    "source_function": c.rule.source_function,
                    "source_module": c.rule.source_module,
                } for c in candidates
            ],
        })
        if not candidates:
            await sink({"type": "AgentFinalMatches", "task_id": task.id, "rules": []})
            continue

        try:
            verdicts: list[ValidationVerdict] = await validate_candidates(
                process, task, candidates,
                sibling_tasks=tasks,
            )
        except Exception as e:
            SmartLogger.log(
                "WARN", "Agentic validator LLM call failed — skipping task",
                category="ingestion.hybrid.agentic",
                params={"task_id": task.id, "error": str(e)},
            )
            verdicts = []

        accepted_this_task: list[AcceptedMapping] = []
        for v in verdicts:
            await sink({
                "type": "AgentStepDecision",
                "task_id": task.id,
                "rule_id": v.rule_id,
                "verdict": v.verdict,
                "rationale": v.rationale,
            })
            if v.verdict != "accept":
                continue
            # Score: use the best embedding cosine for this candidate, fallback 1.0
            cand = next((c for c in candidates if c.rule.id == v.rule_id), None)
            score = 1.0
            if cand:
                # re-compute against the task query — cheap since cached
                parts = [process.name, *(process.domain_keywords or []), task.name]
                if task.description:
                    parts.append(task.description)
                qv = cache.embed(" ".join(p for p in parts if p))
                rv = cache.embed(
                    f"{cand.context.given}\n{cand.context.when}\n{cand.context.then}"
                )
                score = max(0.0, cosine(qv, rv))
            accepted_this_task.append(AcceptedMapping(
                task_id=task.id, rule_id=v.rule_id,
                score=float(score), rationale=v.rationale,
                evidence_refs=v.evidence_refs,
                evidence_path=module_fqns,
            ))

        # AgentFinalMatches now carries enough info that the runner can
        # persist this single task's mappings IMMEDIATELY (per-task DB write
        # + Navigator R-count update), without waiting for the whole process
        # to finish. Rejected verdicts are filtered to true near-misses only
        # (cognitive load reduction §10).
        cand_score_by_rule = {c.rule.id: c.score for c in candidates}
        # Surface only the closest-call rejects so the Inspector's "거부된 후보"
        # panel stays small. Filter rules:
        #   1. Step 2 cosine ≥ REJECT_NEAR_MISS_FLOOR (true near-miss territory)
        #   2. Top REJECT_VISIBLE_CAP by score
        # Anything below floor is an obvious-mismatch the validator confidently
        # dropped — surfacing it adds no review value, only inbox clutter.
        ranked_rejects = sorted(
            (
                {
                    "rule_id": v.rule_id,
                    "rationale": v.rationale,
                    "evidence_refs": list(v.evidence_refs or []),
                    "score": float(cand_score_by_rule.get(v.rule_id, 0.0)),
                }
                for v in verdicts if v.verdict != "accept"
            ),
            key=lambda x: x["score"],
            reverse=True,
        )
        near_miss_rejects = [
            r for r in ranked_rejects if r["score"] >= REJECT_NEAR_MISS_FLOOR
        ][:REJECT_VISIBLE_CAP]
        await sink({
            "type": "AgentFinalMatches",
            "task_id": task.id,
            "process_id": process.id,
            "rules": [
                {
                    "rule_id": m.rule_id,
                    "score": float(m.score),
                    "rationale": m.rationale,
                    "evidence_refs": list(m.evidence_refs or []),
                    "evidence_path": list(m.evidence_path or []),
                }
                for m in accepted_this_task
            ],
            "rejects": near_miss_rejects,
        })
        result.accepted.extend(accepted_this_task)

    # --- Post-processing: per-task cap only ----------------------------------
    # We intentionally do NOT cross-task dedup here anymore — same rule
    # accepted by ≥2 tasks within one process now flows through the
    # cross-process arbitrator (which already handles same-rule competing
    # claims across any (process, task) pair). This lets the per-task UI
    # show partial results immediately; arbitration corrects duplicates
    # afterwards via DELETE events the runner forwards to the frontend.
    by_task: dict[str, list[AcceptedMapping]] = {}
    for m in result.accepted:
        by_task.setdefault(m.task_id, []).append(m)
    final_accepted: list[AcceptedMapping] = []
    for tid, items in by_task.items():
        items.sort(key=lambda x: x.score, reverse=True)
        final_accepted.extend(items[: max(1, per_task_cap)])

    result.accepted = final_accepted

    # Note: `result.mappings` is kept populated by `activity_rule_mapper.map_tasks_to_rules`
    # (the caller), not here — it iterates `result.accepted` to build the full
    # ActivityRuleMapping list. We intentionally don't double-populate.

    await sink({
        "type": "AgentDone",
        "process_id": process.id,
        "accepted": len(result.accepted),
        "total_ms": int((time.perf_counter() - started) * 1000),
    })
    return result
