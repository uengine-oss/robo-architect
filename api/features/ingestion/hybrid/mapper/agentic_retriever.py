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

import asyncio
import os
import time
from dataclasses import dataclass, field
from typing import Awaitable, Callable, Optional

from api.features.ingestion.hybrid.contracts import (
    ActivityRuleMapping,
    BpmActor,
    BpmProcess,
    BpmSkeleton,
    BpmTaskDTO,
    GlossaryTerm,
    RuleContext,
    RuleDTO,
)
from api.features.ingestion.hybrid.mapper.agent_validator import (
    CandidateBL,
    ValidationVerdict,
    validate_candidates,
)
from api.features.ingestion.hybrid.mapper.embeddings import EmbeddingCache, cosine
from api.features.ingestion.hybrid.mapper.term_normalizer import (
    normalize_query,
    normalize_rule_blob,
)


def _glossary_normalize_enabled() -> bool:
    """env 토글 — `HYBRID_GLOSSARY_NORMALIZE=0`이면 정규화 완전 비활성(기존 경로와 동일)."""
    return os.getenv("HYBRID_GLOSSARY_NORMALIZE", "1") != "0"


def _max_recoveries_per_task() -> int:
    """§036 — task당 정규화 회복 후보 상한. 검증기 부하·화면 노출·비용을 묶는 핵심 레버.

    baseline 후보는 그대로 두고, 어휘갭으로 누락된 후보를 task당 이 수만큼만(가장 확신
    높은 것부터) 검증기에 추가한다. 0이면 회복 없음(정규화 무효), 큰 값이면 recall↑·비용↑.

    기본 4 (B2): glossary 가 task 명/별칭/코드후보를 풍부히 담고 있어(예: '카드사 식별 및
    정합성 검증' → code ['카드사','정합성']) 용어겹침이 분명한 rule 이 2-슬롯 cap 에서 다른
    below-floor 후보에 밀려 누락되던 리콜 갭을 완화. 회복분 포함 검증기 후보 수는 여전히
    top_k 이내로 캡되므로 비용·노출 상한은 불변(MIN_BL_INCLUSION floor 는 미변경 → 노이즈
    회귀 없음). 더 보수/공격적으로는 env `HYBRID_GLOSSARY_MAX_RECOVERIES` 로 조정.
    """
    try:
        return max(0, int(os.getenv("HYBRID_GLOSSARY_MAX_RECOVERIES", "4")))
    except ValueError:
        return 4
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
    glossary: list[GlossaryTerm] | None = None,
) -> list[CandidateBL]:
    """Step 2 — filter rules to those inside the Step-1 modules, then use
    embedding similarity to pick the top-k for this task.

    Module match is **exact**: both sides are the analyzer's module id.
      - `module_fqns` = `m.id` (module_retriever query)
      - `source_module` = `f.owner_id` — the analyzer now stores the owning module
        as a node property (analyzer spec 047 FR-007).

    The old code compared "trailing segments" because `source_module` used to be
    *guessed by slicing the function id*, which could
    produce a bare name that never matched a fully-qualified one. That slicing is
    gone — **an id is an opaque key, not an address to parse**. Rules with no
    module info still fall through to embedding-only (can't prove exclusion).
    """
    module_set = {fqn for fqn in module_fqns if fqn}

    in_scope: list[tuple[RuleDTO, RuleContext]] = []
    for r in rules:
        ctx = contexts_by_rule.get(r.id)
        if not ctx:
            continue
        sm = (r.source_module or ctx.source_module or "").strip()
        if not sm:
            in_scope.append((r, ctx))
            continue
        if sm in module_set:
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

    # ---- Baseline ranking (정규화 미적용) — 항상 먼저 계산 ----
    try:
        qv0 = cache.embed(query)
        rule_vecs0 = cache.embed_many([_rule_blob(ctx) for _, ctx in in_scope])
    except Exception:
        # No embeddings available — degrade to "return everything in scope"
        # and let the LLM validator do all the filtering.
        return [CandidateBL(rule=r, context=ctx, score=0.0)
                for r, ctx in in_scope][: top_k]

    def _above_floor(qv, vecs) -> list[tuple[int, float]]:
        out = [(i, cosine(qv, rv)) for i, rv in enumerate(vecs) if rv]
        out = [(i, s) for i, s in out if s >= MIN_BL_INCLUSION]
        out.sort(key=lambda x: x[1], reverse=True)
        return out

    base = _above_floor(qv0, rule_vecs0)

    # §036 — glossary 용어 정규화(양방향) + union-under-cap.
    # 핵심 원칙(인지부하·비용 최소화):
    #   (1) baseline 후보는 항상 전부 보존  → 정규화로 인한 회귀 0건(구조적 보장).
    #   (2) cap(top_k)에 여유가 있을 때만 정규화 회복분을 채움 → "후보가 적은 task"
    #       (= 어휘갭으로 recall이 실제 위험한 경우)에만 효과. full-plate task는 무변경.
    #   (3) 검증기에 가는 후보 수는 top_k 이내로 불변 → validator 부하·비용 상한 유지.
    # env off / glossary 부재 시 baseline 그대로(기존 경로와 동일).
    norm_on = bool(glossary) and _glossary_normalize_enabled()
    if norm_on and len(base) < top_k:
        qn, _ = normalize_query(query, glossary)
        try:
            qvn = cache.embed(qn)
            rule_vecsn = cache.embed_many([
                normalize_rule_blob(_rule_blob(ctx), r, ctx, glossary)[0]
                for r, ctx in in_scope
            ])
            norm = _above_floor(qvn, rule_vecsn)
        except Exception:
            norm = []
        base_ids = {i for i, _ in base}
        # task당 회복 상한 + cap 여유 중 작은 값만큼만 추가(검증기 부하·노출·비용 억제).
        room = min(top_k - len(base), _max_recoveries_per_task())
        extras = [(i, s) for i, s in norm if i not in base_ids][: max(0, room)]
        picked = base + extras
    else:
        # full-plate task 또는 정규화 off → baseline만(회귀·churn·추가비용 0).
        picked = base[: max(1, top_k)]

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
    # §036 — 용어 정규화용 glossary. None/빈 목록이면 정규화 미적용(하위 호환).
    glossary: Optional[list[GlossaryTerm]] = None,
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
        # _candidates_for_task does synchronous OpenAI embedding I/O (cache.embed);
        # run it off the event loop so a slow embeddings call can't freeze the
        # whole server (this is the document-upload-only mapping phase — the
        # blocking embed here was the cause of the UI-generation hang).
        candidates = await asyncio.to_thread(
            _candidates_for_task,
            task=task, process=process, rules=rules,
            contexts_by_rule=ctx_by_rule, module_fqns=module_fqns,
            top_k=bl_top_k, cache=cache, actor_name_by_id=actor_name_by_id,
            glossary=glossary,
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
                # Off-loop: cache.embed makes a blocking OpenAI HTTPS call.
                qv = await asyncio.to_thread(cache.embed, " ".join(p for p in parts if p))
                rv = await asyncio.to_thread(
                    cache.embed,
                    f"{cand.context.given}\n{cand.context.when}\n{cand.context.then}",
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

    # §036 관찰성 — 정규화 활성 여부 + 후보 예산 상한(불변 확인). 후보가 늘어도
    # bl_top_k/per_task_cap는 그대로이므로 검증기 부하·사용자 노출은 불변이다.
    SmartLogger.log(
        "INFO", "Agentic retrieval done (036 term normalization)",
        category="ingestion.hybrid.agentic",
        params={
            "process_id": process.id,
            "normalize_enabled": bool(glossary) and _glossary_normalize_enabled(),
            "glossary_terms": len(glossary or []),
            "bl_top_k": bl_top_k,
            "per_task_cap": per_task_cap,
            "accepted": len(result.accepted),
        },
    )

    await sink({
        "type": "AgentDone",
        "process_id": process.id,
        "accepted": len(result.accepted),
        "total_ms": int((time.perf_counter() - started) * 1000),
    })
    return result
