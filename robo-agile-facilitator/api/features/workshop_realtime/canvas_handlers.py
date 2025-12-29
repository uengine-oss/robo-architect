"""Socket.IO handlers for realtime board collaboration (canvas + timer + presence)."""

from typing import Dict, Set

from .server import sio
from .presence_store import presence
from ..event_storming.graph_store import graph
from ..event_storming.models import StickerCreate, StickerUpdate, ConnectionCreate, Position
from ..ai_facilitator.facilitator import validate_event_text
from ...platform.observability.request_logging import (
    RequestTimer,
    get_request_id,
    new_request_id,
    set_request_id,
    summarize_for_log,
)
from ...platform.observability.smart_logger import SmartLogger


# Track connected clients per session
session_clients: Dict[str, Set[str]] = {}


def _start_event(event: str, sid: str, data: dict | None = None) -> RequestTimer:
    """Create per-socket-event request_id for log correlation, and emit a start log."""
    rid = new_request_id("sio")
    set_request_id(rid)
    t = RequestTimer()
    SmartLogger.log(
        "INFO",
        "sio.event.start",
        category="workshop_realtime.socket",
        params={"event": event, "sid": sid, "data": summarize_for_log(data or {}), "request_id": rid},
    )
    return t


def _end_event(event: str, sid: str, t: RequestTimer, *, ok: bool, extra: dict | None = None, error: Exception | None = None) -> None:
    params = {"event": event, "sid": sid, "ok": ok, "duration_ms": t.ms()}
    if extra:
        params.update(extra)
    if error is not None:
        params["error"] = repr(error)
    rid = get_request_id()
    if rid:
        params["request_id"] = rid
    SmartLogger.log(
        "INFO" if ok else "ERROR",
        "sio.event.ok" if ok else "sio.event.error",
        category="workshop_realtime.socket",
        params=params,
    )
    set_request_id(None)


@sio.event
async def connect(sid, environ):
    """Handle client connection."""
    t = _start_event("connect", sid, {"has_environ": environ is not None})
    _end_event("connect", sid, t, ok=True)


@sio.event
async def disconnect(sid):
    """Handle client disconnection."""
    t = _start_event("disconnect", sid)
    # Mark as offline but keep participant data for potential reconnection
    for session_id, clients in session_clients.items():
        if sid in clients:
            clients.discard(sid)
            # Mark participant as offline (don't remove completely)
            await presence.mark_participant_offline(session_id, sid)
            await sio.emit(
                "participant_offline",
                {"sid": sid, "message": "연결이 끊어졌습니다. 재접속을 기다리는 중..."},
                room=session_id,
            )
            _end_event("disconnect", sid, t, ok=True, extra={"session_id": session_id})
            return
    _end_event("disconnect", sid, t, ok=True, extra={"session_id": None})


@sio.event
async def join_session(sid, data):
    """
    Join a session room.

    data: {session_id: str, participant_name: str}

    If a participant with the same name already exists, they are treated as
    reconnecting (e.g., page refresh) and their session state is preserved.
    """
    t = _start_event("join_session", sid, data)
    session_id = data.get("session_id")
    participant_name = data.get("participant_name", "Anonymous")

    if not session_id:
        await sio.emit("error", {"message": "session_id required"}, to=sid)
        _end_event("join_session", sid, t, ok=False, extra={"reason": "session_id_required"})
        return

    # Verify session exists
    session = await graph.get_session(session_id)
    if not session:
        await sio.emit("error", {"message": "Session not found"}, to=sid)
        _end_event("join_session", sid, t, ok=False, extra={"session_id": session_id, "reason": "session_not_found"})
        return

    # Check if this is a reconnection (same name)
    existing_participant = await presence.find_participant_by_name(session_id, participant_name)
    is_reconnection = existing_participant is not None

    # Join Socket.IO room
    await sio.enter_room(sid, session_id)

    # Track client
    if session_id not in session_clients:
        session_clients[session_id] = set()

    # If reconnecting, remove old socket ID from tracking
    if is_reconnection and existing_participant.get("id"):
        old_sid = existing_participant.get("id")
        session_clients[session_id].discard(old_sid)

    session_clients[session_id].add(sid)

    # Add/update participant in Redis
    await presence.add_participant(
        session_id, {"id": sid, "name": participant_name, "online": True}
    )

    # Notify room (different event for reconnection vs new join)
    if is_reconnection:
        await sio.emit(
            "participant_reconnected",
            {"sid": sid, "name": participant_name, "message": f"{participant_name}님이 다시 접속했습니다."},
            room=session_id,
        )
    else:
        await sio.emit("participant_joined", {"sid": sid, "name": participant_name}, room=session_id)

    # Send current state to client (works for both new join and reconnection)
    stickers = await graph.get_stickers(session_id)
    connections = await graph.get_connections(session_id)
    participants = await presence.get_session_participants(session_id)

    await sio.emit(
        "session_state",
        {
            "session": session.model_dump(mode="json"),
            "stickers": [s.model_dump(mode="json") for s in stickers],
            "connections": [c.model_dump(mode="json") for c in connections],
            "participants": participants,
            "is_reconnection": is_reconnection,
        },
        to=sid,
    )

    _end_event(
        "join_session",
        sid,
        t,
        ok=True,
        extra={
            "session_id": session_id,
            "participant_name": participant_name,
            "is_reconnection": is_reconnection,
            "stickers": summarize_for_log(stickers, max_list=5000, max_dict_items=5000),
            "connections": summarize_for_log(connections, max_list=5000, max_dict_items=5000),
            "participants": summarize_for_log(participants, max_list=5000, max_dict_items=5000),
        },
    )


