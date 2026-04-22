"""
Ingestion Sessions (in-memory)

Business capability: track an ingestion run across upload -> streaming workflow execution.
"""

from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass, field
from typing import Optional

from api.features.ingestion.ingestion_contracts import CreatedObject, IngestionPhase, ProgressEvent


@dataclass
class IngestionSession:
    """Tracks state of an ingestion session."""

    id: str
    status: IngestionPhase = IngestionPhase.UPLOAD
    progress: int = 0
    message: str = ""
    events: list[dict] = field(default_factory=list)
    created_objects: list[CreatedObject] = field(default_factory=list)
    error: Optional[str] = None
    content: str = ""
    is_paused: bool = False
    is_cancelled: bool = False
    is_workflow_running: bool = False
    event_queues: list[asyncio.Queue] = field(default_factory=list)  # per-subscriber queues
    workflow_task: Optional[asyncio.Task] = None
    # Display language for UI labels: "ko" (한글) or "en" (English). Used to generate displayName on nodes/properties.
    display_language: str = "ko"
    # Source type: "rfp" | "analyzer_graph" | "figma" | "hybrid"
    source_type: str = "rfp"
    # When source_type == "hybrid": id of the upstream hybrid ingestion session
    # whose BPM (BpmTask + Rule + REALIZED_BY) is the source of UserStories.
    hybrid_source_session_id: Optional[str] = None


# Active sessions (feature-local, in-memory)
_sessions: dict[str, IngestionSession] = {}


def get_session(session_id: str) -> Optional[IngestionSession]:
    return _sessions.get(session_id)


def create_session() -> IngestionSession:
    session_id = str(uuid.uuid4())[:8]
    session = IngestionSession(id=session_id)
    _sessions[session_id] = session
    return session


def add_event(session: IngestionSession, event: ProgressEvent) -> None:
    """Add event to session, update status, and broadcast to subscribers."""
    event_dict = event.model_dump()
    session.events.append(event_dict)
    session.status = event.phase
    session.progress = event.progress
    session.message = event.message

    # Broadcast to all subscriber queues (best-effort)
    for q in list(session.event_queues):
        try:
            q.put_nowait(event_dict)
        except Exception:
            pass


async def wait_if_paused(session: IngestionSession, ctx=None, current_phase: str | None = None) -> bool:
    """
    If the ingestion session is paused, wait until it is resumed.
    After resuming, synchronize context from Neo4j if provided.

    Args:
        session: The ingestion session to check
        ctx: Optional IngestionWorkflowContext to sync after resume
        current_phase: Optional phase name to limit sync scope

    Returns True if we actually waited (was paused), False otherwise.
    """
    if not getattr(session, "is_paused", False):
        return False

    # Reduced sleep interval for faster response (0.1s instead of 0.25s)
    while getattr(session, "is_paused", False):
        await asyncio.sleep(0.1)

    # After resume, sync context from Neo4j if provided
    if ctx is not None and hasattr(ctx, "sync_from_neo4j"):
        ctx.sync_from_neo4j(up_to_phase=current_phase)

    return True


def check_pause(session: IngestionSession) -> bool:
    """
    Quick synchronous check if session is paused.
    Use this before/after long-running operations for faster pause response.
    
    Returns True if paused, False otherwise.
    """
    return getattr(session, "is_paused", False)


def subscribe(session: IngestionSession) -> asyncio.Queue:
    """Register an SSE subscriber queue for this session."""
    q: asyncio.Queue = asyncio.Queue()
    session.event_queues.append(q)
    return q


def unsubscribe(session: IngestionSession, q: asyncio.Queue) -> None:
    """Unregister an SSE subscriber queue from this session."""
    try:
        session.event_queues.remove(q)
    except ValueError:
        pass


def delete_session(session_id: str) -> None:
    _sessions.pop(session_id, None)


def list_active_sessions() -> list[IngestionSession]:
    return list(_sessions.values())


def active_session_count() -> int:
    return len(_sessions)


