"""Hybrid ingestion API router (dev-only toggle).

Endpoints:
- POST /api/ingest/hybrid/upload      — upload doc + optional analyzer_graph_ref
- GET  /api/ingest/hybrid/stream/{id} — SSE progress
- GET  /api/ingest/hybrid/bpm/{id}    — read BpmTask graph (cytoscape elements)

Reuses ingestion_sessions infrastructure so the existing floating progress panel
on the frontend works without modification.
"""

from __future__ import annotations

import asyncio
import os
import uuid
from pathlib import Path
from typing import Any, Optional

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sse_starlette.sse import EventSourceResponse
from starlette.requests import Request

from api.features.ingestion.hybrid.document_to_bpm.config import (
    a2a_pdf_tmp_dir,
    hybrid_public_base_url,
)
from api.features.ingestion.hybrid.event_storming_bridge.promote_to_es import (
    clear_promoted_nodes,
)
from api.features.ingestion.hybrid.hybrid_workflow_runner import run_hybrid_workflow
from api.features.ingestion.hybrid.ontology.neo4j_ops import (
    accept_review_mapping,
    assign_rule_to_task,
    clear_all_hybrid_workspace,
    debug_session_snapshot,
    fetch_bpm_skeleton_cytoscape,
    fetch_processes_for_session,
    fetch_rules,
    fetch_session_snapshot,
    move_rule_between_tasks,
    reject_review_mapping,
    unassign_rule_from_task,
    update_rule_es_role_manual,
)
from api.features.ingestion.hybrid.contracts import (
    ActivityRuleMapping,
    BpmActor,
    BpmProcess,
    BpmTaskDTO,
    RuleDTO,
)
from api.features.ingestion.hybrid.mapper.agentic_retriever import run_agentic_retrieval
from api.features.ingestion.hybrid.mapper.rule_context import build_rule_contexts
from api.features.ingestion.hybrid.ontology.neo4j_ops import (
    save_mappings as _save_mappings,
)
from api.platform.neo4j import get_session as _get_session
from api.features.ingestion.ingestion_contracts import IngestionPhase, ProgressEvent
from api.features.ingestion.ingestion_sessions import (
    add_event,
    create_session,
    delete_session,
    get_session,
    subscribe,
    unsubscribe,
)
from api.features.ingestion.requirements_document_text import extract_text_from_pdf
from api.platform.observability.smart_logger import SmartLogger

router = APIRouter(prefix="/api/ingest/hybrid", tags=["ingestion-hybrid"])


@router.post("/upload")
async def upload_hybrid(
    request: Request,
    file: Optional[UploadFile] = File(None),
    text: Optional[str] = Form(None),
    analyzer_graph_ref: Optional[str] = Form(None),
    display_language: Optional[str] = Form("ko"),
) -> dict[str, Any]:
    content = ""
    pdf_path: Optional[str] = None
    pdf_url: Optional[str] = None
    source_pdf_name: Optional[str] = None
    if file:
        raw = await file.read()
        filename = file.filename or ""
        if filename:
            source_pdf_name = Path(filename).name
        if filename.lower().endswith(".pdf"):
            content = extract_text_from_pdf(raw)
            # Persist the raw PDF so the external A2A pdf2bpmn service can fetch it.
            shared_dir = a2a_pdf_tmp_dir()
            os.makedirs(shared_dir, exist_ok=True)
            stored_name = f"{uuid.uuid4().hex}_{Path(filename).name or 'doc.pdf'}"
            pdf_path = str(Path(shared_dir) / stored_name)
            with open(pdf_path, "wb") as fp:
                fp.write(raw)
            # A2A server downloads via httpx — serve the PDF over HTTP.
            pdf_url = f"{hybrid_public_base_url()}/api/ingest/hybrid/pdf/{stored_name}"
            # Stash extracted text next to the PDF (Phase 3 glossary debug / re-use).
            try:
                with open(pdf_path + ".txt", "w", encoding="utf-8") as fp:
                    fp.write(content)
            except OSError:
                pass  # best-effort only
        else:
            try:
                content = raw.decode("utf-8")
            except UnicodeDecodeError:
                content = raw.decode("latin-1")
    elif text:
        content = text
    else:
        raise HTTPException(status_code=400, detail="Either 'file' or 'text' must be provided")

    if not content.strip():
        raise HTTPException(status_code=400, detail="Document content is empty")

    session = create_session()
    session.content = content
    session.source_type = "hybrid"
    session.display_language = (display_language or "ko").strip().lower() or "ko"
    # Stash analyzer_graph_ref + pdf_path on session for the runner
    setattr(session, "analyzer_graph_ref", analyzer_graph_ref)
    setattr(session, "pdf_path", pdf_path)
    setattr(session, "pdf_url", pdf_url)
    setattr(session, "source_pdf_name", source_pdf_name)

    SmartLogger.log(
        "INFO", "Hybrid ingestion session created",
        category="ingestion.hybrid.upload",
        params={"session_id": session.id, "chars": len(content), "analyzer_graph_ref": analyzer_graph_ref},
    )

    return {
        "session_id": session.id,
        "content_length": len(content),
        "source_type": "hybrid",
        "preview": content[:500] + ("..." if len(content) > 500 else ""),
    }


