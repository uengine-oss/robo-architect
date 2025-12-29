"""HTTP API for the Event Storming workshop capability (sessions + board graph)."""

from fastapi import APIRouter, HTTPException

from ...platform.observability.request_logging import RequestTimer, summarize_for_log
from ...platform.observability.smart_logger import SmartLogger
from .graph_store import graph
from .models import (
    Session,
    SessionCreate,
    SessionPhase,
    Sticker,
    StickerCreate,
    StickerUpdate,
    Connection,
    ConnectionCreate,
)

router = APIRouter(prefix="/api/sessions", tags=["sessions"])


@router.post("", response_model=Session)
async def create_session(data: SessionCreate):
    """Create a new event storming session."""
    t = RequestTimer()
    SmartLogger.log(
        "INFO",
        "event_storming.session.create.start",
        category="event_storming.http",
        params={"data": summarize_for_log(data.model_dump(mode="json"))},
    )
    try:
        session = await graph.create_session(data)
        SmartLogger.log(
            "INFO",
            "event_storming.session.create.ok",
            category="event_storming.http",
            params={
                "session_id": session.id,
                "duration_ms": t.ms(),
                "session": summarize_for_log(session.model_dump(mode="json")),
            },
        )
        return session
    except Exception as e:
        SmartLogger.log(
            "ERROR",
            "event_storming.session.create.error",
            category="event_storming.http",
            params={"duration_ms": t.ms(), "error": repr(e), "data": summarize_for_log(data.model_dump(mode="json"))},
        )
        raise


@router.get("/{session_id}", response_model=Session)
async def get_session(session_id: str):
    """Get session by ID."""
    t = RequestTimer()
    SmartLogger.log(
        "DEBUG",
        "event_storming.session.get.start",
        category="event_storming.http",
        params={"session_id": session_id},
    )
    session = await graph.get_session(session_id)
    if not session:
        SmartLogger.log(
            "INFO",
            "event_storming.session.get.not_found",
            category="event_storming.http",
            params={"session_id": session_id, "duration_ms": t.ms()},
        )
        raise HTTPException(status_code=404, detail="Session not found")
    SmartLogger.log(
        "DEBUG",
        "event_storming.session.get.ok",
        category="event_storming.http",
        params={"session_id": session_id, "duration_ms": t.ms()},
    )
    return session


@router.post("/{session_id}/start")
async def start_session(session_id: str):
    """Start the session timer."""
    t = RequestTimer()
    SmartLogger.log(
        "INFO",
        "event_storming.session.start.start",
        category="event_storming.http",
        params={"session_id": session_id},
    )
    success = await graph.start_session(session_id)
    if not success:
        SmartLogger.log(
            "INFO",
            "event_storming.session.start.not_found",
            category="event_storming.http",
            params={"session_id": session_id, "duration_ms": t.ms()},
        )
        raise HTTPException(status_code=404, detail="Session not found")
    SmartLogger.log(
        "INFO",
        "event_storming.session.start.ok",
        category="event_storming.http",
        params={"session_id": session_id, "duration_ms": t.ms()},
    )
    return {"status": "started"}


@router.patch("/{session_id}/phase")
async def update_phase(session_id: str, phase: SessionPhase):
    """Update session phase."""
    t = RequestTimer()
    SmartLogger.log(
        "INFO",
        "event_storming.session.phase.update.start",
        category="event_storming.http",
        params={"session_id": session_id, "phase": getattr(phase, "value", str(phase))},
    )
    success = await graph.update_session_phase(session_id, phase)
    if not success:
        SmartLogger.log(
            "INFO",
            "event_storming.session.phase.update.not_found",
            category="event_storming.http",
            params={"session_id": session_id, "phase": getattr(phase, "value", str(phase)), "duration_ms": t.ms()},
        )
        raise HTTPException(status_code=404, detail="Session not found")
    SmartLogger.log(
        "INFO",
        "event_storming.session.phase.update.ok",
        category="event_storming.http",
        params={"session_id": session_id, "phase": getattr(phase, "value", str(phase)), "duration_ms": t.ms()},
    )
    return {"status": "updated", "phase": phase}


# Sticker routes
@router.post("/{session_id}/stickers", response_model=Sticker)
async def create_sticker(session_id: str, data: StickerCreate):
    """Create a new sticker in session."""
    t = RequestTimer()
    SmartLogger.log(
        "INFO",
        "event_storming.sticker.create.start",
        category="event_storming.http",
        params={"session_id": session_id, "data": summarize_for_log(data.model_dump(mode="json"))},
    )
    # Verify session exists
    session = await graph.get_session(session_id)
    if not session:
        SmartLogger.log(
            "INFO",
            "event_storming.sticker.create.session_not_found",
            category="event_storming.http",
            params={"session_id": session_id, "duration_ms": t.ms()},
        )
        raise HTTPException(status_code=404, detail="Session not found")

    try:
        sticker = await graph.create_sticker(session_id, data)
        SmartLogger.log(
            "INFO",
            "event_storming.sticker.create.ok",
            category="event_storming.http",
            params={"session_id": session_id, "sticker_id": sticker.id, "duration_ms": t.ms()},
        )
        return sticker
    except Exception as e:
        SmartLogger.log(
            "ERROR",
            "event_storming.sticker.create.error",
            category="event_storming.http",
            params={
                "session_id": session_id,
                "duration_ms": t.ms(),
                "error": repr(e),
                "data": summarize_for_log(data.model_dump(mode="json")),
            },
        )
        raise


