"""Redis-backed realtime workshop state.

This store is owned by the `workshop_realtime` capability, rather than a generic `db/redis` layer.
"""

import json
from typing import Optional
from urllib.parse import urlparse

import redis.asyncio as redis

from ...config import get_settings
from ...platform.observability.request_logging import RequestTimer, get_request_id, summarize_for_log
from ...platform.observability.smart_logger import SmartLogger


class WorkshopPresenceStore:
    """Redis store for realtime session state (participants, cursors, timer, drag positions)."""

    def __init__(self):
        self._client: Optional[redis.Redis] = None

    def _ctx(self) -> dict:
        rid = get_request_id()
        return {"request_id": rid} if rid else {}

    async def connect(self):
        """Establish connection to Redis."""
        t = RequestTimer()
        settings = get_settings()
        # Avoid logging secrets embedded in URLs (e.g., redis://:password@host:port/0)
        safe_redis = None
        try:
            u = urlparse(settings.redis_url)
            host = u.hostname or ""
            port = f":{u.port}" if u.port else ""
            safe_redis = f"{u.scheme}://{host}{port}{u.path or ''}"
        except Exception:
            safe_redis = "<redacted>"
        SmartLogger.log(
            "INFO",
            "redis.connect.start",
            category="workshop_realtime.presence_store",
            params={**self._ctx(), "redis": safe_redis},
        )
        self._client = redis.from_url(settings.redis_url, encoding="utf-8", decode_responses=True)
        # Test connection
        await self._client.ping()
        SmartLogger.log(
            "INFO",
            "redis.connect.ok",
            category="workshop_realtime.presence_store",
            params={**self._ctx(), "duration_ms": t.ms()},
        )

    async def disconnect(self):
        """Close Redis connection."""
        t = RequestTimer()
        if self._client:
            await self._client.close()
        SmartLogger.log(
            "INFO",
            "redis.disconnect.ok",
            category="workshop_realtime.presence_store",
            params={**self._ctx(), "duration_ms": t.ms()},
        )

    # Session state
    async def set_session_participants(self, session_id: str, participants: list[dict]):
        """Store active participants for a session."""
        t = RequestTimer()
        key = f"session:{session_id}:participants"
        await self._client.set(key, json.dumps(participants))
        await self._client.expire(key, 86400)  # 24 hours
        SmartLogger.log(
            "DEBUG",
            "presence.participants.set",
            category="workshop_realtime.presence_store",
            params={
                **self._ctx(),
                "session_id": session_id,
                "participants": summarize_for_log(participants, max_list=5000, max_dict_items=5000),
                "duration_ms": t.ms(),
            },
        )

    async def get_session_participants(self, session_id: str) -> list[dict]:
        """Get active participants for a session."""
        t = RequestTimer()
        key = f"session:{session_id}:participants"
        data = await self._client.get(key)
        out = json.loads(data) if data else []
        SmartLogger.log(
            "DEBUG",
            "presence.participants.get",
            category="workshop_realtime.presence_store",
            params={
                **self._ctx(),
                "session_id": session_id,
                "participants": summarize_for_log(out, max_list=5000, max_dict_items=5000),
                "duration_ms": t.ms(),
            },
        )
        return out

    async def add_participant(self, session_id: str, participant: dict):
        """Add a participant to session. If same name exists, update their socket ID."""
        t = RequestTimer()
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
        SmartLogger.log(
            "INFO",
            "presence.participant.add",
            category="workshop_realtime.presence_store",
            params={
                **self._ctx(),
                "session_id": session_id,
                "participant": summarize_for_log(participant),
                "is_reconnection": existing is not None,
                "participants": summarize_for_log(participants, max_list=5000, max_dict_items=5000),
                "duration_ms": t.ms(),
            },
        )
        return existing is not None  # Return True if this was a reconnection

    async def find_participant_by_name(self, session_id: str, name: str) -> Optional[dict]:
        """Find a participant by name."""
        t = RequestTimer()
        participants = await self.get_session_participants(session_id)
        out = next((p for p in participants if p.get("name") == name), None)
        SmartLogger.log(
            "DEBUG",
            "presence.participant.find_by_name",
            category="workshop_realtime.presence_store",
            params={**self._ctx(), "session_id": session_id, "name": name, "found": out is not None, "duration_ms": t.ms()},
        )
        return out

    async def remove_participant(self, session_id: str, participant_id: str):
        """Remove a participant from session by socket ID."""
        t = RequestTimer()
        participants = await self.get_session_participants(session_id)
        participants = [p for p in participants if p.get("id") != participant_id]
        await self.set_session_participants(session_id, participants)
        SmartLogger.log(
            "INFO",
            "presence.participant.remove",
            category="workshop_realtime.presence_store",
            params={
                **self._ctx(),
                "session_id": session_id,
                "participant_id": participant_id,
                "participants": summarize_for_log(participants, max_list=5000, max_dict_items=5000),
                "duration_ms": t.ms(),
            },
        )

    async def mark_participant_offline(self, session_id: str, participant_id: str):
        """Mark participant as offline but keep their data for reconnection."""
        t = RequestTimer()
        participants = await self.get_session_participants(session_id)
        for p in participants:
            if p.get("id") == participant_id:
                p["online"] = False
                p["offline_since"] = __import__("time").time()
                break
        await self.set_session_participants(session_id, participants)
        SmartLogger.log(
            "INFO",
            "presence.participant.offline",
            category="workshop_realtime.presence_store",
            params={**self._ctx(), "session_id": session_id, "participant_id": participant_id, "duration_ms": t.ms()},
        )

    # Session phase timer
    async def set_phase_timer(self, session_id: str, phase: str, end_time: float):
        """Set timer for session phase."""
        t = RequestTimer()
        key = f"session:{session_id}:phase_timer"
        await self._client.hset(key, mapping={"phase": phase, "end_time": str(end_time)})
        await self._client.expire(key, 7200)  # 2 hours
        SmartLogger.log(
            "INFO",
            "presence.phase_timer.set",
            category="workshop_realtime.presence_store",
            params={**self._ctx(), "session_id": session_id, "phase": phase, "end_time": end_time, "duration_ms": t.ms()},
        )

    async def get_phase_timer(self, session_id: str) -> Optional[dict]:
        """Get current phase timer."""
        t = RequestTimer()
        key = f"session:{session_id}:phase_timer"
        data = await self._client.hgetall(key)
        if data:
            out = {"phase": data["phase"], "end_time": float(data["end_time"])}
            SmartLogger.log(
                "DEBUG",
                "presence.phase_timer.get",
                category="workshop_realtime.presence_store",
                params={**self._ctx(), "session_id": session_id, "found": True, "duration_ms": t.ms()},
            )
            return out
        SmartLogger.log(
            "DEBUG",
            "presence.phase_timer.get",
            category="workshop_realtime.presence_store",
            params={**self._ctx(), "session_id": session_id, "found": False, "duration_ms": t.ms()},
        )
        return None

    # Real-time sticker positions (for smooth dragging)
    async def set_sticker_position(self, sticker_id: str, x: float, y: float):
        """Update sticker position in real-time."""
        t = RequestTimer()
        key = f"sticker:{sticker_id}:position"
        await self._client.hset(key, mapping={"x": str(x), "y": str(y)})
        await self._client.expire(key, 3600)  # 1 hour
        SmartLogger.log(
            "DEBUG",
            "presence.sticker_position.set",
            category="workshop_realtime.presence_store",
            params={**self._ctx(), "sticker_id": sticker_id, "x": x, "y": y, "duration_ms": t.ms()},
        )

    async def get_sticker_position(self, sticker_id: str) -> Optional[dict]:
        """Get current sticker position."""
        t = RequestTimer()
        key = f"sticker:{sticker_id}:position"
        data = await self._client.hgetall(key)
        if data:
            out = {"x": float(data["x"]), "y": float(data["y"])}
            SmartLogger.log(
                "DEBUG",
                "presence.sticker_position.get",
                category="workshop_realtime.presence_store",
                params={**self._ctx(), "sticker_id": sticker_id, "found": True, "duration_ms": t.ms()},
            )
            return out
        SmartLogger.log(
            "DEBUG",
            "presence.sticker_position.get",
            category="workshop_realtime.presence_store",
            params={**self._ctx(), "sticker_id": sticker_id, "found": False, "duration_ms": t.ms()},
        )
        return None

    # Pub/Sub for real-time events
    async def publish_event(self, channel: str, event: dict):
        """Publish event to channel."""
        t = RequestTimer()
        await self._client.publish(channel, json.dumps(event))
        SmartLogger.log(
            "DEBUG",
            "presence.pubsub.publish",
            category="workshop_realtime.presence_store",
            params={**self._ctx(), "channel": channel, "event": summarize_for_log(event), "duration_ms": t.ms()},
        )

    def subscribe(self, channel: str):
        """Subscribe to channel for events."""
        return self._client.pubsub()


# Global store instance (owned by this capability)
presence = WorkshopPresenceStore()


