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
    # Source type: "rfp" | "analyzer_graph" | "figma"
    source_type: str = "rfp"
    # UI generation mode: "html" (default — legacy HTML wireframe template path)
    # or "figma" (skip HTML entirely, generate sceneGraph via the backend
    # JSX-based open-pencil agent — Phase 1 of the AI design backend port).
    ui_generation_mode: str = "html"

    # ─── Spec 017: Token counter ─────────────────────────────────────────
    # Cumulative across the run; updated by IngestionTokenCallback on every
    # successful LLM call. Reset implicitly because sessions are recreated
    # per upload.
    tokens_total: int = 0
    # Per-phase aggregation; key = `IngestionPhase` value (e.g. "extracting_events").
    tokens_by_phase: dict[str, int] = field(default_factory=dict)
    # Sticky once True — flips when at least one call was tokenized via the
    # heuristic / fallback path (D2). Drives the `~` prefix in the UI chip.
    tokens_approximate: bool = False
    # Most recent LLM call's contribution. Used for the "this call cost N"
    # diff-display in SSE; overwritten per call.
    tokens_last_call: Optional[int] = None
    # Sequence number of the most recent emitted-progress event that carried
    # `tokens_by_phase`; lets the workflow runner emit a sparse `byPhase`
    # diff (only include phases that changed since the last emit).
    _tokens_by_phase_emit_snapshot: dict[str, int] = field(default_factory=dict)

    # ─── Spec 017: Granular suspend ──────────────────────────────────────
    # User-visible suspend state machine: "running" | "suspending" | "suspended".
    # Distinct from `is_cancelled` (the trigger flag) so the UI doesn't have
    # to combine multiple booleans. Transitions:
    #   running ──user clicks 취소──▶ suspending ──gate fires──▶ suspended
    suspend_state: str = "running"
    # The phase currently executing — set by the workflow runner at each
    # phase boundary; consumed by the suspend gate's log emit and by the
    # token callback's per-phase aggregation.
    current_phase: str = ""
    # Wall-clock time of the most recent SSE progress event emit. Used by
    # IngestionTokenCallback to decide whether to schedule a synthetic
    # micro-emit (SC-003: ≤ 2 s update visibility).
    last_progress_emit_at: float = 0.0


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