@router.get("/stream/{session_id}")
async def stream_hybrid(session_id: str, request: Request, reconnect: bool = False):
    session = get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    queue = subscribe(session)

    if not getattr(session, "is_workflow_running", False):
        session.is_workflow_running = True
        analyzer_graph_ref = getattr(session, "analyzer_graph_ref", None)
        pdf_path = getattr(session, "pdf_path", None)
        pdf_url = getattr(session, "pdf_url", None)
        source_pdf_name = getattr(session, "source_pdf_name", None)

        async def _run():
            try:
                async for event in run_hybrid_workflow(
                    session.id, session.content, analyzer_graph_ref,
                    pdf_path=pdf_path, pdf_url=pdf_url,
                    source_pdf_name=source_pdf_name,
                ):
                    if getattr(session, "is_cancelled", False):
                        add_event(session, ProgressEvent(
                            phase=IngestionPhase.ERROR, message="❌ 생성이 중단되었습니다",
                            progress=session.progress or 0, data={"cancelled": True},
                        ))
                        return
                    add_event(session, event)
            except Exception as e:
                add_event(session, ProgressEvent(
                    phase=IngestionPhase.ERROR, message=f"❌ 오류: {e}",
                    progress=session.progress or 0, data={"error": str(e)},
                ))
            finally:
                session.is_workflow_running = False

        session.workflow_task = asyncio.create_task(_run())

    async def event_generator():
        try:
            if reconnect and session.events:
                for stored in session.events:
                    yield {"event": "progress", "data": ProgressEvent(**stored).model_dump_json()}
            if session.status in (IngestionPhase.COMPLETE, IngestionPhase.ERROR):
                return
            while True:
                if await request.is_disconnected():
                    break
                try:
                    item = await asyncio.wait_for(queue.get(), timeout=1.0)
                except asyncio.TimeoutError:
                    continue
                yield {"event": "progress", "data": ProgressEvent(**item).model_dump_json()}
                if item.get("phase") in (IngestionPhase.COMPLETE.value, IngestionPhase.ERROR.value):
                    break
        finally:
            unsubscribe(session, queue)
            if session.status in (IngestionPhase.COMPLETE, IngestionPhase.ERROR) and not session.event_queues:
                delete_session(session_id)

    return EventSourceResponse(event_generator())


@router.get("/pdf/{filename}")
async def serve_hybrid_pdf(filename: str):
    """Serve an uploaded PDF so the external A2A service can fetch it via httpx."""
    safe = Path(filename).name  # strip any path components
    full = Path(a2a_pdf_tmp_dir()) / safe
    if not full.is_file():
        raise HTTPException(status_code=404, detail="PDF not found")
    return FileResponse(str(full), media_type="application/pdf", filename=safe)