@sio.event
async def leave_session(sid, data):
    """Leave a session room."""
    t = _start_event("leave_session", sid, data)
    session_id = data.get("session_id")

    if session_id:
        await sio.leave_room(sid, session_id)
        if session_id in session_clients:
            session_clients[session_id].discard(sid)
        await presence.remove_participant(session_id, sid)
        await sio.emit("participant_left", {"sid": sid}, room=session_id)
        _end_event("leave_session", sid, t, ok=True, extra={"session_id": session_id})
        return

    _end_event("leave_session", sid, t, ok=False, extra={"reason": "session_id_missing"})


@sio.event
async def add_sticker(sid, data):
    """
    Add a new sticker to the canvas.

    data: {session_id, type, text, position: {x, y}, author}
    """
    session_id = data.get("session_id")

    try:
        t = _start_event("add_sticker", sid, data)
        sticker_data = StickerCreate(
            type=data["type"],
            text=data["text"],
            position=Position(x=data["position"]["x"], y=data["position"]["y"]),
            author=data.get("author", "Anonymous"),
        )

        sticker = await graph.create_sticker(session_id, sticker_data)

        SmartLogger.log(
            "INFO",
            "sio.add_sticker.created",
            category="workshop_realtime.socket",
            params={
                "request_id": get_request_id(),
                "session_id": session_id,
                "sid": sid,
                "sticker_id": sticker.id,
                "type": sticker_data.type.value,
                "author": sticker_data.author,
                # Keep raw text for reproduction. Large payloads will be offloaded to detail logs.
                "text": sticker_data.text,
                "position": summarize_for_log(sticker_data.position.model_dump()),
            },
        )

        # Broadcast to room
        response = {"sticker": sticker.model_dump(mode="json"), "author_sid": sid}

        # Validate stickers based on type
        sticker_type = sticker_data.type.value

        if sticker_type == "event":
            validation = validate_event_text(sticker_data.text)
            if not validation["valid"]:
                response["ai_feedback"] = {
                    "type": "validation",
                    "sticker_id": sticker.id,
                    "issue": validation["issue"],
                    "suggestion": validation.get("suggestion"),
                    "message": validation.get("message"),
                }
            else:
                # Positive feedback for correct events
                response["ai_feedback"] = {
                    "type": "tip",
                    "sticker_id": sticker.id,
                    "message": f'좋습니다! "{sticker_data.text}"는 올바른 이벤트 형식입니다.',
                }
        elif sticker_type == "command":
            # Check if command looks like an event
            if any(end in sticker_data.text for end in ["됨", "됐", "ed", "었다", "했다"]):
                response["ai_feedback"] = {
                    "type": "validation",
                    "sticker_id": sticker.id,
                    "issue": "event_not_command",
                    "message": '이것은 이벤트처럼 보입니다. 커맨드는 명령형으로 작성하세요. (예: "주문 생성")',
                }
        elif sticker_type == "policy":
            # Check policy format
            if not any(kw in sticker_data.text for kw in ["하면", "되면", "시", "When", "If", "경우"]):
                response["ai_feedback"] = {
                    "type": "tip",
                    "sticker_id": sticker.id,
                    "message": '정책은 "X가 발생하면 Y를 한다" 형식으로 작성하면 더 명확합니다.',
                }

        ai_feedback = response.get("ai_feedback")
        SmartLogger.log(
            "INFO",
            "sio.add_sticker.feedback_decided",
            category="workshop_realtime.socket",
            params={
                "request_id": get_request_id(),
                "session_id": session_id,
                "sid": sid,
                "sticker_id": sticker.id,
                "type": sticker_type,
                "has_ai_feedback": bool(ai_feedback),
                # Keep full feedback payload (raw) for reproduction.
                "ai_feedback": summarize_for_log(ai_feedback),
            },
        )

        SmartLogger.log(
            "DEBUG",
            "sio.add_sticker.emit.sticker_added",
            category="workshop_realtime.socket",
            params={
                "request_id": get_request_id(),
                "session_id": session_id,
                "sid": sid,
                "sticker_id": sticker.id,
                "payload_keys": sorted(list(response.keys())),
            },
        )
        await sio.emit("sticker_added", response, room=session_id)

    except Exception as e:
        # Ensure we have a timer even if StickerCreate fails early.
        if "t" not in locals():
            t = _start_event("add_sticker", sid, data)
        SmartLogger.log(
            "ERROR",
            "sio.add_sticker.error",
            category="workshop_realtime.socket",
            params={
                "request_id": get_request_id(),
                "session_id": session_id,
                "sid": sid,
                "data": summarize_for_log(data or {}),
                "error": repr(e),
            },
        )
        await sio.emit("error", {"message": str(e)}, to=sid)
        _end_event("add_sticker", sid, t, ok=False, extra={"session_id": session_id}, error=e)
        return

    _end_event("add_sticker", sid, t, ok=True, extra={"session_id": session_id, "sticker_id": sticker.id, "type": sticker.type.value})


