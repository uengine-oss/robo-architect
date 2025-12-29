"""WebSocket handler for real-time canvas synchronization."""
import socketio
from typing import Dict, Set
from ..models.session import StickerCreate, StickerUpdate, ConnectionCreate, Position
from ..db.neo4j import db
from ..db.redis import redis_db
from ..ai.facilitator import validate_event_text

# Create Socket.IO server
sio = socketio.AsyncServer(
    async_mode='asgi',
    cors_allowed_origins='*'
)

# Track connected clients per session
session_clients: Dict[str, Set[str]] = {}


@sio.event
async def connect(sid, environ):
    """Handle client connection."""
    print(f"Client connected: {sid}")


@sio.event
async def disconnect(sid):
    """Handle client disconnection."""
    print(f"Client disconnected: {sid}")
    # Mark as offline but keep participant data for potential reconnection
    for session_id, clients in session_clients.items():
        if sid in clients:
            clients.discard(sid)
            # Mark participant as offline (don't remove completely)
            await redis_db.mark_participant_offline(session_id, sid)
            await sio.emit('participant_offline', {
                'sid': sid,
                'message': '연결이 끊어졌습니다. 재접속을 기다리는 중...'
            }, room=session_id)


@sio.event
async def join_session(sid, data):
    """
    Join a session room.
    
    data: {session_id: str, participant_name: str}
    
    If a participant with the same name already exists, they are treated as
    reconnecting (e.g., page refresh) and their session state is preserved.
    """
    session_id = data.get('session_id')
    participant_name = data.get('participant_name', 'Anonymous')
    
    if not session_id:
        await sio.emit('error', {'message': 'session_id required'}, to=sid)
        return
    
    # Verify session exists
    session = await db.get_session(session_id)
    if not session:
        await sio.emit('error', {'message': 'Session not found'}, to=sid)
        return
    
    # Check if this is a reconnection (same name)
    existing_participant = await redis_db.find_participant_by_name(session_id, participant_name)
    is_reconnection = existing_participant is not None
    
    # Join Socket.IO room
    await sio.enter_room(sid, session_id)
    
    # Track client
    if session_id not in session_clients:
        session_clients[session_id] = set()
    
    # If reconnecting, remove old socket ID from tracking
    if is_reconnection and existing_participant.get('id'):
        old_sid = existing_participant.get('id')
        session_clients[session_id].discard(old_sid)
    
    session_clients[session_id].add(sid)
    
    # Add/update participant in Redis
    await redis_db.add_participant(session_id, {
        'id': sid,
        'name': participant_name,
        'online': True
    })
    
    # Notify room (different event for reconnection vs new join)
    if is_reconnection:
        await sio.emit('participant_reconnected', {
            'sid': sid,
            'name': participant_name,
            'message': f'{participant_name}님이 다시 접속했습니다.'
        }, room=session_id)
    else:
        await sio.emit('participant_joined', {
            'sid': sid,
            'name': participant_name
        }, room=session_id)
    
    # Send current state to client (works for both new join and reconnection)
    stickers = await db.get_stickers(session_id)
    connections = await db.get_connections(session_id)
    participants = await redis_db.get_session_participants(session_id)
    
    await sio.emit('session_state', {
        'session': session.model_dump(mode='json'),
        'stickers': [s.model_dump(mode='json') for s in stickers],
        'connections': [c.model_dump(mode='json') for c in connections],
        'participants': participants,
        'is_reconnection': is_reconnection
    }, to=sid)


@sio.event
async def leave_session(sid, data):
    """Leave a session room."""
    session_id = data.get('session_id')
    
    if session_id:
        await sio.leave_room(sid, session_id)
        if session_id in session_clients:
            session_clients[session_id].discard(sid)
        await redis_db.remove_participant(session_id, sid)
        await sio.emit('participant_left', {'sid': sid}, room=session_id)


