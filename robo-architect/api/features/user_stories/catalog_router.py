from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from starlette.requests import Request

from api.platform.neo4j import get_session
from api.platform.observability.request_logging import http_context
from api.platform.observability.smart_logger import SmartLogger

router = APIRouter(prefix="/api/user-stories", tags=["user-stories"])


@router.get("")
async def get_all_user_stories(request: Request) -> list[dict[str, Any]]:
    """
    GET /api/user-stories - User Story 목록 조회
    Returns all User Stories with their BC assignments.
    """
    query = """
    MATCH (us:UserStory)
    OPTIONAL MATCH (us)-[:IMPLEMENTS]->(bc:BoundedContext)
    RETURN {
        id: us.id,
        role: us.role,
        action: us.action,
        benefit: us.benefit,
        priority: us.priority,
        status: us.status,
        bcId: bc.id,
        bcName: bc.name
    } as user_story
    ORDER BY us.id
    """
    SmartLogger.log(
        "INFO",
        "User stories list requested: returning all user stories with BC assignment.",
        category="api.user_stories.list.request",
        params=http_context(request),
    )
    with get_session() as session:
        result = session.run(query)
        items = [dict(record["user_story"]) for record in result]
        SmartLogger.log(
            "INFO",
            "User stories list returned.",
            category="api.user_stories.list.done",
            params={**http_context(request), "count": len(items)},
        )
        return items


@router.get("/unassigned")
async def get_unassigned_user_stories(request: Request) -> list[dict[str, Any]]:
    """
    GET /api/user-stories/unassigned - BC에 할당되지 않은 User Story 조회
    """
    query = """
    MATCH (us:UserStory)
    WHERE NOT (us)-[:IMPLEMENTS]->(:BoundedContext)
    RETURN {
        id: us.id,
        role: us.role,
        action: us.action,
        benefit: us.benefit,
        priority: us.priority,
        status: us.status
    } as user_story
    ORDER BY us.id
    """
    SmartLogger.log(
        "INFO",
        "Unassigned user stories requested: finding user stories without BC assignment.",
        category="api.user_stories.unassigned.request",
        params=http_context(request),
    )
    with get_session() as session:
        result = session.run(query)
        items = [dict(record["user_story"]) for record in result]
        SmartLogger.log(
            "INFO",
            "Unassigned user stories returned.",
            category="api.user_stories.unassigned.done",
            params={**http_context(request), "count": len(items)},
        )
        return items


