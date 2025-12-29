"""WebRTC signaling for video conferencing between participants.

Note: OpenAI Realtime API uses its own WebRTC connection.
This module handles peer-to-peer video between participants only.
"""
import socketio
from typing import Dict, Set

# Reuse the same Socket.IO server from canvas
from .canvas import sio

# Track video peers per session
video_peers: Dict[str, Set[str]] = {}


@sio.event
async def video_join(sid, data):
    """
    Join video room for a session.
    
    data: {session_id, participant_name}
    """
    session_id = data.get('session_id')
    participant_name = data.get('participant_name', 'Anonymous')
    
    if not session_id:
        return
    
    # Track video peer
    if session_id not in video_peers:
        video_peers[session_id] = set()
    
    # Get existing peers before adding new one
    existing_peers = list(video_peers[session_id])
    
    video_peers[session_id].add(sid)
    
    # Send list of existing peers to new participant
    await sio.emit('video_peers', {
        'peers': existing_peers
    }, to=sid)
    
    # Notify existing peers about new participant
    await sio.emit('video_peer_joined', {
        'peer_id': sid,
        'name': participant_name
    }, room=session_id, skip_sid=sid)


@sio.event
async def video_leave(sid, data):
    """Leave video room."""
    session_id = data.get('session_id')
    
    if session_id and session_id in video_peers:
        video_peers[session_id].discard(sid)
        
        await sio.emit('video_peer_left', {
            'peer_id': sid
        }, room=session_id)


@sio.event
async def video_offer(sid, data):
    """
    Forward WebRTC offer to target peer.
    
    data: {target_id, sdp}
    """
    target_id = data.get('target_id')
    
    await sio.emit('video_offer', {
        'from_id': sid,
        'sdp': data.get('sdp')
    }, to=target_id)


@sio.event
async def video_answer(sid, data):
    """
    Forward WebRTC answer to target peer.
    
    data: {target_id, sdp}
    """
    target_id = data.get('target_id')
    
    await sio.emit('video_answer', {
        'from_id': sid,
        'sdp': data.get('sdp')
    }, to=target_id)


@sio.event
async def video_ice_candidate(sid, data):
    """
    Forward ICE candidate to target peer.
    
    data: {target_id, candidate}
    """
    target_id = data.get('target_id')
    
    await sio.emit('video_ice_candidate', {
        'from_id': sid,
        'candidate': data.get('candidate')
    }, to=target_id)


@sio.event
async def video_mute(sid, data):
    """
    Notify peers about mute status change.
    
    data: {session_id, audio_muted, video_muted}
    """
    session_id = data.get('session_id')
    
    await sio.emit('video_mute_status', {
        'peer_id': sid,
        'audio_muted': data.get('audio_muted', False),
        'video_muted': data.get('video_muted', False)
    }, room=session_id, skip_sid=sid)


@sio.event
async def screen_share_start(sid, data):
    """Notify peers that screen sharing started."""
    session_id = data.get('session_id')
    
    await sio.emit('screen_share_started', {
        'peer_id': sid
    }, room=session_id, skip_sid=sid)


@sio.event
async def screen_share_stop(sid, data):
    """Notify peers that screen sharing stopped."""
    session_id = data.get('session_id')
    
    await sio.emit('screen_share_stopped', {
        'peer_id': sid
    }, room=session_id, skip_sid=sid)