@sio.event
async def add_sticker(sid, data):
    """
    Add a new sticker to the canvas.
    
    data: {session_id, type, text, position: {x, y}, author}
    """
    session_id = data.get('session_id')
    
    try:
        sticker_data = StickerCreate(
            type=data['type'],
            text=data['text'],
            position=Position(x=data['position']['x'], y=data['position']['y']),
            author=data.get('author', 'Anonymous')
        )
        
        sticker = await db.create_sticker(session_id, sticker_data)
        
        # Broadcast to room
        response = {
            'sticker': sticker.model_dump(mode='json'),
            'author_sid': sid
        }
        
        # Validate stickers based on type
        sticker_type = sticker_data.type.value
        
        if sticker_type == 'event':
            validation = validate_event_text(sticker_data.text)
            if not validation['valid']:
                response['ai_feedback'] = {
                    'type': 'validation',
                    'sticker_id': sticker.id,
                    'issue': validation['issue'],
                    'suggestion': validation.get('suggestion'),
                    'message': validation.get('message')
                }
            else:
                # Positive feedback for correct events
                response['ai_feedback'] = {
                    'type': 'tip',
                    'sticker_id': sticker.id,
                    'message': f'좋습니다! "{sticker_data.text}"는 올바른 이벤트 형식입니다.'
                }
        elif sticker_type == 'command':
            # Check if command looks like an event
            if any(end in sticker_data.text for end in ['됨', '됐', 'ed', '었다', '했다']):
                response['ai_feedback'] = {
                    'type': 'validation',
                    'sticker_id': sticker.id,
                    'issue': 'event_not_command',
                    'message': f'이것은 이벤트처럼 보입니다. 커맨드는 명령형으로 작성하세요. (예: "주문 생성")'
                }
        elif sticker_type == 'policy':
            # Check policy format
            if not any(kw in sticker_data.text for kw in ['하면', '되면', '시', 'When', 'If', '경우']):
                response['ai_feedback'] = {
                    'type': 'tip',
                    'sticker_id': sticker.id,
                    'message': '정책은 "X가 발생하면 Y를 한다" 형식으로 작성하면 더 명확합니다.'
                }
        
        await sio.emit('sticker_added', response, room=session_id)
        
    except Exception as e:
        await sio.emit('error', {'message': str(e)}, to=sid)


@sio.event
async def update_sticker(sid, data):
    """
    Update a sticker.
    
    data: {session_id, sticker_id, text?, position?}
    """
    session_id = data.get('session_id')
    sticker_id = data.get('sticker_id')
    
    try:
        update_data = StickerUpdate(
            text=data.get('text'),
            position=Position(**data['position']) if data.get('position') else None
        )
        
        sticker = await db.update_sticker(sticker_id, update_data)
        
        if sticker:
            await sio.emit('sticker_updated', {
                'sticker': sticker.model_dump(mode='json'),
                'author_sid': sid
            }, room=session_id)
        else:
            await sio.emit('error', {'message': 'Sticker not found'}, to=sid)
            
    except Exception as e:
        await sio.emit('error', {'message': str(e)}, to=sid)


@sio.event
async def move_sticker(sid, data):
    """
    Real-time sticker movement (for smooth dragging).
    This is optimistic - only updates Redis, not Neo4j.
    
    data: {session_id, sticker_id, position: {x, y}}
    """
    session_id = data.get('session_id')
    sticker_id = data.get('sticker_id')
    position = data.get('position', {})
    
    # Update Redis for real-time sync
    await redis_db.set_sticker_position(sticker_id, position.get('x', 0), position.get('y', 0))
    
    # Broadcast to others (exclude sender)
    await sio.emit('sticker_moved', {
        'sticker_id': sticker_id,
        'position': position,
        'author_sid': sid
    }, room=session_id, skip_sid=sid)


@sio.event
async def delete_sticker(sid, data):
    """
    Delete a sticker.
    
    data: {session_id, sticker_id}
    """
    session_id = data.get('session_id')
    sticker_id = data.get('sticker_id')
    
    success = await db.delete_sticker(sticker_id)
    
    if success:
        await sio.emit('sticker_deleted', {
            'sticker_id': sticker_id,
            'author_sid': sid
        }, room=session_id)
    else:
        await sio.emit('error', {'message': 'Sticker not found'}, to=sid)