@router.get("/{session_id}/stickers", response_model=list[Sticker])
async def get_stickers(session_id: str):
    """Get all stickers in session."""
    t = RequestTimer()
    stickers = await graph.get_stickers(session_id)
    SmartLogger.log(
        "DEBUG",
        "event_storming.sticker.list.ok",
        category="event_storming.http",
        params={
            "session_id": session_id,
            "stickers": summarize_for_log([{"id": s.id, "type": s.type.value} for s in stickers]),
            "duration_ms": t.ms(),
        },
    )
    return stickers


@router.patch("/{session_id}/stickers/{sticker_id}", response_model=Sticker)
async def update_sticker(session_id: str, sticker_id: str, data: StickerUpdate):
    """Update a sticker."""
    t = RequestTimer()
    SmartLogger.log(
        "INFO",
        "event_storming.sticker.update.start",
        category="event_storming.http",
        params={"session_id": session_id, "sticker_id": sticker_id, "data": summarize_for_log(data.model_dump(mode="json"))},
    )
    sticker = await graph.update_sticker(sticker_id, data)
    if not sticker:
        SmartLogger.log(
            "INFO",
            "event_storming.sticker.update.not_found",
            category="event_storming.http",
            params={"session_id": session_id, "sticker_id": sticker_id, "duration_ms": t.ms()},
        )
        raise HTTPException(status_code=404, detail="Sticker not found")
    SmartLogger.log(
        "INFO",
        "event_storming.sticker.update.ok",
        category="event_storming.http",
        params={"session_id": session_id, "sticker_id": sticker_id, "duration_ms": t.ms()},
    )
    return sticker


@router.delete("/{session_id}/stickers/{sticker_id}")
async def delete_sticker(session_id: str, sticker_id: str):
    """Delete a sticker."""
    t = RequestTimer()
    SmartLogger.log(
        "INFO",
        "event_storming.sticker.delete.start",
        category="event_storming.http",
        params={"session_id": session_id, "sticker_id": sticker_id},
    )
    success = await graph.delete_sticker(sticker_id)
    if not success:
        SmartLogger.log(
            "INFO",
            "event_storming.sticker.delete.not_found",
            category="event_storming.http",
            params={"session_id": session_id, "sticker_id": sticker_id, "duration_ms": t.ms()},
        )
        raise HTTPException(status_code=404, detail="Sticker not found")
    SmartLogger.log(
        "INFO",
        "event_storming.sticker.delete.ok",
        category="event_storming.http",
        params={"session_id": session_id, "sticker_id": sticker_id, "duration_ms": t.ms()},
    )
    return {"status": "deleted"}


# Connection routes
@router.post("/{session_id}/connections", response_model=Connection)
async def create_connection(session_id: str, data: ConnectionCreate):
    """Create a connection between stickers."""
    t = RequestTimer()
    SmartLogger.log(
        "INFO",
        "event_storming.connection.create.start",
        category="event_storming.http",
        params={"session_id": session_id, "data": summarize_for_log(data.model_dump(mode="json"))},
    )
    try:
        connection = await graph.create_connection(data)
        SmartLogger.log(
            "INFO",
            "event_storming.connection.create.ok",
            category="event_storming.http",
            params={"session_id": session_id, "connection_id": connection.id, "duration_ms": t.ms()},
        )
        return connection
    except Exception as e:
        SmartLogger.log(
            "ERROR",
            "event_storming.connection.create.error",
            category="event_storming.http",
            params={"session_id": session_id, "duration_ms": t.ms(), "error": repr(e), "data": summarize_for_log(data.model_dump(mode="json"))},
        )
        raise


@router.get("/{session_id}/connections", response_model=list[Connection])
async def get_connections(session_id: str):
    """Get all connections in session."""
    t = RequestTimer()
    connections = await graph.get_connections(session_id)
    SmartLogger.log(
        "DEBUG",
        "event_storming.connection.list.ok",
        category="event_storming.http",
        params={
            "session_id": session_id,
            "connections": summarize_for_log(
                [{"id": c.id, "source_id": c.source_id, "target_id": c.target_id} for c in connections]
            ),
            "duration_ms": t.ms(),
        },
    )
    return connections


@router.delete("/{session_id}/connections/{connection_id}")
async def delete_connection(session_id: str, connection_id: str):
    """Delete a connection."""
    t = RequestTimer()
    SmartLogger.log(
        "INFO",
        "event_storming.connection.delete.start",
        category="event_storming.http",
        params={"session_id": session_id, "connection_id": connection_id},
    )
    success = await graph.delete_connection(connection_id)
    if not success:
        SmartLogger.log(
            "INFO",
            "event_storming.connection.delete.not_found",
            category="event_storming.http",
            params={"session_id": session_id, "connection_id": connection_id, "duration_ms": t.ms()},
        )
        raise HTTPException(status_code=404, detail="Connection not found")
    SmartLogger.log(
        "INFO",
        "event_storming.connection.delete.ok",
        category="event_storming.http",
        params={"session_id": session_id, "connection_id": connection_id, "duration_ms": t.ms()},
    )
    return {"status": "deleted"}


