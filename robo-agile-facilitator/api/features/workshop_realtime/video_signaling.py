"""WebRTC signaling for video conferencing between participants.

Note: OpenAI Realtime API uses its own WebRTC connection.
This module handles peer-to-peer video between participants only.
"""

from typing import Dict, Set

from .server import sio
from ...platform.observability.request_logging import (
    RequestTimer,
    get_request_id,
    new_request_id,
    set_request_id
)
from ...platform.observability.smart_logger import SmartLogger


# Track video peers per session
video_peers: Dict[str, Set[str]] = {}


@sio.event
async def video_join(sid, data):
    """
    Join video room for a session.

    data: {session_id, participant_name}
    """
    rid = new_request_id("sio")
    set_request_id(rid)
    t = RequestTimer()
    session_id = data.get("session_id")
    participant_name = data.get("participant_name", "Anonymous")

    if not session_id:
        SmartLogger.log(
            "INFO",
            "video.join.missing_session_id",
            category="workshop_realtime.video",
            params={"sid": sid, "duration_ms": t.ms()},
        )
        set_request_id(None)
        return

    # Ensure this socket is in the session room (robust even if join_session hasn't run yet)
    await sio.enter_room(sid, session_id)

    # Track video peer
    if session_id not in video_peers:
        video_peers[session_id] = set()

    # Get existing peers before adding new one
    existing_peers = list(video_peers[session_id])

    video_peers[session_id].add(sid)

    # Send list of existing peers to new participant
    await sio.emit("video_peers", {"peers": existing_peers}, to=sid)

    # Notify existing peers about new participant
    await sio.emit(
        "video_peer_joined",
        {"peer_id": sid, "name": participant_name},
        room=session_id,
        skip_sid=sid,
    )

    SmartLogger.log(
        "INFO",
        "video.join.ok",
        category="workshop_realtime.video",
        params={
            "request_id": get_request_id(),
            "session_id": session_id,
            "sid": sid,
            "participant_name": participant_name,
            "existing_peers_count": len(existing_peers),
            "peers_count": len(video_peers[session_id]),
            "duration_ms": t.ms(),
        },
    )
    set_request_id(None)


@sio.event
async def video_leave(sid, data):
    """Leave video room."""
    rid = new_request_id("sio")
    set_request_id(rid)
    t = RequestTimer()
    session_id = data.get("session_id")

    if session_id and session_id in video_peers:
        video_peers[session_id].discard(sid)

        await sio.emit("video_peer_left", {"peer_id": sid}, room=session_id)

        SmartLogger.log(
            "INFO",
            "video.leave.ok",
            category="workshop_realtime.video",
            params={"request_id": get_request_id(), "session_id": session_id, "sid": sid, "peers_count": len(video_peers[session_id]), "duration_ms": t.ms()},
        )
        set_request_id(None)
        return

    SmartLogger.log(
        "INFO",
        "video.leave.noop",
        category="workshop_realtime.video",
        params={"request_id": get_request_id(), "session_id": session_id, "sid": sid, "duration_ms": t.ms()},
    )
    set_request_id(None)


@sio.event
async def video_offer(sid, data):
    """
    Forward WebRTC offer to target peer.

    data: {target_id, sdp}
    """
    rid = new_request_id("sio")
    set_request_id(rid)
    t = RequestTimer()
    target_id = data.get("target_id")
    sdp = data.get("sdp") or ""

    SmartLogger.log(
        "DEBUG",
        "video.offer.forward.start",
        category="workshop_realtime.video",
        params={
            "request_id": get_request_id(),
            "from_id": sid,
            "target_id": target_id,
            "sdp_len": len(sdp),
            "sdp": sdp,
        },
    )

    await sio.emit("video_offer", {"from_id": sid, "sdp": data.get("sdp")}, to=target_id)

    SmartLogger.log(
        "DEBUG",
        "video.offer.forward.ok",
        category="workshop_realtime.video",
        params={"request_id": get_request_id(), "from_id": sid, "target_id": target_id, "duration_ms": t.ms()},
    )
    set_request_id(None)


