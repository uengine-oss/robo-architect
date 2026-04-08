"""
Ingestion API (feature router) - Document Upload and Real-time Processing

Business capability:
- Upload requirements documents (text, PDF)
- Stream real-time progress (SSE)
- Run Event Storming extraction workflow and persist to Neo4j
"""

from __future__ import annotations

import json
import os
import sys
import asyncio
from typing import Any, List, Optional

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse
from starlette.requests import Request

from api.features.ingestion.ingestion_contracts import IngestionPhase, ProgressEvent
from api.features.ingestion.langchain_cache import disable_langchain_cache, enable_langchain_cache, is_cache_enabled
from api.features.ingestion.ingestion_sessions import (
    active_session_count,
    add_event,
    create_session,
    delete_session,
    get_session,
    list_active_sessions,
    subscribe,
    unsubscribe,
    wait_if_paused,
)
from api.features.ingestion.ingestion_workflow_runner import run_ingestion_workflow
from api.features.ingestion.requirements_document_text import extract_text_from_pdf
from api.platform.observability.request_logging import (
    http_context,
    sha256_bytes,
    summarize_for_log,
)
from api.platform.observability.smart_logger import SmartLogger

# Keep a stable import root when running the API in varied contexts (dev/prod/tests).
# Historically this module was at `api/ingestion.py` and inserted the project root.
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
if _PROJECT_ROOT and _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

router = APIRouter(prefix="/api/ingest", tags=["ingestion"])


@router.post("/upload")
async def upload_document(
    request: Request,
    file: Optional[UploadFile] = File(None),
    text: Optional[str] = Form(None),
    display_language: Optional[str] = Form("ko"),
    source_type: Optional[str] = Form("rfp"),
) -> dict[str, Any]:
    """
    Upload a requirements document (text or PDF) to start ingestion.
    Returns a session_id for SSE streaming of progress.
    
    Note: Large file uploads are supported.
    Text input is limited to 1024KB due to Starlette's FormData default limit.
    For large content, please use file upload instead.
    """
    content = ""

    if file:
        file_content = await file.read()
        filename = file.filename or ""
        SmartLogger.log(
            "INFO",
            "Ingestion upload received (file): reading file bytes and extracting text.",
            category="ingestion.api.upload.inputs",
            params={
                **http_context(request),
                "inputs": {
                    "file": {
                        "filename": filename,
                        "content_type": getattr(file, "content_type", None),
                        "bytes": len(file_content),
                        "sha256": sha256_bytes(file_content),
                    },
                    "text_form_provided": bool(text),
                },
            },
        )
        SmartLogger.log(
            "INFO",
            "Upload received (file)",
            category="ingestion.api.upload",
            params={"filename": filename, "bytes": len(file_content)},
        )

        if filename.lower().endswith(".pdf"):
            content = extract_text_from_pdf(file_content)
        else:
            try:
                content = file_content.decode("utf-8")
            except UnicodeDecodeError:
                content = file_content.decode("latin-1")
    elif text:
        content = text
        SmartLogger.log(
            "INFO",
            "Ingestion upload received (text): starting ingestion session from raw text.",
            category="ingestion.api.upload.inputs",
            params={**http_context(request), "inputs": {"text": summarize_for_log(text)}},
        )
        SmartLogger.log(
            "INFO",
            "Upload received (text)",
            category="ingestion.api.upload",
            params={"text": content},
        )
    else:
        resolved_source_type_early = (source_type or "rfp").strip().lower()
        if resolved_source_type_early != "analyzer_graph":
            SmartLogger.log(
                "WARNING",
                "Ingestion upload rejected: neither 'file' nor 'text' was provided.",
                category="ingestion.api.upload.invalid",
                params=http_context(request),
            )
            raise HTTPException(status_code=400, detail="Either 'file' or 'text' must be provided")

    resolved_source_type = (source_type or "rfp").strip().lower()
    if resolved_source_type not in ("rfp", "analyzer_graph", "figma"):
        resolved_source_type = "rfp"

    if not content.strip() and resolved_source_type != "analyzer_graph":
        SmartLogger.log(
            "WARNING",
            "Ingestion upload rejected: extracted content is empty after parsing.",
            category="ingestion.api.upload.empty",
            params={**http_context(request), "content": content},
        )
        raise HTTPException(status_code=400, detail="Document content is empty")

    SmartLogger.log(
        "INFO",
        "Ingestion content prepared: extracted text ready for workflow.",
        category="ingestion.api.upload.content",
        params={
            **http_context(request),
            "content": content,
        },
    )

    session = create_session()
    session.content = content
    session.display_language = (display_language or "ko").strip().lower() or "ko"
    if session.display_language not in ("ko", "en"):
        session.display_language = "ko"
    session.source_type = resolved_source_type
    SmartLogger.log(
        "INFO",
        "Ingestion session created",
        category="ingestion.api.upload",
        params={"session_id": session.id, "display_language": session.display_language, "source_type": session.source_type},
    )

    return {"session_id": session.id, "content_length": len(content), "display_language": session.display_language, "source_type": session.source_type, "preview": content[:500] + "..." if len(content) > 500 else content}