@sio.event
async def update_sticker(sid, data):
    """
    Update a sticker.

    data: {session_id, sticker_id, text?, position?}
    """
    session_id = data.get("session_id")
    sticker_id = data.get("sticker_id")

    try:
        t = _start_event("update_sticker", sid, data)
        update_data = StickerUpdate(
            text=data.get("text"),
            position=Position(**data["position"]) if data.get("position") else None,
        )

        sticker = await graph.update_sticker(sticker_id, update_data)

        if sticker:
            await sio.emit(
                "sticker_updated",
                {"sticker": sticker.model_dump(mode="json"), "author_sid": sid},
                room=session_id,
            )
        else:
            await sio.emit("error", {"message": "Sticker not found"}, to=sid)

    except Exception as e:
        if "t" not in locals():
            t = _start_event("update_sticker", sid, data)
        await sio.emit("error", {"message": str(e)}, to=sid)
        _end_event("update_sticker", sid, t, ok=False, extra={"session_id": session_id, "sticker_id": sticker_id}, error=e)
        return

    _end_event("update_sticker", sid, t, ok=True, extra={"session_id": session_id, "sticker_id": sticker_id, "found": bool(sticker)})


@sio.event
async def move_sticker(sid, data):
    """
    Real-time sticker movement (for smooth dragging).
    This is optimistic - only updates Redis, not Neo4j.

    data: {session_id, sticker_id, position: {x, y}}
    """
    # High-frequency event: keep logs at DEBUG to avoid flooding.
    rid = new_request_id("sio")
    set_request_id(rid)
    t = RequestTimer()
    session_id = data.get("session_id")
    sticker_id = data.get("sticker_id")
    position = data.get("position", {})

    SmartLogger.log(
        "DEBUG",
        "sio.move_sticker.start",
        category="workshop_realtime.socket",
        params={"session_id": session_id, "sticker_id": sticker_id, "position": summarize_for_log(position), "sid": sid},
    )

    # Update Redis for real-time sync
    await presence.set_sticker_position(sticker_id, position.get("x", 0), position.get("y", 0))

    # Broadcast to others (exclude sender)
    await sio.emit(
        "sticker_moved",
        {"sticker_id": sticker_id, "position": position, "author_sid": sid},
        room=session_id,
        skip_sid=sid,
    )

    SmartLogger.log(
        "DEBUG",
        "sio.move_sticker.ok",
        category="workshop_realtime.socket",
        params={"session_id": session_id, "sticker_id": sticker_id, "duration_ms": t.ms(), "sid": sid},
    )
    set_request_id(None)