@router.get("/bpm/{session_id}")
async def get_hybrid_bpm(session_id: str) -> dict[str, Any]:
    """Return the BpmTask graph for the BPMN panel (cytoscape elements)."""
    return fetch_bpm_skeleton_cytoscape(session_id)


@router.get("/session/{session_id}/snapshot")
async def get_session_snapshot(session_id: str) -> dict[str, Any]:
    """Full rehydration payload for a hybrid session — actors + enriched tasks +
    rules + glossary + review queue + bpmn_xml. Source of truth is Neo4j; the
    frontend uses this on cold load instead of relying on localStorage."""
    return fetch_session_snapshot(session_id)


@router.get("/task/{session_id}/{task_id}/retrieve")
async def task_agent_retrieval(session_id: str, task_id: str, request: Request):
    """SSE — stream the agentic retrieval process for a single task.

    Emits AgentStart → AgentStepModuleSearch → AgentStepBlSearch →
    AgentStepDecision → AgentFinalMatches so the frontend Inspector's
    "Agent Reasoning" section can show the pipeline live (§2.C).

    The inspector can either (a) subscribe when the user opens the panel
    and show live progress, or (b) read cached rationale from the snapshot
    (REALIZED_BY.rationale) if the session's Phase 3 already ran.
    """
    snap = fetch_session_snapshot(session_id)
    task_dict = next((t for t in snap.get("tasks", []) if t["id"] == task_id), None)
    if not task_dict:
        raise HTTPException(status_code=404, detail="Task not found")

    process_dict = None
    for p in snap.get("processes", []):
        if task_id in (p.get("task_ids") or []):
            process_dict = p
            break
    if not process_dict:
        # Fallback: synthesize a minimal process so the agent still runs.
        process_dict = {
            "id": "proc_fallback",
            "name": task_dict.get("name") or "Process",
            "domain_keywords": [],
            "task_ids": [task_id],
            "actor_ids": task_dict.get("actor_ids", []),
        }

    process = BpmProcess(
        id=process_dict["id"],
        name=process_dict.get("name") or "",
        domain_keywords=process_dict.get("domain_keywords") or [],
        source_pdf_name=process_dict.get("source_pdf_name"),
        session_id=session_id,
        actor_ids=process_dict.get("actor_ids") or [],
        task_ids=process_dict.get("task_ids") or [],
    )
    task = BpmTaskDTO(
        id=task_dict["id"],
        name=task_dict.get("name", ""),
        description=task_dict.get("description"),
        sequence_index=task_dict.get("sequence_index", 0),
        actor_ids=task_dict.get("actor_ids", []),
        source_page=task_dict.get("source_page"),
        source_section=task_dict.get("source_section"),
        process_id=process.id,
    )
    actor_id_set = set(task.actor_ids) | set(process.actor_ids)
    actors = [
        BpmActor(id=a["id"], name=a.get("name", ""), description=a.get("description"))
        for a in snap.get("actors", [])
        if a["id"] in actor_id_set
    ]
    rules = [RuleDTO(**{k: v for k, v in r.items() if k != "_hidden"})
             for r in snap.get("rules", [])]
    contexts = build_rule_contexts(rules)

    event_queue: asyncio.Queue = asyncio.Queue()

    async def sink(ev: dict) -> None:
        await event_queue.put(ev)

    async def runner_task():
        try:
            # Single-task re-retrieval: the parent process already passed the
            # batch-time process gate; recomputing the gate from this one
            # task's module score would falsely reject legitimate tasks whose
            # module score sits below 0.55 (e.g. "입력값 검증" scored 0.53
            # while the process max was 0.60). Skip the gate here.
            retrieval = await run_agentic_retrieval(
                process=process, tasks=[task], actors=actors,
                rules=rules, contexts=contexts, event_sink=sink,
                skip_process_gate=True,
            )
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
            # Replace existing mappings atomically (delete + insert). If the
            # re-retrieval returned empty, it's a real "no matches" result
            # and we clear the old mappings — but only inside the same
            # transaction so a transient failure can't wipe the DB.
            with _get_session() as s:
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
                _save_mappings(session_id, new_mappings)
            await event_queue.put({
                "type": "AgentPersisted",
                "task_id": task_id,
                "mapping_count": len(new_mappings),
            })
        except Exception as e:
            await event_queue.put({"type": "AgentError", "error": str(e)})
        finally:
            await event_queue.put({"type": "__done__"})

    asyncio.create_task(runner_task())

    async def event_gen():
        while True:
            if await request.is_disconnected():
                break
            try:
                ev = await asyncio.wait_for(event_queue.get(), timeout=30.0)
            except asyncio.TimeoutError:
                # Heartbeat so the client knows we're alive.
                yield {"event": "ping", "data": "{}"}
                continue
            if ev.get("type") == "__done__":
                break
            import json as _json
            yield {"event": "agent", "data": _json.dumps(ev, ensure_ascii=False)}

    return EventSourceResponse(event_gen())