class FigmaUploadRequest(BaseModel):
    figma_nodes: List[dict]
    source_type: str = "figma"
    display_language: str = "ko"


@router.post("/upload/figma")
async def upload_figma_document(
    request: Request,
    body: FigmaUploadRequest,
) -> dict[str, Any]:
    """
    Upload Figma node data (JSON) to start ingestion.
    Parses Figma UI element structure into requirements for Event Storming extraction.
    """
    if not body.figma_nodes:
        raise HTTPException(status_code=400, detail="figma_nodes must not be empty")

    SmartLogger.log(
        "INFO",
        "Ingestion upload received (figma): parsing Figma node changes.",
        category="ingestion.api.upload.figma",
        params={
            **http_context(request),
            "node_count": len(body.figma_nodes),
        },
    )

    # Serialize figma nodes as the content (JSON string for workflow)
    content = json.dumps(body.figma_nodes, ensure_ascii=False)

    session = create_session()
    session.content = content
    session.display_language = (body.display_language or "ko").strip().lower() or "ko"
    if session.display_language not in ("ko", "en"):
        session.display_language = "ko"
    session.source_type = "figma"

    SmartLogger.log(
        "INFO",
        "Ingestion session created (figma)",
        category="ingestion.api.upload",
        params={"session_id": session.id, "display_language": session.display_language, "source_type": "figma", "node_count": len(body.figma_nodes)},
    )

    return {
        "session_id": session.id,
        "content_length": len(content),
        "display_language": session.display_language,
        "source_type": "figma",
        "preview": f"Figma storyboard: {len(body.figma_nodes)} UI elements",
    }


@router.get("/session/{session_id}/status")
async def get_ingestion_session_status(session_id: str) -> dict[str, Any]:
    """
    Page refresh recovery / session restore helper.

    Returns whether the session is still active, plus a compact status snapshot.
    """
    session = get_session(session_id)
    if not session:
        return {"active": False, "reason": "Session not found or expired"}

    if session.status == IngestionPhase.COMPLETE:
        return {"active": False, "reason": "Session completed"}

    if session.status == IngestionPhase.ERROR:
        return {"active": False, "reason": "Session has error"}

    last_event = session.events[-1] if session.events else None
    return {
        "active": True,
        "phase": session.status.value if session.status else "processing",
        "message": (last_event.get("message") if last_event else None) or "Processing...",
        "progress": (last_event.get("progress") if last_event else None) or 0,
        "isPaused": bool(getattr(session, "is_paused", False)),
    }


