"""Session management API routes."""
from fastapi import APIRouter, HTTPException
from ..models.session import (
    Session, SessionCreate, SessionPhase,
    Sticker, StickerCreate, StickerUpdate,
    Connection, ConnectionCreate
)
from ..db.neo4j import db

router = APIRouter(prefix="/api/sessions", tags=["sessions"])


@router.post("", response_model=Session)
async def create_session(data: SessionCreate):
    """Create a new event storming session."""
    session = await db.create_session(data)
    return session


@router.get("/{session_id}", response_model=Session)
async def get_session(session_id: str):
    """Get session by ID."""
    session = await db.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session


@router.post("/{session_id}/start")
async def start_session(session_id: str):
    """Start the session timer."""
    success = await db.start_session(session_id)
    if not success:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"status": "started"}


@router.patch("/{session_id}/phase")
async def update_phase(session_id: str, phase: SessionPhase):
    """Update session phase."""
    success = await db.update_session_phase(session_id, phase)
    if not success:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"status": "updated", "phase": phase}


# Sticker routes
@router.post("/{session_id}/stickers", response_model=Sticker)
async def create_sticker(session_id: str, data: StickerCreate):
    """Create a new sticker in session."""
    # Verify session exists
    session = await db.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    sticker = await db.create_sticker(session_id, data)
    return sticker


@router.get("/{session_id}/stickers", response_model=list[Sticker])
async def get_stickers(session_id: str):
    """Get all stickers in session."""
    stickers = await db.get_stickers(session_id)
    return stickers


@router.patch("/{session_id}/stickers/{sticker_id}", response_model=Sticker)
async def update_sticker(session_id: str, sticker_id: str, data: StickerUpdate):
    """Update a sticker."""
    sticker = await db.update_sticker(sticker_id, data)
    if not sticker:
        raise HTTPException(status_code=404, detail="Sticker not found")
    return sticker


@router.delete("/{session_id}/stickers/{sticker_id}")
async def delete_sticker(session_id: str, sticker_id: str):
    """Delete a sticker."""
    success = await db.delete_sticker(sticker_id)
    if not success:
        raise HTTPException(status_code=404, detail="Sticker not found")
    return {"status": "deleted"}


# Connection routes
@router.post("/{session_id}/connections", response_model=Connection)
async def create_connection(session_id: str, data: ConnectionCreate):
    """Create a connection between stickers."""
    connection = await db.create_connection(data)
    return connection


@router.get("/{session_id}/connections", response_model=list[Connection])
async def get_connections(session_id: str):
    """Get all connections in session."""
    connections = await db.get_connections(session_id)
    return connections


@router.delete("/{session_id}/connections/{connection_id}")
async def delete_connection(session_id: str, connection_id: str):
    """Delete a connection."""
    success = await db.delete_connection(connection_id)
    if not success:
        raise HTTPException(status_code=404, detail="Connection not found")
    return {"status": "deleted"}