@sio.event
async def delete_sticker(sid, data):
    """
    Delete a sticker.

    data: {session_id, sticker_id}
    """
    t = _start_event("delete_sticker", sid, data)
    session_id = data.get("session_id")
    sticker_id = data.get("sticker_id")

    success = await graph.delete_sticker(sticker_id)

    if success:
        await sio.emit("sticker_deleted", {"sticker_id": sticker_id, "author_sid": sid}, room=session_id)
        _end_event("delete_sticker", sid, t, ok=True, extra={"session_id": session_id, "sticker_id": sticker_id})
    else:
        await sio.emit("error", {"message": "Sticker not found"}, to=sid)
        _end_event("delete_sticker", sid, t, ok=False, extra={"session_id": session_id, "sticker_id": sticker_id, "reason": "not_found"})


@sio.event
async def add_connection(sid, data):
    """
    Create a connection between stickers.

    data: {session_id, source_id, target_id, label?}
    """
    session_id = data.get("session_id")

    try:
        t = _start_event("add_connection", sid, data)
        conn_data = ConnectionCreate(
            source_id=data["source_id"], target_id=data["target_id"], label=data.get("label")
        )

        connection = await graph.create_connection(conn_data)

        await sio.emit(
            "connection_added",
            {"connection": connection.model_dump(mode="json"), "author_sid": sid},
            room=session_id,
        )

    except Exception as e:
        if "t" not in locals():
            t = _start_event("add_connection", sid, data)
        await sio.emit("error", {"message": str(e)}, to=sid)
        _end_event("add_connection", sid, t, ok=False, extra={"session_id": session_id}, error=e)
        return

    _end_event("add_connection", sid, t, ok=True, extra={"session_id": session_id, "connection_id": connection.id})


@sio.event
async def delete_connection(sid, data):
    """Delete a connection."""
    t = _start_event("delete_connection", sid, data)
    session_id = data.get("session_id")
    connection_id = data.get("connection_id")

    success = await graph.delete_connection(connection_id)

    if success:
        await sio.emit(
            "connection_deleted", {"connection_id": connection_id, "author_sid": sid}, room=session_id
        )
        _end_event("delete_connection", sid, t, ok=True, extra={"session_id": session_id, "connection_id": connection_id})
        return

    _end_event("delete_connection", sid, t, ok=False, extra={"session_id": session_id, "connection_id": connection_id, "reason": "not_found"})


@sio.event
async def update_phase(sid, data):
    """
    Update session phase (facilitator action).

    data: {session_id, phase}
    """
    t = _start_event("update_phase", sid, data)
    session_id = data.get("session_id")
    phase = data.get("phase")

    success = await graph.update_session_phase(session_id, phase)

    if success:
        await sio.emit("phase_changed", {"phase": phase, "author_sid": sid}, room=session_id)
        _end_event("update_phase", sid, t, ok=True, extra={"session_id": session_id, "phase": phase})
        return

    _end_event("update_phase", sid, t, ok=False, extra={"session_id": session_id, "phase": phase, "reason": "session_not_found"})


@sio.event
async def start_workshop(sid, data):
    """
    Start the workshop session. Only host can do this.
    Broadcasts start time to all participants for timer sync.

    data: {session_id, host_name}
    """
    t = _start_event("start_workshop", sid, data)
    session_id = data.get("session_id")
    host_name = data.get("host_name", "Host")

    # Mark session as started in database
    success = await graph.start_session(session_id)

    if success:
        # Get updated session with start time
        session = await graph.get_session(session_id)

        if session and session.started_at:
            # Broadcast to all participants
            await sio.emit(
                "workshop_started",
                {
                    "session_id": session_id,
                    "started_at": session.started_at.isoformat(),
                    "started_by": host_name,
                    "duration_minutes": session.duration_minutes,
                    "phase": session.phase,
                },
                room=session_id,
            )
        else:
            await sio.emit("error", {"message": "Failed to start workshop"}, to=sid)
            _end_event("start_workshop", sid, t, ok=False, extra={"session_id": session_id, "reason": "start_time_missing"})
    else:
        await sio.emit("error", {"message": "Session not found"}, to=sid)
        _end_event("start_workshop", sid, t, ok=False, extra={"session_id": session_id, "reason": "session_not_found"})
        return

    _end_event("start_workshop", sid, t, ok=True, extra={"session_id": session_id, "host_name": host_name})