@router.get("/stream/{session_id}")
async def stream_progress(session_id: str, request: Request, reconnect: bool = False):
    """
    SSE endpoint for streaming ingestion progress.
    Client should connect after receiving session_id from /upload.
    """
    session = get_session(session_id)

    if not session:
        SmartLogger.log(
            "WARNING",
            "Ingestion stream requested for missing session: client may be using an expired/invalid session_id.",
            category="ingestion.api.stream.not_found",
            params={**http_context(request), "inputs": {"session_id": session_id}, "active_sessions": active_session_count()},
        )
        raise HTTPException(status_code=404, detail="Session not found")

    SmartLogger.log(
        "INFO",
        "Ingestion stream connected: starting SSE progress events for workflow execution.",
        category="ingestion.api.stream.connected",
        params={**http_context(request), "inputs": {"session_id": session_id}},
    )

    # Create a queue for this subscriber
    subscriber_queue = subscribe(session)

    # Ensure workflow is running (single runner per session)
    if not getattr(session, "is_workflow_running", False):
        session.is_workflow_running = True

        async def _run():
            try:
                async for event in run_ingestion_workflow(session, session.content):
                    # Check cancellation before adding event
                    if getattr(session, "is_cancelled", False):
                        add_event(
                            session,
                            ProgressEvent(
                                phase=IngestionPhase.ERROR,
                                message="❌ 생성이 중단되었습니다",
                                progress=session.progress or 0,
                                data={"error": "Cancelled by user", "cancelled": True},
                            ),
                        )
                        return
                    add_event(session, event)
            except asyncio.CancelledError:
                # Task was cancelled, emit cancellation event
                add_event(
                    session,
                    ProgressEvent(
                        phase=IngestionPhase.ERROR,
                        message="❌ 생성이 중단되었습니다",
                        progress=session.progress or 0,
                        data={"error": "Cancelled by user", "cancelled": True},
                    ),
                )
                raise  # Re-raise to properly cancel the task
            except Exception as e:
                # Only emit error if not cancelled
                if not getattr(session, "is_cancelled", False):
                    add_event(
                        session,
                        ProgressEvent(
                            phase=IngestionPhase.ERROR,
                            message=f"❌ 오류 발생: {str(e)}",
                            progress=session.progress or 0,
                            data={"error": str(e)},
                        ),
                    )
            finally:
                session.is_workflow_running = False

        session.workflow_task = asyncio.create_task(_run())

    async def event_generator():
        SmartLogger.log(
            "INFO",
            "Ingestion stream generator started: emitting 'progress' SSE events.",
            category="ingestion.api.stream.generator_start",
            params={**http_context(request), "inputs": {"session_id": session_id, "reconnect": reconnect}},
        )
        try:
            # Replay stored events on reconnect (or when explicitly requested)
            if reconnect and session.events:
                for stored in session.events:
                    yield {"event": "progress", "data": ProgressEvent(**stored).model_dump_json()}

            # If already finished, stop immediately after replay (if any)
            if session.status in (IngestionPhase.COMPLETE, IngestionPhase.ERROR):
                return

            while True:
                if await request.is_disconnected():
                    break

                try:
                    item = await asyncio.wait_for(subscriber_queue.get(), timeout=1.0)
                except asyncio.TimeoutError:
                    continue

                yield {"event": "progress", "data": ProgressEvent(**item).model_dump_json()}

                if item.get("phase") in (IngestionPhase.COMPLETE.value, IngestionPhase.ERROR.value):
                    break
        finally:
            unsubscribe(session, subscriber_queue)
            # Cleanup completed sessions when no subscribers remain
            if session.status in (IngestionPhase.COMPLETE, IngestionPhase.ERROR) and not session.event_queues:
                delete_session(session_id)
                SmartLogger.log(
                    "INFO",
                    "Ingestion session cleaned up: workflow completed and session removed from memory.",
                    category="ingestion.api.stream.cleaned",
                    params={**http_context(request), "inputs": {"session_id": session_id}},
                )

    return EventSourceResponse(event_generator())


@router.post("/{session_id}/pause")
async def pause_ingestion(session_id: str, request: Request) -> dict[str, Any]:
    """
    Pause an ongoing ingestion process.

    Note: the workflow pauses at the next checkpoint (cooperative pause).
    """
    session = get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    session.is_paused = True
    SmartLogger.log(
        "INFO",
        "Ingestion paused",
        category="ingestion.api.pause",
        params={**http_context(request), "inputs": {"session_id": session_id}},
    )
    return {"success": True, "status": "paused", "session_id": session_id, "is_paused": session.is_paused}


@router.post("/{session_id}/resume")
async def resume_ingestion(session_id: str, request: Request) -> dict[str, Any]:
    """Resume a paused ingestion process."""
    session = get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    if not getattr(session, "is_paused", False):
        raise HTTPException(status_code=400, detail="Ingestion is not paused")

    session.is_paused = False
    SmartLogger.log(
        "INFO",
        "Ingestion resumed",
        category="ingestion.api.resume",
        params={**http_context(request), "inputs": {"session_id": session_id}},
    )
    return {"success": True, "status": "resumed", "session_id": session_id, "is_paused": session.is_paused}


@router.post("/{session_id}/cancel")
async def cancel_ingestion(session_id: str, request: Request) -> dict[str, Any]:
    """Cancel an ongoing ingestion process."""
    session = get_session(session_id)
    if not session:
        # Session already expired/deleted - return success since cancellation intent is clear
        SmartLogger.log(
            "INFO",
            "Cancel requested for non-existent session: session already expired/deleted, treating as success",
            category="ingestion.api.cancel.not_found",
            params={**http_context(request), "inputs": {"session_id": session_id}},
        )
        return {"success": True, "status": "cancelled", "session_id": session_id, "message": "Session already expired or completed"}

    # Mark session as cancelled
    session.is_cancelled = True
    session.is_paused = False  # Cancel overrides pause
    
    # Cancel the workflow task if it exists
    if session.workflow_task and not session.workflow_task.done():
        session.workflow_task.cancel()
        SmartLogger.log(
            "INFO",
            "Ingestion workflow task cancelled",
            category="ingestion.api.cancel",
            params={**http_context(request), "inputs": {"session_id": session_id}},
        )
    
    # Emit cancellation event
    from api.features.ingestion.ingestion_contracts import ProgressEvent, IngestionPhase
    add_event(
        session,
        ProgressEvent(
            phase=IngestionPhase.ERROR,
            message="❌ 생성이 중단되었습니다",
            progress=session.progress or 0,
            data={"error": "Cancelled by user", "cancelled": True},
        ),
    )
    
    SmartLogger.log(
        "INFO",
        "Ingestion cancelled",
        category="ingestion.api.cancel",
        params={**http_context(request), "inputs": {"session_id": session_id}},
    )
    return {"success": True, "status": "cancelled", "session_id": session_id, "is_cancelled": session.is_cancelled}


