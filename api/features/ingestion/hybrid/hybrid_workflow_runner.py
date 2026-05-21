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
    BpmProcess,
    BpmSequenceDTO,
    BpmSkeleton,
    HybridPhase,
    ProcessBundle,
)
from api.features.ingestion.hybrid.document_to_bpm import extract_bpm_skeleton
from api.features.ingestion.hybrid.document_to_bpm.bpmn_builder import build_bpmn_xml
from api.features.ingestion.hybrid.mapper.document_chunker import chunk_document
from api.features.ingestion.hybrid.mapper.embeddings import EmbeddingCache
from api.features.ingestion.hybrid.mapper.glossary_extractor import extract_glossary
from api.features.ingestion.hybrid.mapper.passage_retriever import (
    retrieve_passages_per_task,
)
from api.features.ingestion.hybrid.ontology.neo4j_ops import (
    clear_all_hybrid_workspace,
    relabel_pdf2bpmn_nodes,
    save_bpm_skeleton,
    save_glossary,
    save_passages,
    save_rules,
    save_session_bpmn_xml,
    save_task_passage_links,
)
from api.features.ingestion.ingestion_contracts import IngestionPhase, ProgressEvent
from api.features.ingestion.ingestion_workflow_runner import clear_event_storming_nodes
from api.features.ingestion.event_storming.neo4j_client import get_neo4j_client
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
    pdf_artifacts: Optional[list[dict[str, Optional[str]]]] = None,
) -> AsyncGenerator[ProgressEvent, None]:
    try:
        yield _ev(HybridPhase.UPLOAD, "📥 문서 준비 완료", 3, {"chars": len(content)})

        # --- Phase 1: Document → BPM (multi-process) ----------------------------------
        yield _ev(HybridPhase.DOCUMENT_BPM, "📘 문서에서 업무 프로세스(들) 추출 중...", 10)
        # A document upload regenerates from BPM up — wipe every previously
        # generated artifact (all BPM workspaces + all event-storming nodes)
        # so re-ingestion is a clean rebuild. The analyzer code-analysis
        # graph is preserved (single-label / session_id guards).
        clear_all_hybrid_workspace()
        try:
            clear_event_storming_nodes(get_neo4j_client(), session_id)
        except Exception as exc:  # noqa: BLE001 — clear is best-effort
            SmartLogger.log(
                "WARN",
                f"ES clear before hybrid BPM ingestion failed (non-fatal): {exc}",
                category="ingestion.hybrid.clear_es.error",
                params={"session_id": session_id, "error": str(exc)},
            )
        phase1 = await extract_bpm_skeleton(
            content=content, session_id=session_id,
            pdf_path=pdf_path, pdf_url=pdf_url,
            source_pdf_name=source_pdf_name,
            pdf_artifacts=pdf_artifacts,
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

        # --- Phase 3.0: Glossary (session-level, kept in pipeline — single LLM call) -----
        yield _ev(HybridPhase.MAPPING, "🧾 도메인 용어집 추출 중...", 82)
        try:
            glossary = await extract_glossary(content, skeleton)
        except Exception as e:
            SmartLogger.log(
                "WARN", "Glossary extraction failed (continuing without)",
                category="ingestion.hybrid.glossary",
                params={"error": str(e)},
            )
            glossary = []
        if glossary:
            save_glossary(session_id, glossary)
            yield _ev(
                HybridPhase.MAPPING,
                f"🧾 용어집 {len(glossary)}개 항목",
                85,
                {
                    "type": "HybridGlossary",
                    "terms": [g.model_dump() for g in glossary],
                },
            )

        # --- Phase 3 (Agentic Retrieval) + Phase 4.2 (Conditions) — DEFERRED ----------
        # Per §11 cost optimization: per-task LLM mapping + per-task condition
        # extraction are no longer auto-run for every task during ingestion.
        # The user triggers them on demand:
        #   - Single task: open Inspector panel → "🔍 이 Task 탐색하기" button
        #     calls GET /api/ingest/hybrid/task/{sid}/{tid}/retrieve (force=false
        #     hits the REALIZED_BY cache; force=true re-runs).
        #   - Whole process: Navigator process row → "🔍 전체 탐색" calls
        #     POST /api/ingest/hybrid/process/{sid}/{pid}/explore (parallel N=3,
        #     skips already-mapped tasks unless force=true).
        # Cross-process arbitration runs after every explore op (cheap when no
        # conflicts) so concurrent claims on a rule converge naturally.

        # --- Phase 4.0+4.1: Document chunk + per-task passage retrieval (cheap, kept) ---
        yield _ev(HybridPhase.ONTOLOGY, "📄 문서 구절 분할 중...", 90)
        passages = chunk_document(content)
        if passages:
            save_passages(session_id, passages)
            yield _ev(
                HybridPhase.ONTOLOGY,
                f"📄 Passage {len(passages)}개 ({passages[0].chunk_method})",
                92,
                {
                    "type": "HybridPassages",
                    "passage_count": len(passages),
                    "chunk_method": passages[0].chunk_method,
                },
            )
            cache = EmbeddingCache()
            links = retrieve_passages_per_task(skeleton, passages, cache=cache)
            save_task_passage_links(session_id, links)
            yield _ev(
                HybridPhase.ONTOLOGY,
                f"🔗 Task↔Passage 링크 {len(links)}개",
                95,
                {"type": "HybridPassageLinks", "link_count": len(links)},
            )
        else:
            yield _ev(HybridPhase.ONTOLOGY, "📄 문서 구절 없음 (skip)", 95,
                      {"type": "HybridPassages", "passage_count": 0})

        # 매핑 + 조건은 lazy. 사용자에게 다음 단계 안내.
        yield _ev(
            HybridPhase.MAPPING,
            "💤 매핑 + 조건 추출은 사용자 트리거 대기 — Task 패널의 '🔍 탐색하기' 또는 프로세스 '전체 탐색'으로 시작",
            97,
            {"type": "HybridExplorationPending"},
        )

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
