from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from starlette.requests import Request

from api.platform.neo4j import get_session
from api.platform.observability.request_logging import http_context
from api.platform.observability.smart_logger import SmartLogger

router = APIRouter()


@router.get("/history/{user_story_id}")
async def get_change_history(user_story_id: str, request: Request) -> dict[str, Any]:
    query = """
    MATCH (us:UserStory {id: $user_story_id})
    OPTIONAL MATCH (us)-[r:CHANGED_TO]->(version)
    RETURN us {.*} as current,
           collect(version {.*, changedAt: r.changedAt}) as history
    ORDER BY r.changedAt DESC
    """

    with get_session() as session:
        SmartLogger.log(
            "INFO",
            "Change history requested: returning current user story and version history.",
            category="change.history.request",
            params={**http_context(request), "inputs": {"user_story_id": user_story_id}},
        )
        result = session.run(query, user_story_id=user_story_id)
        record = result.single()

        if not record:
            SmartLogger.log(
                "WARNING",
                "Change history not found: user story id did not match any node.",
                category="change.history.not_found",
                params={**http_context(request), "inputs": {"user_story_id": user_story_id}},
            )
            raise HTTPException(status_code=404, detail=f"User story {user_story_id} not found")

        payload = {
            "current": dict(record["current"]) if record["current"] else None,
            "history": [dict(h) for h in record["history"]],
        }
        SmartLogger.log(
            "INFO",
            "Change history returned.",
            category="change.history.done",
            params={**http_context(request), "user_story_id": user_story_id, "versions": len(payload.get("history") or [])},
        )
        return payload