@sio.event
async def sync_timer(sid, data):
    """
    Request timer synchronization.
    Used when a participant joins an already-started workshop.

    data: {session_id}
    """
    t = _start_event("sync_timer", sid, data)
    session_id = data.get("session_id")

    session = await graph.get_session(session_id)

    if session:
        await sio.emit(
            "timer_sync",
            {
                "session_id": session_id,
                "started_at": session.started_at.isoformat() if session.started_at else None,
                "duration_minutes": session.duration_minutes,
                "phase": session.phase,
            },
            to=sid,
        )
        _end_event("sync_timer", sid, t, ok=True, extra={"session_id": session_id, "has_started_at": bool(session.started_at)})
        return

    _end_event("sync_timer", sid, t, ok=False, extra={"session_id": session_id, "reason": "session_not_found"})


@sio.event
async def pause_timer(sid, data):
    """
    Pause/Resume the workshop timer (host only).

    data: {session_id, paused: bool, elapsed_seconds: int}
    """
    t = _start_event("pause_timer", sid, data)
    session_id = data.get("session_id")
    paused = data.get("paused", True)
    elapsed_seconds = data.get("elapsed_seconds", 0)

    await sio.emit(
        "timer_paused",
        {"paused": paused, "elapsed_seconds": elapsed_seconds, "author_sid": sid},
        room=session_id,
    )
    _end_event("pause_timer", sid, t, ok=True, extra={"session_id": session_id, "paused": paused, "elapsed_seconds": elapsed_seconds})


@sio.event
async def cursor_move(sid, data):
    """
    Broadcast cursor position for collaborative awareness.

    data: {session_id, x, y, name}
    """
    # High-frequency event: keep logs at DEBUG to avoid flooding.
    rid = new_request_id("sio")
    set_request_id(rid)
    t = RequestTimer()
    session_id = data.get("session_id")

    SmartLogger.log(
        "DEBUG",
        "sio.cursor_move.start",
        category="workshop_realtime.socket",
        params={
            "session_id": session_id,
            "x": data.get("x"),
            "y": data.get("y"),
            "name": data.get("name"),
            "sid": sid,
        },
    )

    await sio.emit(
        "cursor_update",
        {"sid": sid, "x": data.get("x"), "y": data.get("y"), "name": data.get("name")},
        room=session_id,
        skip_sid=sid,
    )
    SmartLogger.log(
        "DEBUG",
        "sio.cursor_move.ok",
        category="workshop_realtime.socket",
        params={"session_id": session_id, "duration_ms": t.ms(), "sid": sid},
    )
    set_request_id(None)


@sio.event
async def ai_connected(sid, data):
    """
    Notify all participants that AI Facilitator has connected.
    The host_id indicates which client is hosting the AI connection.

    data: {session_id, host_id}
    """
    t = _start_event("ai_connected", sid, data)
    session_id = data.get("session_id")
    host_id = data.get("host_id")

    await sio.emit(
        "ai_connected",
        {"host_id": host_id, "message": "AI 퍼실리테이터가 연결되었습니다."},
        room=session_id,
    )
    _end_event("ai_connected", sid, t, ok=True, extra={"session_id": session_id, "host_id": host_id})


@sio.event
async def ai_disconnected(sid, data):
    """
    Notify all participants that AI Facilitator has disconnected.

    data: {session_id}
    """
    t = _start_event("ai_disconnected", sid, data)
    session_id = data.get("session_id")

    await sio.emit("ai_disconnected", {"message": "AI 퍼실리테이터 연결이 해제되었습니다."}, room=session_id)
    _end_event("ai_disconnected", sid, t, ok=True, extra={"session_id": session_id})


