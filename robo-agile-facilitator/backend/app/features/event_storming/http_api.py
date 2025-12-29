"""HTTP API for the Event Storming workshop capability (sessions + board graph)."""

from fastapi import APIRouter, HTTPException

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
    session = await graph.create_session(data)
    return session


@router.get("/{session_id}", response_model=Session)
async def get_session(session_id: str):
    """Get session by ID."""
    session = await graph.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session


@router.post("/{session_id}/start")
async def start_session(session_id: str):
    """Start the session timer."""
    success = await graph.start_session(session_id)
    if not success:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"status": "started"}


@router.patch("/{session_id}/phase")
async def update_phase(session_id: str, phase: SessionPhase):
    """Update session phase."""
    success = await graph.update_session_phase(session_id, phase)
    if not success:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"status": "updated", "phase": phase}


# Sticker routes
@router.post("/{session_id}/stickers", response_model=Sticker)
async def create_sticker(session_id: str, data: StickerCreate):
    """Create a new sticker in session."""
    # Verify session exists
    session = await graph.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    sticker = await graph.create_sticker(session_id, data)
    return sticker


@router.get("/{session_id}/stickers", response_model=list[Sticker])
async def get_stickers(session_id: str):
    """Get all stickers in session."""
    stickers = await graph.get_stickers(session_id)
    return stickers


@router.patch("/{session_id}/stickers/{sticker_id}", response_model=Sticker)
async def update_sticker(session_id: str, sticker_id: str, data: StickerUpdate):
    """Update a sticker."""
    sticker = await graph.update_sticker(sticker_id, data)
    if not sticker:
        raise HTTPException(status_code=404, detail="Sticker not found")
    return sticker


@router.delete("/{session_id}/stickers/{sticker_id}")
async def delete_sticker(session_id: str, sticker_id: str):
    """Delete a sticker."""
    success = await graph.delete_sticker(sticker_id)
    if not success:
        raise HTTPException(status_code=404, detail="Sticker not found")
    return {"status": "deleted"}


# Connection routes
@router.post("/{session_id}/connections", response_model=Connection)
async def create_connection(session_id: str, data: ConnectionCreate):
    """Create a connection between stickers."""
    connection = await graph.create_connection(data)
    return connection


@router.get("/{session_id}/connections", response_model=list[Connection])
async def get_connections(session_id: str):
    """Get all connections in session."""
    connections = await graph.get_connections(session_id)
    return connections


@router.delete("/{session_id}/connections/{connection_id}")
async def delete_connection(session_id: str, connection_id: str):
    """Delete a connection."""
    success = await graph.delete_connection(connection_id)
    if not success:
        raise HTTPException(status_code=404, detail="Connection not found")
    return {"status": "deleted"}