@sio.event
async def add_connection(sid, data):
    """
    Create a connection between stickers.
    
    data: {session_id, source_id, target_id, label?}
    """
    session_id = data.get('session_id')
    
    try:
        conn_data = ConnectionCreate(
            source_id=data['source_id'],
            target_id=data['target_id'],
            label=data.get('label')
        )
        
        connection = await db.create_connection(conn_data)
        
        await sio.emit('connection_added', {
            'connection': connection.model_dump(mode='json'),
            'author_sid': sid
        }, room=session_id)
        
    except Exception as e:
        await sio.emit('error', {'message': str(e)}, to=sid)


@sio.event
async def delete_connection(sid, data):
    """Delete a connection."""
    session_id = data.get('session_id')
    connection_id = data.get('connection_id')
    
    success = await db.delete_connection(connection_id)
    
    if success:
        await sio.emit('connection_deleted', {
            'connection_id': connection_id,
            'author_sid': sid
        }, room=session_id)


@sio.event
async def update_phase(sid, data):
    """
    Update session phase (facilitator action).
    
    data: {session_id, phase}
    """
    session_id = data.get('session_id')
    phase = data.get('phase')
    
    success = await db.update_session_phase(session_id, phase)
    
    if success:
        await sio.emit('phase_changed', {
            'phase': phase,
            'author_sid': sid
        }, room=session_id)


@sio.event
async def start_workshop(sid, data):
    """
    Start the workshop session. Only host can do this.
    Broadcasts start time to all participants for timer sync.
    
    data: {session_id, host_name}
    """
    session_id = data.get('session_id')
    host_name = data.get('host_name', 'Host')
    
    # Mark session as started in database
    success = await db.start_session(session_id)
    
    if success:
        # Get updated session with start time
        session = await db.get_session(session_id)
        
        if session and session.started_at:
            # Broadcast to all participants
            await sio.emit('workshop_started', {
                'session_id': session_id,
                'started_at': session.started_at.isoformat(),
                'started_by': host_name,
                'duration_minutes': session.duration_minutes,
                'phase': session.phase
            }, room=session_id)
        else:
            await sio.emit('error', {'message': 'Failed to start workshop'}, to=sid)
    else:
        await sio.emit('error', {'message': 'Session not found'}, to=sid)


@sio.event
async def sync_timer(sid, data):
    """
    Request timer synchronization.
    Used when a participant joins an already-started workshop.
    
    data: {session_id}
    """
    session_id = data.get('session_id')
    
    session = await db.get_session(session_id)
    
    if session:
        await sio.emit('timer_sync', {
            'session_id': session_id,
            'started_at': session.started_at.isoformat() if session.started_at else None,
            'duration_minutes': session.duration_minutes,
            'phase': session.phase
        }, to=sid)


@sio.event
async def pause_timer(sid, data):
    """
    Pause/Resume the workshop timer (host only).
    
    data: {session_id, paused: bool, elapsed_seconds: int}
    """
    session_id = data.get('session_id')
    paused = data.get('paused', True)
    elapsed_seconds = data.get('elapsed_seconds', 0)
    
    await sio.emit('timer_paused', {
        'paused': paused,
        'elapsed_seconds': elapsed_seconds,
        'author_sid': sid
    }, room=session_id)


@sio.event
async def cursor_move(sid, data):
    """
    Broadcast cursor position for collaborative awareness.
    
    data: {session_id, x, y, name}
    """
    session_id = data.get('session_id')
    
    await sio.emit('cursor_update', {
        'sid': sid,
        'x': data.get('x'),
        'y': data.get('y'),
        'name': data.get('name')
    }, room=session_id, skip_sid=sid)


@sio.event
async def ai_connected(sid, data):
    """
    Notify all participants that AI Facilitator has connected.
    The host_id indicates which client is hosting the AI connection.
    
    data: {session_id, host_id}
    """
    session_id = data.get('session_id')
    host_id = data.get('host_id')
    
    await sio.emit('ai_connected', {
        'host_id': host_id,
        'message': 'AI 퍼실리테이터가 연결되었습니다.'
    }, room=session_id)


@sio.event
async def ai_disconnected(sid, data):
    """
    Notify all participants that AI Facilitator has disconnected.
    
    data: {session_id}
    """
    session_id = data.get('session_id')
    
    await sio.emit('ai_disconnected', {
        'message': 'AI 퍼실리테이터 연결이 해제되었습니다.'
    }, room=session_id)

