"""Conversational (chat) edit routes (035).

Per-requirement-item chat where NL feedback → LLM proposes a one-shot edit
(propose→confirm). The decision (feedback + rationale + diff + actor) is saved
to the collaborative edit History and to a per-item conversation log.

  GET  /chat-edit/{scope}/{id}/stream?feedback=...   (SSE) — stream reasoning → proposal
  POST /chat-edit/{scope}/{id}/apply                  — apply edit, record history+log
  GET  /chat-edit/{scope}/{id}/log                    — conversation thread
  GET  /chat-edit/{scope}/{id}/history                — collaborative edit history

scope ∈ epic | feature | user-story  (label-agnostic via scope_io).
"""

from __future__ import annotations

import asyncio
import json
import threading

from fastapi import APIRouter, HTTPException
from sse_starlette.sse import EventSourceResponse
from starlette.requests import Request

from api.features.requirements.chat_edit import history_service as hist
from api.features.requirements.chat_edit import scope_io
from api.features.requirements.chat_edit.chat_edit_agent import stream_chat_edit
from api.features.requirements.requirements_contracts import (
    ChatEditApplyRequest,
    ChatEditApplyResponse,
    ChatEditLogEntry,
    ChatEditLogResponse,
    EditHistoryResponse,
)
from api.platform.neo4j import get_session
from api.platform.observability.smart_logger import SmartLogger

router = APIRouter()


def _check_scope(scope: str) -> None:
    if scope not in scope_io.LABELS:
        raise HTTPException(status_code=404, detail=f"Unknown scope '{scope}'")


def _existing_requirements(session, exclude_id: str) -> list[str]:
    """Brief strings for nearby requirements, for conflict/dup detection."""
    rows = session.run(
        """
        MATCH (us:UserStory) WHERE us.id <> $id
        RETURN coalesce(us.role,'') + ': ' + coalesce(us.action,'') AS s
        LIMIT 60
        """,
        id=exclude_id,
    )
    out = [r["s"] for r in rows if (r["s"] or "").strip(": ")]
    feats = session.run(
        "MATCH (f:Feature) WHERE f.id <> $id RETURN f.name AS s LIMIT 40", id=exclude_id
    )
    out += [f"[Feature] {r['s']}" for r in feats if r["s"]]
    return out


def _now_iso() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat()


@router.get("/chat-edit/{scope}/{node_id}/stream")
async def chat_edit_stream(scope: str, node_id: str, request: Request, feedback: str = ""):
    """Stream the agent's reasoning, then a final `proposal` event (SSE)."""
    _check_scope(scope)
    if not feedback.strip():
        raise HTTPException(status_code=422, detail="feedback must not be empty")

    with get_session() as session:
        state = scope_io.fetch_state(session, scope, node_id)
        if state is None:
            raise HTTPException(status_code=404, detail=f"{scope} {node_id} not found")
        existing = _existing_requirements(session, node_id)

    history_param = request.query_params.get("history")
    try:
        history = json.loads(history_param) if history_param else []
    except (ValueError, TypeError):
        history = []

    loop = asyncio.get_event_loop()
    queue: asyncio.Queue = asyncio.Queue()

    def _worker():
        try:
            for ev in stream_chat_edit(
                scope=scope, state=state, feedback=feedback,
                history=history, existing_requirements=existing,
            ):
                loop.call_soon_threadsafe(queue.put_nowait, ev)
        except Exception as exc:  # noqa: BLE001
            loop.call_soon_threadsafe(
                queue.put_nowait, {"phase": "complete", "message": f"오류: {exc}", "proposal": None}
            )
        finally:
            loop.call_soon_threadsafe(queue.put_nowait, None)

    threading.Thread(target=_worker, daemon=True).start()

    async def gen():
        while True:
            if await request.is_disconnected():
                break
            ev = await queue.get()
            if ev is None:
                break
            yield {"event": "progress", "data": json.dumps(ev, ensure_ascii=False)}
            if ev.get("phase") == "complete":
                break

    return EventSourceResponse(gen())


@router.post("/chat-edit/{scope}/{node_id}/apply", response_model=ChatEditApplyResponse)
async def chat_edit_apply(
    scope: str, node_id: str, req: ChatEditApplyRequest, request: Request
) -> ChatEditApplyResponse:
    """Apply a confirmed chat edit; record collaborative history + conversation log."""
    _check_scope(scope)
    actor = getattr(request.state, "actor", None)

    with get_session() as session:
        state = scope_io.fetch_state(session, scope, node_id)
        if state is None:
            raise HTTPException(status_code=404, detail=f"{scope} {node_id} not found")

        # Optimistic concurrency — multiple collaborators may edit the same item.
        if req.baseUpdatedAt and state.get("updatedAt") not in (None, req.baseUpdatedAt):
            raise HTTPException(
                status_code=409,
                detail={"code": "EDIT_CONFLICT", "latestUpdatedAt": state.get("updatedAt")},
            )

        changes, updated_at = scope_io.apply_edits(session, scope, node_id, req.fields)
        history_id = None
        if changes:
            history_id = hist.record_history(
                session, node_id, source="chat", changes=changes,
                actor=actor, feedback=req.feedback, rationale=req.rationale,
            )
        hist.append_chat_log(
            session,
            node_id,
            ChatEditLogEntry(
                at=_now_iso(),
                userName=getattr(actor, "name", None) or "unknown",
                userEmail=getattr(actor, "email", None) or "unknown",
                feedback=req.feedback, rationale=req.rationale, summary=req.summary,
                applied=bool(changes), changes=changes,
            ),
        )

    SmartLogger.log(
        "INFO",
        "Conversational edit applied.",
        category="requirements.chat_edit.apply",
        params={
            "scope": scope, "node_id": node_id, "changed": bool(changes),
            "fields": list(changes.keys()),
            "actor_email": getattr(actor, "email", "unknown"),
        },
    )
    return ChatEditApplyResponse(
        changed=bool(changes), updatedAt=updated_at, historyId=history_id, changes=changes
    )


@router.get("/chat-edit/{scope}/{node_id}/log", response_model=ChatEditLogResponse)
async def chat_edit_log(scope: str, node_id: str) -> ChatEditLogResponse:
    """The saved conversation/decision thread for this item."""
    _check_scope(scope)
    with get_session() as session:
        entries = hist.fetch_chat_log(session, node_id)
    return ChatEditLogResponse(entries=entries)


@router.get("/chat-edit/{scope}/{node_id}/history", response_model=EditHistoryResponse)
async def chat_edit_history(scope: str, node_id: str) -> EditHistoryResponse:
    """Collaborative edit history (newest first) for any requirement item."""
    _check_scope(scope)
    with get_session() as session:
        items = hist.fetch_history(session, node_id, limit=50)
    return EditHistoryResponse(items=items)