@router.get("/debug/{session_id}")
async def debug_hybrid(session_id: str) -> dict[str, Any]:
    """Diagnostic: counts + small samples of every hybrid node label + key relationships."""
    return debug_session_snapshot(session_id)


@router.post("/review/{session_id}/{task_id}/{rule_id}/accept")
async def accept_review(session_id: str, task_id: str, rule_id: str) -> dict[str, Any]:
    """Promote a review-queue mapping into an auto REALIZED_BY edge."""
    res = accept_review_mapping(session_id, task_id, rule_id)
    if not res.get("ok"):
        raise HTTPException(status_code=404, detail=res.get("error", "not found"))
    return res


@router.post("/review/{session_id}/{task_id}/{rule_id}/reject")
async def reject_review(session_id: str, task_id: str, rule_id: str) -> dict[str, Any]:
    """Drop a review-queue mapping so it stays unmapped."""
    return reject_review_mapping(session_id, task_id, rule_id)


# ---------------------------------------------------------------------------
# BL (Rule) manual control — user moves BL between tasks or changes promotion target.
# See PRD §8.2.4.
# ---------------------------------------------------------------------------

@router.post("/rule/{session_id}/{rule_id}/unassign/{task_id}")
async def unassign_rule(session_id: str, rule_id: str, task_id: str) -> dict[str, Any]:
    """Detach a Rule from a Task (remove REALIZED_BY + ActivityMapping)."""
    return unassign_rule_from_task(session_id, rule_id, task_id)


@router.post("/rule/{session_id}/{rule_id}/assign/{task_id}")
async def assign_rule(session_id: str, rule_id: str, task_id: str) -> dict[str, Any]:
    """Manually attach a Rule to a Task (method='manual', reviewed=true)."""
    res = assign_rule_to_task(session_id, rule_id, task_id)
    if not res.get("ok"):
        raise HTTPException(status_code=404, detail=res.get("error", "not found"))
    return res


@router.post("/rule/{session_id}/{rule_id}/move/{from_task_id}/{to_task_id}")
async def move_rule(
    session_id: str, rule_id: str, from_task_id: str, to_task_id: str,
) -> dict[str, Any]:
    """Move a Rule from one Task to another in a single request."""
    res = move_rule_between_tasks(session_id, rule_id, from_task_id, to_task_id)
    if not res.get("ok"):
        raise HTTPException(status_code=400, detail=res.get("error", "move failed"))
    return res