@sio.event
async def video_answer(sid, data):
    """
    Forward WebRTC answer to target peer.

    data: {target_id, sdp}
    """
    rid = new_request_id("sio")
    set_request_id(rid)
    t = RequestTimer()
    target_id = data.get("target_id")
    sdp = data.get("sdp") or ""

    SmartLogger.log(
        "DEBUG",
        "video.answer.forward.start",
        category="workshop_realtime.video",
        params={
            "request_id": get_request_id(),
            "from_id": sid,
            "target_id": target_id,
            "sdp_len": len(sdp),
            "sdp": sdp,
        },
    )

    await sio.emit("video_answer", {"from_id": sid, "sdp": data.get("sdp")}, to=target_id)

    SmartLogger.log(
        "DEBUG",
        "video.answer.forward.ok",
        category="workshop_realtime.video",
        params={"request_id": get_request_id(), "from_id": sid, "target_id": target_id, "duration_ms": t.ms()},
    )
    set_request_id(None)


@sio.event
async def video_ice_candidate(sid, data):
    """
    Forward ICE candidate to target peer.

    data: {target_id, candidate}
    """
    rid = new_request_id("sio")
    set_request_id(rid)
    t = RequestTimer()
    target_id = data.get("target_id")
    candidate = data.get("candidate") or ""

    SmartLogger.log(
        "DEBUG",
        "video.ice.forward.start",
        category="workshop_realtime.video",
        params={
            "request_id": get_request_id(),
            "from_id": sid,
            "target_id": target_id,
            "candidate_len": len(candidate),
            "candidate": candidate,
        },
    )

    await sio.emit(
        "video_ice_candidate",
        {"from_id": sid, "candidate": data.get("candidate")},
        to=target_id,
    )

    SmartLogger.log(
        "DEBUG",
        "video.ice.forward.ok",
        category="workshop_realtime.video",
        params={"request_id": get_request_id(), "from_id": sid, "target_id": target_id, "duration_ms": t.ms()},
    )
    set_request_id(None)


@sio.event
async def video_mute(sid, data):
    """
    Notify peers about mute status change.

    data: {session_id, audio_muted, video_muted}
    """
    rid = new_request_id("sio")
    set_request_id(rid)
    t = RequestTimer()
    session_id = data.get("session_id")

    await sio.emit(
        "video_mute_status",
        {
            "peer_id": sid,
            "audio_muted": data.get("audio_muted", False),
            "video_muted": data.get("video_muted", False),
        },
        room=session_id,
        skip_sid=sid,
    )

    SmartLogger.log(
        "INFO",
        "video.mute_status.broadcast",
        category="workshop_realtime.video",
        params={
            "request_id": get_request_id(),
            "session_id": session_id,
            "peer_id": sid,
            "audio_muted": data.get("audio_muted", False),
            "video_muted": data.get("video_muted", False),
            "duration_ms": t.ms(),
        },
    )
    set_request_id(None)


@sio.event
async def screen_share_start(sid, data):
    """Notify peers that screen sharing started."""
    rid = new_request_id("sio")
    set_request_id(rid)
    t = RequestTimer()
    session_id = data.get("session_id")

    await sio.emit("screen_share_started", {"peer_id": sid}, room=session_id, skip_sid=sid)
    SmartLogger.log(
        "INFO",
        "video.screen_share.start",
        category="workshop_realtime.video",
        params={"request_id": get_request_id(), "session_id": session_id, "peer_id": sid, "duration_ms": t.ms()},
    )
    set_request_id(None)


@sio.event
async def screen_share_stop(sid, data):
    """Notify peers that screen sharing stopped."""
    rid = new_request_id("sio")
    set_request_id(rid)
    t = RequestTimer()
    session_id = data.get("session_id")

    await sio.emit("screen_share_stopped", {"peer_id": sid}, room=session_id, skip_sid=sid)
    SmartLogger.log(
        "INFO",
        "video.screen_share.stop",
        category="workshop_realtime.video",
        params={"request_id": get_request_id(), "session_id": session_id, "peer_id": sid, "duration_ms": t.ms()},
    )
    set_request_id(None)


