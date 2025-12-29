"""Redis connection for session state and caching."""
import json
from typing import Optional
import redis.asyncio as redis
from ..config import get_settings


class RedisDB:
    """Redis database manager for real-time session state."""
    
    def __init__(self):
        self._client: Optional[redis.Redis] = None
    
    async def connect(self):
        """Establish connection to Redis."""
        settings = get_settings()
        self._client = redis.from_url(
            settings.redis_url,
            encoding="utf-8",
            decode_responses=True
        )
        # Test connection
        await self._client.ping()
    
    async def disconnect(self):
        """Close Redis connection."""
        if self._client:
            await self._client.close()
    
    # Session state
    async def set_session_participants(self, session_id: str, participants: list[dict]):
        """Store active participants for a session."""
        key = f"session:{session_id}:participants"
        await self._client.set(key, json.dumps(participants))
        await self._client.expire(key, 86400)  # 24 hours
    
    async def get_session_participants(self, session_id: str) -> list[dict]:
        """Get active participants for a session."""
        key = f"session:{session_id}:participants"
        data = await self._client.get(key)
        return json.loads(data) if data else []
    
    async def add_participant(self, session_id: str, participant: dict):
        """Add a participant to session. If same name exists, update their socket ID."""
        participants = await self.get_session_participants(session_id)
        name = participant.get("name")
        new_id = participant.get("id")
        
        # Check if participant with same name already exists
        existing = next((p for p in participants if p.get("name") == name), None)
        
        if existing:
            # Update socket ID for existing participant (reconnection)
            existing["id"] = new_id
            existing["reconnected"] = True
        else:
            # New participant
            participants.append(participant)
        
        await self.set_session_participants(session_id, participants)
        return existing is not None  # Return True if this was a reconnection
    
    async def find_participant_by_name(self, session_id: str, name: str) -> Optional[dict]:
        """Find a participant by name."""
        participants = await self.get_session_participants(session_id)
        return next((p for p in participants if p.get("name") == name), None)
    
    async def remove_participant(self, session_id: str, participant_id: str):
        """Remove a participant from session by socket ID."""
        participants = await self.get_session_participants(session_id)
        participants = [p for p in participants if p.get("id") != participant_id]
        await self.set_session_participants(session_id, participants)
    
    async def mark_participant_offline(self, session_id: str, participant_id: str):
        """Mark participant as offline but keep their data for reconnection."""
        participants = await self.get_session_participants(session_id)
        for p in participants:
            if p.get("id") == participant_id:
                p["online"] = False
                p["offline_since"] = __import__("time").time()
                break
        await self.set_session_participants(session_id, participants)
    
    # Session phase timer
    async def set_phase_timer(self, session_id: str, phase: str, end_time: float):
        """Set timer for session phase."""
        key = f"session:{session_id}:phase_timer"
        await self._client.hset(key, mapping={
            "phase": phase,
            "end_time": str(end_time)
        })
        await self._client.expire(key, 7200)  # 2 hours
    
    async def get_phase_timer(self, session_id: str) -> Optional[dict]:
        """Get current phase timer."""
        key = f"session:{session_id}:phase_timer"
        data = await self._client.hgetall(key)
        if data:
            return {
                "phase": data["phase"],
                "end_time": float(data["end_time"])
            }
        return None
    
    # Real-time sticker positions (for smooth dragging)
    async def set_sticker_position(self, sticker_id: str, x: float, y: float):
        """Update sticker position in real-time."""
        key = f"sticker:{sticker_id}:position"
        await self._client.hset(key, mapping={"x": str(x), "y": str(y)})
        await self._client.expire(key, 3600)  # 1 hour
    
    async def get_sticker_position(self, sticker_id: str) -> Optional[dict]:
        """Get current sticker position."""
        key = f"sticker:{sticker_id}:position"
        data = await self._client.hgetall(key)
        if data:
            return {"x": float(data["x"]), "y": float(data["y"])}
        return None
    
    # Pub/Sub for real-time events
    async def publish_event(self, channel: str, event: dict):
        """Publish event to channel."""
        await self._client.publish(channel, json.dumps(event))
    
    def subscribe(self, channel: str):
        """Subscribe to channel for events."""
        return self._client.pubsub()


# Global Redis instance
redis_db = RedisDB()

