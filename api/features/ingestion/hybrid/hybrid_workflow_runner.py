"""Hybrid ingestion workflow runner — 5-phase SSE streamer.

Phase 1 (document → BPM) is functional with incremental per-actor / per-task
events so the frontend BPMN canvas + navigator can update in real time.
Phases 2–5 are stubbed and emit progress events only.
"""

from __future__ import annotations

import asyncio
from typing import AsyncGenerator, Optional

from api.features.ingestion.hybrid.code_to_rules.rule_extractor import (
    extract_rules_from_analyzer_graph,
)
from api.features.ingestion.hybrid.contracts import (
    ActivityRuleMapping,
    BpmProcess,
    BpmSequenceDTO,
    BpmSkeleton,
    HybridPhase,
    ProcessBundle,
)
from api.features.ingestion.hybrid.mapper.rule_context import build_rule_contexts
from api.features.ingestion.hybrid.document_to_bpm import extract_bpm_skeleton
from api.features.ingestion.hybrid.document_to_bpm.bpmn_builder import build_bpmn_xml
from api.features.ingestion.hybrid.mapper.activity_rule_mapper import map_tasks_to_rules
from api.features.ingestion.hybrid.mapper.condition_extractor import (
    extract_conditions_for_all,
)
from api.features.ingestion.hybrid.mapper.document_chunker import chunk_document
from api.features.ingestion.hybrid.mapper.embeddings import EmbeddingCache
from api.features.ingestion.hybrid.mapper.passage_retriever import (
    retrieve_passages_per_task,
)
from api.features.ingestion.hybrid.ontology.neo4j_ops import (
    clear_hybrid_nodes,
    delete_task_rule_mapping,
    relabel_pdf2bpmn_nodes,
    replace_process_modules,
    save_bpm_skeleton,
    save_glossary,
    save_mappings,
    save_passages,
    save_rules,
    save_session_bpmn_xml,
    save_task_conditions,
    save_task_passage_links,
)
from api.features.ingestion.ingestion_contracts import IngestionPhase, ProgressEvent
from api.platform.observability.smart_logger import SmartLogger

# Small delay between incremental emits so the UI sees a smooth reveal.
_STREAM_DELAY_S = 0.12


def _ev(phase: HybridPhase, message: str, progress: int, data: dict | None = None) -> ProgressEvent:
    es_phase = IngestionPhase.COMPLETE if phase == HybridPhase.COMPLETE else (
        IngestionPhase.ERROR if phase == HybridPhase.ERROR else IngestionPhase.PARSING
    )
    payload = dict(data or {})
    payload["hybrid_phase"] = phase.value
    return ProgressEvent(phase=es_phase, message=message, progress=progress, data=payload)