# =============================================================================
# Cache Control Endpoints
# =============================================================================


@router.get("/cache/status")
async def get_cache_status() -> dict[str, Any]:
    return {"enabled": is_cache_enabled()}


@router.post("/cache/enable")
async def enable_cache() -> dict[str, Any]:
    success = enable_langchain_cache()
    return {
        "success": success,
        "enabled": is_cache_enabled(),
        "message": "LangChain 캐시가 활성화되었습니다." if success else "캐시 활성화 실패",
    }


@router.post("/cache/disable")
async def disable_cache() -> dict[str, Any]:
    success = disable_langchain_cache()
    return {
        "success": success,
        "enabled": is_cache_enabled(),
        "message": "LangChain 캐시가 비활성화되었습니다." if success else "캐시 비활성화 실패",
    }


@router.get("/sessions")
async def list_sessions(request: Request) -> list[dict[str, Any]]:
    """List all active ingestion sessions."""
    SmartLogger.log(
        "INFO",
        "List ingestion sessions: returning in-memory active sessions.",
        category="ingestion.api.sessions.request",
        params={**http_context(request), "active": active_session_count()},
    )
    return [
        {
            "id": s.id,
            "status": s.status.value,
            "progress": s.progress,
            "message": s.message,
            "isPaused": bool(getattr(s, "is_paused", False)),
            "isWorkflowRunning": bool(getattr(s, "is_workflow_running", False)),
        }
        for s in list_active_sessions()
    ]


@router.delete("/clear-all")
async def clear_all_data(request: Request) -> dict[str, Any]:
    """
    Clear all nodes and relationships from Neo4j. Used before starting a fresh ingestion.
    """
    from api.features.ingestion.event_storming.neo4j_client import get_neo4j_client

    client = get_neo4j_client()

    try:
        SmartLogger.log(
            "WARNING",
            "Clear-all requested: deleting all nodes/relationships from Neo4j (destructive).",
            category="ingestion.api.clear_all.request",
            params=http_context(request),
        )
        with client.session() as session:
            count_query = """
            MATCH (n)
            WITH labels(n)[0] as label, count(n) as count
            RETURN collect({label: label, count: count}) as counts
            """
            result = session.run(count_query)
            record = result.single()
            before_counts = {item["label"]: item["count"] for item in record["counts"]} if record else {}

            delete_query = """
            MATCH (n)
            DETACH DELETE n
            """
            session.run(delete_query)
            SmartLogger.log(
                "INFO",
                "Clear-all completed: Neo4j graph wiped.",
                category="ingestion.api.clear_all.done",
                params={**http_context(request), "deleted": before_counts},
            )

            return {"success": True, "message": "모든 데이터가 삭제되었습니다", "deleted": before_counts}
    except Exception as e:
        SmartLogger.log(
            "ERROR",
            "Clear-all failed: Neo4j delete operation raised an exception.",
            category="ingestion.api.clear_all.error",
            params={**http_context(request), "error": {"type": type(e).__name__, "message": str(e)}},
        )
        return {"success": False, "message": f"삭제 실패: {str(e)}", "deleted": {}}


@router.get("/stats")
async def get_data_stats(request: Request) -> dict[str, Any]:
    """
    Get current data statistics from Neo4j.
    """
    from api.features.ingestion.event_storming.neo4j_client import get_neo4j_client

    client = get_neo4j_client()

    try:
        SmartLogger.log(
            "INFO",
            "Ingestion stats requested: counting Neo4j nodes by label.",
            category="ingestion.api.stats.request",
            params=http_context(request),
        )
        with client.session() as session:
            query = """
            MATCH (n)
            WITH labels(n)[0] as label, count(n) as count
            RETURN collect({label: label, count: count}) as counts
            """
            result = session.run(query)
            record = result.single()
            counts = {item["label"]: item["count"] for item in record["counts"]} if record else {}

            total = sum(counts.values())
            SmartLogger.log(
                "INFO",
                "Ingestion stats returned.",
                category="ingestion.api.stats.done",
                params={**http_context(request), "total": total, "counts": counts},
            )

            return {"total": total, "counts": counts, "hasData": total > 0}
    except Exception as e:
        SmartLogger.log(
            "ERROR",
            "Ingestion stats failed: Neo4j count query raised an exception.",
            category="ingestion.api.stats.error",
            params={**http_context(request), "error": {"type": type(e).__name__, "message": str(e)}},
        )
        return {"total": 0, "counts": {}, "hasData": False, "error": str(e)}