@router.patch("/rule/{session_id}/{rule_id}/es-role")
async def set_rule_es_role(session_id: str, rule_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Override a Rule's es_role (DDD/ES promotion target). Body: {"es_role": "invariant"|...}."""
    role = (payload or {}).get("es_role") or (payload or {}).get("role")
    if not role:
        raise HTTPException(status_code=400, detail="body must include es_role")
    res = update_rule_es_role_manual(session_id, rule_id, role)
    if not res.get("ok"):
        raise HTTPException(status_code=400, detail=res.get("error", "update failed"))
    return res


@router.delete("/reset")
async def reset_hybrid_workspace() -> dict[str, Any]:
    """Wipe every hybrid-owned node (all sessions), preserving analyzer + legacy event_storming.
    Use this before starting a fresh hybrid run when analyzer DB shares the default Neo4j DB.
    Also wipes hybrid-tagged Phase 5 promotion nodes (UserStory/Event/BC/... with session_id).
    """
    deleted = clear_all_hybrid_workspace()
    # Phase 5 promoted nodes use the same labels as legacy ES but are tagged with session_id.
    # We only wipe nodes that carry a session_id (legacy ingestion ones lack it → preserved).
    from api.features.ingestion.hybrid.event_storming_bridge.promote_to_es import (
        ALL_PROMOTED_LABELS,
    )
    from api.platform.neo4j import get_session as _gs
    promoted_deleted: dict[str, int] = {}
    with _gs() as s:
        for label in ALL_PROMOTED_LABELS:
            r = s.run(
                f"MATCH (n:{label}) WHERE n.session_id IS NOT NULL "
                "WITH n, count(n) AS c DETACH DELETE n RETURN c"
            ).single()
            if r and r["c"]:
                promoted_deleted[label] = int(r["c"])
    return {"success": True, "deleted": deleted, "promoted_deleted": promoted_deleted}


# ---------------------------------------------------------------------------
# Phase 5 — Event Storming promotion (manual trigger)
# ---------------------------------------------------------------------------


@router.post("/{session_id}/promote-to-es")
async def promote_start(session_id: str) -> dict[str, Any]:
    """Start Phase 5 Event Storming promotion for a finished BPM session.

    Reuses the standard ingestion infrastructure:
      1. Create an IngestionSession with source_type="hybrid" + hybrid_source_session_id
      2. Frontend subscribes to GET /api/ingest/stream/{ingestion_session_id} (existing route)
      3. The standard ingestion workflow runs, but `user_stories` phase now branches into
         hybrid mode (build_grouped_unit_contexts_from_bpm + extract_user_stories_from_bpm_group)
         and downstream phases (Event/BC/Aggregate/Command/ReadModel/Policy/...) reuse the
         existing event_storming code unchanged.
      4. After the workflow finishes, hybrid_post_workflow_hook attaches BpmTask→US/Event/Cmd
         PROMOTED_TO bridges + cross-BC Policy auto-detection.
    """
    snap = fetch_session_snapshot(session_id)
    if not snap.get("tasks"):
        raise HTTPException(
            status_code=400,
            detail="BPM 가 아직 없습니다. Phase 1~4 (BPM 생성) 를 먼저 완료하세요.",
        )

    ingestion_session = create_session()
    ingestion_session.source_type = "hybrid"
    ingestion_session.hybrid_source_session_id = session_id
    ingestion_session.content = ""  # downstream phases don't use ctx.content in hybrid mode
    SmartLogger.log(
        "INFO", "Hybrid → Event Storming promotion session created",
        category="ingestion.hybrid.es.promote",
        params={"ingestion_session_id": ingestion_session.id, "hybrid_source_session_id": session_id},
    )
    return {
        # The frontend should subscribe to /api/ingest/stream/{ingestion_session_id}
        "ingestion_session_id": ingestion_session.id,
        "hybrid_source_session_id": session_id,
    }


@router.delete("/{session_id}/promote-to-es")
async def reset_promotion(session_id: str) -> dict[str, Any]:
    """Wipe Phase 5 promotion artifacts (UserStory/Event/BC/... with this session_id)."""
    deleted = clear_promoted_nodes(session_id)
    return {"success": True, "deleted": deleted}