async def run_hybrid_workflow(
    session_id: str,
    content: str,
    analyzer_graph_ref: Optional[str] = None,
    pdf_path: Optional[str] = None,
    pdf_url: Optional[str] = None,
    source_pdf_name: Optional[str] = None,
) -> AsyncGenerator[ProgressEvent, None]:
    try:
        yield _ev(HybridPhase.UPLOAD, "📥 문서 준비 완료", 3, {"chars": len(content)})

        # --- Phase 1: Document → BPM (multi-process) ----------------------------------
        yield _ev(HybridPhase.DOCUMENT_BPM, "📘 문서에서 업무 프로세스(들) 추출 중...", 10)
        clear_hybrid_nodes(session_id)
        phase1 = await extract_bpm_skeleton(
            content=content, session_id=session_id,
            pdf_path=pdf_path, pdf_url=pdf_url, source_pdf_name=source_pdf_name,
        )
        bundle: ProcessBundle = phase1.bundle
        src_label = "외부 A2A 서비스" if phase1.source == "a2a" else "내장 추출기"
        yield _ev(
            HybridPhase.DOCUMENT_BPM,
            f"🔌 Phase 1 소스: {src_label} · 프로세스 {len(bundle.processes)}개"
            + (f" (fallback: {phase1.error})" if phase1.error else ""),
            12,
            {
                "phase1_source": phase1.source,
                "phase1_error": phase1.error,
                "process_count": len(bundle.processes),
            },
        )

        # Reveal each Process + its actors/tasks in order.
        total_processes = len(bundle.processes)
        all_actors: list = []
        all_tasks: list = []
        all_sequences: list = []
        for p_idx, skel in enumerate(bundle.processes, start=1):
            process = skel.process
            if process is None:
                # Should not happen post-§A.0 — skip defensively.
                continue
            yield _ev(
                HybridPhase.DOCUMENT_BPM,
                f"🧭 프로세스 추출: {process.name} ({p_idx}/{total_processes})",
                12 + int(5 * p_idx / max(1, total_processes)),
                {
                    "type": "HybridProcess",
                    "process": process.model_dump(),
                    "bpmn_xml": skel.bpmn_xml,  # may be None here; final emit below fills it
                },
            )
            await asyncio.sleep(_STREAM_DELAY_S)

            # Actors for this process
            total_actors = len(skel.actors)
            for i, actor in enumerate(skel.actors, start=1):
                all_actors.append(actor)
                yield _ev(
                    HybridPhase.DOCUMENT_BPM,
                    f"👤 Actor: {actor.name} ({process.name} {i}/{total_actors})",
                    17 + int(8 * p_idx / max(1, total_processes)),
                    {
                        "type": "HybridActor",
                        "actor": actor.model_dump(),
                        "process_id": process.id,
                    },
                )
                await asyncio.sleep(_STREAM_DELAY_S)

            # Tasks for this process (canvas XML grows from the merged bundle XML)
            total_tasks = len(skel.tasks)
            revealed_tasks: list = []
            seq = skel.sequences[0] if skel.sequences else None
            for i, task in enumerate(skel.tasks, start=1):
                revealed_tasks.append(task)
                all_tasks.append(task)
                partial = BpmSkeleton(
                    actors=skel.actors,
                    tasks=revealed_tasks,
                    sequences=[
                        BpmSequenceDTO(
                            id=seq.id if seq else "seq_tmp",
                            name=seq.name if seq else "Main",
                            task_ids=[t.id for t in revealed_tasks],
                            process_id=process.id,
                        )
                    ] if seq else [],
                )
                partial_xml = build_bpmn_xml(partial)
                yield _ev(
                    HybridPhase.DOCUMENT_BPM,
                    f"🧩 Task: {task.name} ({process.name} {i}/{total_tasks})",
                    25 + int(35 * p_idx / max(1, total_processes)),
                    {
                        "type": "HybridTask",
                        "task": task.model_dump(),
                        "process_id": process.id,
                        "bpmn_xml": partial_xml,
                        "tasks_so_far": [t.model_dump() for t in revealed_tasks],
                        "actors": [a.model_dump() for a in skel.actors],
                    },
                )
                await asyncio.sleep(_STREAM_DELAY_S)
            all_sequences.extend(skel.sequences)
            # Generate per-process standalone XML if adapter didn't (native path).
            if not skel.bpmn_xml:
                try:
                    skel.bpmn_xml = build_bpmn_xml(skel)
                except Exception:
                    skel.bpmn_xml = None
            # Persist this process's subgraph + per-process XML on BpmProcess node
            save_bpm_skeleton(session_id, skel)

        # Rename pdf2bpmn's side-effect nodes (:Event/:Gateway/:Process) to :Bpmn* and
        # tag with our session_id — prevents label clash with event_storming :Event.
        _relabeled = relabel_pdf2bpmn_nodes(session_id)
        if _relabeled:
            SmartLogger.log(
                "INFO", "pdf2bpmn nodes relabeled",
                category="ingestion.hybrid.document_bpm",
                params={"session_id": session_id, **_relabeled},
            )

        # Combined canvas XML spans every process (for canvas rendering BC).
        flat_skeleton = bundle.flatten()
        final_xml = bundle.bpmn_xml or flat_skeleton.bpmn_xml or build_bpmn_xml(flat_skeleton)
        save_session_bpmn_xml(session_id, final_xml)

        # Provide a convenient alias the rest of this runner uses as the
        # flat skeleton (Phase 2+ code is still single-skeleton oriented).
        skeleton = flat_skeleton

        # Build per-process payload: process identity + its standalone BPMN XML
        process_payloads = []
        for skel in bundle.processes:
            if not skel.process:
                continue
            entry = skel.process.model_dump()
            entry["bpmn_xml"] = skel.bpmn_xml
            process_payloads.append(entry)

        yield _ev(
            HybridPhase.DOCUMENT_BPM,
            f"💾 BPM 저장 완료 (Process {total_processes} / Actor {len(all_actors)} / Task {len(all_tasks)})",
            65,
            {
                "type": "HybridBpmnComplete",
                "bpmn_xml": final_xml,
                "processes": process_payloads,
                "actors": [a.model_dump() for a in all_actors],
                "tasks": [t.model_dump() for t in all_tasks],
                "sequences": [s.model_dump() for s in all_sequences],
            },
        )

        # --- Phase 2: Code → Rules ----------------------------------------------------
        yield _ev(HybridPhase.CODE_RULES, "🔍 레거시 코드에서 Business Rule(GWT) 추출 중...", 68)
        rules = await extract_rules_from_analyzer_graph(analyzer_graph_ref)
        if not rules:
            yield _ev(
                HybridPhase.CODE_RULES,
                "📐 analyzer 그래프에 BusinessLogic이 없거나 모두 인프라로 필터됨 (skip)",
                80,
                {"rule_count": 0},
            )
        else:
            total_rules = len(rules)
            for i, rule in enumerate(rules, start=1):
                yield _ev(
                    HybridPhase.CODE_RULES,
                    f"📐 Rule 추출: {rule.source_function or rule.id} ({i}/{total_rules})",
                    68 + int(12 * i / max(1, total_rules)),
                    {"type": "HybridRule", "rule": rule.model_dump()},
                )
                await asyncio.sleep(_STREAM_DELAY_S)
            save_rules(session_id, rules)
            yield _ev(
                HybridPhase.CODE_RULES,
                f"💾 Rule {total_rules}개 저장 완료",
                80,
                {
                    "type": "HybridRulesComplete",
                    "rule_count": total_rules,
                    "rules": [r.model_dump() for r in rules],
                },
            )

            # Phase 2.5 (BC pre-tagging) + Phase 2.6 (ES role pre-tagging) were
            # retired on 2026-04-21 — the decisions they tried to pre-compute
            # (Rule → BC, Rule → Aggregate/Command/Policy/etc.) require
            # process + task context that's only available after Phase 3 and
            # is properly resolved at Phase 5 (event storming promotion).
            # Pre-tagging on raw GWT alone was heuristic and added noise.
            # Fields `context_cluster` / `es_role` remain on Rule for legacy
            # sessions but are no longer populated.

        # --- Phase 3: Activity ↔ Rule mapping (Hierarchical Agentic Retrieval) --------
        yield _ev(HybridPhase.MAPPING, "🧾 도메인 용어집 + 모듈 탐색 준비 중...", 82)
        phase1_processes = [s.process for s in bundle.processes if s.process]

        # Forward per-task agent progress through the batch SSE stream so the
        # Navigator can show which task is currently being explored (§8.7 UX).
        # `map_tasks_to_rules` runs in a background task; a concurrent drain
        # loop yields HybridAgentTaskEvent ProgressEvents for each sink call.
        phase3_queue: asyncio.Queue = asyncio.Queue()

        async def _phase3_sink(event: dict) -> None:
            await phase3_queue.put(event)

        phase3_task = asyncio.create_task(map_tasks_to_rules(
            skeleton, rules,
            document_text=content,
            processes=phase1_processes,
            event_sink=_phase3_sink,
        ))

        # Build id → name so the UI can show "🔎 탐색 중: 입력값 검증" with the
        # actual task name rather than just "Task 탐색 중".
        task_name_by_id = {t.id: t.name for t in skeleton.tasks}
        task_by_id = {t.id: t for t in skeleton.tasks}
        rule_dto_by_id = {r.id: r for r in rules}
        # Pre-build rule contexts so partial-persist emits can attach function
        # info to HybridTask upserts the same way the final pass does.
        rule_contexts_by_id = {c.rule_id: c for c in build_rule_contexts(rules)}

        def _task_enrichment_payload(task_id: str, task_mappings: list) -> dict:
            """Build the HybridTask payload with rules + functions for one task."""
            rules_payload = []
            fns: dict[str, dict] = {}
            for m in task_mappings:
                rdto = rule_dto_by_id.get(m["rule_id"])
                if not rdto:
                    continue
                rules_payload.append({
                    **rdto.model_dump(),
                    "confidence": float(m["score"]),
                    "match_method": "agentic",
                    "rationale": m.get("rationale") or "",
                    "evidence_refs": list(m.get("evidence_refs") or []),
                    "evidence_path": list(m.get("evidence_path") or []),
                })
                ctx = rule_contexts_by_id.get(m["rule_id"])
                if ctx and ctx.source_function:
                    key = f"{ctx.source_module or ''}.{ctx.source_function}"
                    fns.setdefault(key, {
                        "id": key,
                        "name": ctx.source_function,
                        "module": ctx.source_module,
                        "confidence": float(m["score"]),
                        "summary": ctx.function_summary,
                    })
            task_obj = task_by_id.get(task_id)
            task_dict = task_obj.model_dump() if task_obj else {"id": task_id}
            task_dict["rules"] = rules_payload
            task_dict["functions"] = list(fns.values())
            return task_dict

        def _emit_start(ev):
            tid = ev.get("task_id")
            tname = task_name_by_id.get(tid, tid or "")
            return _ev(
                HybridPhase.MAPPING,
                f"🔎 탐색 중: {tname}",
                82,
                {
                    "type": "HybridAgentTaskEvent",
                    "event_type": "start",
                    "task_id": tid,
                    "task_name": tname,
                    "process_id": ev.get("process_id"),
                },
            )

        def _emit_end(ev):
            tid = ev.get("task_id")
            tname = task_name_by_id.get(tid, tid or "")
            count = len(ev.get("rules", []) or [])
            return _ev(
                HybridPhase.MAPPING,
                f"🎯 완료: {tname} · {count} 매핑",
                82,
                {
                    "type": "HybridAgentTaskEvent",
                    "event_type": "end",
                    "task_id": tid,
                    "task_name": tname,
                    "mapping_count": count,
                },
            )

        async def _handle_phase3_event(ev):
            """Handle a single Phase 3 event from map_tasks_to_rules.
            Returns a list of ProgressEvent to yield (0..N items)."""
            et = ev.get("type")
            outputs: list = []
            if not et:
                return outputs

            # Per-task agent progress (spinner on/off in Navigator) --------
            if et == "AgentStepBlSearch" and ev.get("task_id"):
                outputs.append(_emit_start(ev))
            elif et == "AgentFinalMatches" and ev.get("task_id"):
                outputs.append(_emit_end(ev))

            # §8.7 — per-process partial persist ---------------------------
            elif et == "ProcessMappingsPartial":
                pid = ev.get("process_id")
                raw_mappings = ev.get("mappings") or []
                if raw_mappings:
                    arm_list = [
                        ActivityRuleMapping(
                            task_id=m["task_id"], rule_id=m["rule_id"],
                            score=float(m["score"]), method="agentic",
                            reviewed=False, rationale=m.get("rationale") or "",
                            evidence_refs=list(m.get("evidence_refs") or []),
                            evidence_path=list(m.get("evidence_path") or []),
                            agent_verdict="accept",
                        )
                        for m in raw_mappings
                    ]
                    save_mappings(session_id, arm_list)
                    # Upsert each touched task so Navigator's R count + Inspector
                    # rule list reflect this process's accepts right now.
                    by_task: dict[str, list] = {}
                    for m in raw_mappings:
                        by_task.setdefault(m["task_id"], []).append(m)
                    for tid, mlist in by_task.items():
                        outputs.append(_ev(
                            HybridPhase.MAPPING,
                            f"🪄 Task 보강: {task_name_by_id.get(tid, tid)}",
                            83,
                            {
                                "type": "HybridTask",
                                "task": _task_enrichment_payload(tid, mlist),
                                "process_id": pid,
                                "partial": True,
                            },
                        ))

            # §8.7 — cross-process arbitration highlight -------------------
            elif et == "ArbitrationStart":
                contested = ev.get("contested_claims") or []
                task_ids = sorted({c["task_id"] for c in contested if c.get("task_id")})
                outputs.append(_ev(
                    HybridPhase.MAPPING,
                    f"⚖️ 중복 rule 우선순위 검증 중 ({len(contested)}건)",
                    84,
                    {
                        "type": "HybridArbitrationStart",
                        "contested_claims": contested,
                        "task_ids": task_ids,
                    },
                ))
            elif et == "ArbitrationDecision":
                losing = ev.get("losing_task_ids") or []
                rule_id = ev.get("rule_id")
                # Undo losing edges that were persisted in the partial save.
                for ltid in losing:
                    delete_task_rule_mapping(session_id, ltid, rule_id)
                outputs.append(_ev(
                    HybridPhase.MAPPING,
                    "⚖️ rule 귀속 결정",
                    84,
                    {
                        "type": "HybridArbitrationDecision",
                        "rule_id": rule_id,
                        "winning_task_id": ev.get("winning_task_id"),
                        "losing_task_ids": losing,
                        "rejected": bool(ev.get("rejected")),
                        "rationale": ev.get("rationale") or "",
                    },
                ))
            elif et == "ArbitrationEnd":
                outputs.append(_ev(
                    HybridPhase.MAPPING,
                    "✅ 중복 rule 검증 완료",
                    85,
                    {"type": "HybridArbitrationEnd"},
                ))
            return outputs

        # Drain concurrently — forward events until Phase 3 finishes.
        while not phase3_task.done():
            try:
                ev = await asyncio.wait_for(phase3_queue.get(), timeout=0.25)
            except asyncio.TimeoutError:
                continue
            for progress_ev in await _handle_phase3_event(ev):
                yield progress_ev

        # Drain residual events left in the queue after phase3_task finishes.
        while not phase3_queue.empty():
            try:
                ev = phase3_queue.get_nowait()
            except asyncio.QueueEmpty:
                break
            for progress_ev in await _handle_phase3_event(ev):
                yield progress_ev

        mapping_result = await phase3_task
        # Persist §2.F — (BpmProcess)-[:IMPLEMENTED_BY]->(MODULE) for each
        # process's Step-1 module candidates.
        for pid, entries in (mapping_result.process_modules or {}).items():
            replace_process_modules(
                session_id, pid,
                [(fqn, conf, "agent_step1") for fqn, conf in entries],
            )
        if mapping_result.glossary:
            save_glossary(session_id, mapping_result.glossary)
            yield _ev(
                HybridPhase.MAPPING,
                f"🧾 용어집 {len(mapping_result.glossary)}개 항목",
                84,
                {
                    "type": "HybridGlossary",
                    "terms": [g.model_dump() for g in mapping_result.glossary],
                },
            )

        # Build per-task enrichment payloads so the navigator tree fills in.
        ctx_by_rule = {c.rule_id: c for c in mapping_result.rule_contexts}
        rule_dto_by_id = {r.id: r for r in rules}
        task_enrich: dict[str, dict] = {t.id: {"rules": [], "functions": {}} for t in skeleton.tasks}
        for m in mapping_result.auto_matches:
            rdto = rule_dto_by_id.get(m.rule_id)
            ctx = ctx_by_rule.get(m.rule_id)
            if not rdto:
                continue
            task_enrich.setdefault(m.task_id, {"rules": [], "functions": {}})
            task_enrich[m.task_id]["rules"].append({
                **rdto.model_dump(),
                "confidence": m.score,
                "match_method": m.method,
            })
            if ctx and ctx.source_function:
                fns = task_enrich[m.task_id]["functions"]
                key = f"{ctx.source_module or ''}.{ctx.source_function}"
                fns.setdefault(key, {
                    "id": key,
                    "name": ctx.source_function,
                    "module": ctx.source_module,
                    "confidence": m.score,
                    "summary": ctx.function_summary,
                })

        if mapping_result.auto_matches:
            total_matches = len(mapping_result.auto_matches)
            for i, m in enumerate(mapping_result.auto_matches, start=1):
                yield _ev(
                    HybridPhase.MAPPING,
                    f"🔗 매핑: {m.task_id} ↔ {m.rule_id} ({m.method} {m.score:.2f}) {i}/{total_matches}",
                    85 + int(5 * i / max(1, total_matches)),
                    {"type": "HybridMapping", "mapping": m.model_dump()},
                )
                await asyncio.sleep(_STREAM_DELAY_S)

        # Push enriched task payloads so NavigatorPanel's per-task tree fills in.
        for task in skeleton.tasks:
            enrich = task_enrich.get(task.id, {})
            rules_for_task = enrich.get("rules", [])
            fns_for_task = list(enrich.get("functions", {}).values())
            if not rules_for_task and not fns_for_task:
                continue
            yield _ev(
                HybridPhase.MAPPING,
                f"🪄 Task 보강: {task.name}",
                90,
                {
                    "type": "HybridTask",
                    "task": {
                        **task.model_dump(),
                        "rules": rules_for_task,
                        "functions": fns_for_task,
                    },
                },
            )
            await asyncio.sleep(_STREAM_DELAY_S / 2)

        if mapping_result.review_matches:
            yield _ev(
                HybridPhase.MAPPING,
                f"📝 리뷰 큐 {len(mapping_result.review_matches)}건 (임계치 미달)",
                91,
                {
                    "type": "HybridReviewQueue",
                    "items": [m.model_dump() for m in mapping_result.review_matches],
                },
            )

        save_mappings(
            session_id,
            mapping_result.auto_matches,
            mapping_result.table_edges,
            review_mappings=mapping_result.review_matches,
        )

        yield _ev(
            HybridPhase.ONTOLOGY,
            f"🧠 온톨로지 업데이트: {len(mapping_result.auto_matches)} realized_by, "
            f"{len(mapping_result.table_edges)} evaluates",
            92,
            {
                "type": "HybridOntologyUpdated",
                "auto_matches": len(mapping_result.auto_matches),
                "review_matches": len(mapping_result.review_matches),
                "table_edges": len(mapping_result.table_edges),
            },
        )

        # --- Phase 4: BPM Enrichment (document passages + conditions per Task) ---------
        yield _ev(HybridPhase.ONTOLOGY, "📄 문서 구절 분할 중...", 93)
        passages = chunk_document(content)
        passages_by_task: dict[str, list] = {}
        conditions_by_task: dict[str, list[str]] = {}
        if passages:
            save_passages(session_id, passages)
            yield _ev(
                HybridPhase.ONTOLOGY,
                f"📄 Passage {len(passages)}개 ({passages[0].chunk_method})",
                94,
                {
                    "type": "HybridPassages",
                    "passage_count": len(passages),
                    "chunk_method": passages[0].chunk_method,
                },
            )

            cache = EmbeddingCache()
            links = retrieve_passages_per_task(skeleton, passages, cache=cache)
            save_task_passage_links(session_id, links)

            passage_by_id = {p.id: p for p in passages}
            for link in links:
                p = passage_by_id.get(link.passage_id)
                if p:
                    passages_by_task.setdefault(link.task_id, []).append((link, p))

            rule_by_id = {r.id: r for r in rules}
            rules_by_task: dict[str, list] = {}
            for m in mapping_result.auto_matches:
                r = rule_by_id.get(m.rule_id)
                if r:
                    rules_by_task.setdefault(m.task_id, []).append(r)

            yield _ev(HybridPhase.ONTOLOGY, "🧪 Task별 조건(condition) 추출 중...", 95)
            passages_only_by_task = {tid: [p for _, p in lst] for tid, lst in passages_by_task.items()}
            try:
                conditions_by_task = await extract_conditions_for_all(
                    skeleton, passages_only_by_task, rules_by_task,
                )
            except Exception as e:
                SmartLogger.log(
                    "WARN", "Condition extraction failed (continuing without conditions)",
                    category="ingestion.hybrid.bpm_enrich",
                    params={"error": str(e)},
                )
                conditions_by_task = {}
            if conditions_by_task:
                save_task_conditions(session_id, conditions_by_task)

            for task in skeleton.tasks:
                doc_pass = [
                    {
                        **p.model_dump(),
                        "score": link.score,
                        "rank": link.rank,
                        "low_confidence": link.low_confidence,
                    }
                    for (link, p) in passages_by_task.get(task.id, [])
                ]
                conds = conditions_by_task.get(task.id, [])
                if not doc_pass and not conds and task.id not in task_enrich:
                    continue
                prev = task_enrich.get(task.id, {})
                prev_fns_raw = prev.get("functions", {})
                prev_fns = list(prev_fns_raw.values()) if isinstance(prev_fns_raw, dict) else (prev_fns_raw or [])
                yield _ev(
                    HybridPhase.ONTOLOGY,
                    f"🪄 Task 보강(문서+조건): {task.name}",
                    96,
                    {
                        "type": "HybridTask",
                        "task": {
                            **task.model_dump(),
                            "rules": prev.get("rules", []),
                            "functions": prev_fns,
                            "document_passages": doc_pass,
                            "conditions": conds,
                        },
                    },
                )
                await asyncio.sleep(_STREAM_DELAY_S / 2)

            yield _ev(
                HybridPhase.ONTOLOGY,
                f"✨ BPM 보강 완료: {sum(1 for v in passages_by_task.values() if v)} tasks with passages, "
                f"{sum(1 for v in conditions_by_task.values() if v)} tasks with conditions",
                97,
                {
                    "type": "HybridBpmEnriched",
                    "tasks_with_passages": sum(1 for v in passages_by_task.values() if v),
                    "tasks_with_conditions": sum(1 for v in conditions_by_task.values() if v),
                },
            )
        else:
            yield _ev(HybridPhase.ONTOLOGY, "📄 문서 구절 없음 (skip)", 96, {"type": "HybridPassages", "passage_count": 0})

        # --- Phase 5: Event Storming promotion ----------------------------------------
        # NOT auto-run anymore. Triggered manually from the frontend via
        # POST /api/ingest/hybrid/{session_id}/promote-to-es so the user can review
        # the BPM before producing UserStory/Event/BC/Aggregate/Command/Policy/ReadModel.
        yield _ev(
            HybridPhase.EVENT_STORMING,
            "🛑 Phase 5 (이벤트 스토밍) 는 사용자 트리거 대기 — '이벤트 스토밍' 탭에서 시작하세요",
            99,
            {"type": "HybridPhase5Pending"},
        )

        yield _ev(HybridPhase.COMPLETE, "✅ Hybrid ingestion 완료 (BPM)", 100, {"session_id": session_id})
    except Exception as e:
        SmartLogger.log(
            "ERROR", "Hybrid ingestion failed",
            category="ingestion.hybrid.run",
            params={"session_id": session_id, "error": str(e)},
        )
        yield _ev(HybridPhase.ERROR, f"❌ 오류: {e}", 0, {"error": str(e)})
