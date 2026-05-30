"""User Story direct-edit + edit-history routes (033 — requirement-edit-history).

PATCH /api/requirements/user-story/{id}   — user edits role/action/benefit/priority/status
GET  /api/requirements/user-story/{id}/history — fetch edit history (newest first)
"""

from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, HTTPException
from starlette.requests import Request

from api.features.requirements.clarification_contracts import UserStorySnapshot
from api.features.requirements.clarification_agent.user_story_edit_service import (
    EditConflictError,
    UserStoryEdit,
    apply_user_story_edit,
    fetch_user_story_snapshot,
)
from api.features.requirements.requirements_contracts import (
    EditHistoryItemDTO,
    EditHistoryResponse,
    UserStoryPatchRequest,
    UserStoryPatchResponse,
)
from api.features.requirements.tree_service import user_story_node_dto
from api.platform.neo4j import get_session
from api.platform.observability.smart_logger import SmartLogger

router = APIRouter()


@router.patch("/user-story/{user_story_id}", response_model=UserStoryPatchResponse)
async def patch_user_story(
    user_story_id: str,
    req: UserStoryPatchRequest,
    request: Request,
) -> UserStoryPatchResponse:
    """Directly edit a user story's text fields. Records an EditHistory entry."""
    current = fetch_user_story_snapshot(user_story_id)
    if current is None:
        raise HTTPException(status_code=404, detail=f"User story {user_story_id} not found")

    after = UserStorySnapshot(
        role=req.role if req.role is not None else current.snapshot.role,
        action=req.action if req.action is not None else current.snapshot.action,
        benefit=req.benefit if req.benefit is not None else current.snapshot.benefit,
        priority=req.priority if req.priority is not None else current.snapshot.priority,
        status=req.status if req.status is not None else current.snapshot.status,
        acceptanceCriteria=current.snapshot.acceptanceCriteria,
    )

    try:
        result = apply_user_story_edit(
            UserStoryEdit(
                requirement_id=user_story_id,
                after=after,
                base_updated_at=req.baseUpdatedAt,
                actor=getattr(request.state, "actor", None),
            )
        )
    except EditConflictError as e:
        raise HTTPException(
            status_code=409,
            detail={"code": "EDIT_CONFLICT", "latestUpdatedAt": e.latest_updated_at},
        )

    dto = user_story_node_dto(user_story_id)
    if dto is None:
        raise HTTPException(status_code=404, detail=f"User story {user_story_id} not found after edit")

    SmartLogger.log(
        "INFO",
        "User story edited directly by user.",
        category="requirements.user_story.direct_edit",
        params={
            "user_story_id": user_story_id,
            "changed": result.changed,
            "actor_email": getattr(getattr(request.state, "actor", None), "email", "unknown"),
        },
    )
    return UserStoryPatchResponse(userStory=dto, changed=result.changed, updatedAt=result.updated_at)


@router.get("/user-story/{user_story_id}/history", response_model=EditHistoryResponse)
async def get_user_story_history(user_story_id: str) -> EditHistoryResponse:
    """Return the edit history for a user story, newest first (max 50)."""
    query = """
    MATCH (us:UserStory {id: $id})-[:HAS_HISTORY]->(h:EditHistory)
    RETURN h.id AS id,
           h.timestamp AS timestamp,
           h.userName AS userName,
           h.userEmail AS userEmail,
           h.changes AS changes
    ORDER BY h.timestamp DESC
    LIMIT 50
    """
    with get_session() as session:
        rows = session.run(query, id=user_story_id).data()

    items = [_row_to_dto(r) for r in rows]
    return EditHistoryResponse(items=items)


def _row_to_dto(row: dict[str, Any]) -> EditHistoryItemDTO:
    ts = row.get("timestamp")
    if ts is None:
        ts_str = ""
    elif hasattr(ts, "iso_format"):
        ts_str = ts.iso_format()
    elif hasattr(ts, "isoformat"):
        ts_str = ts.isoformat()
    else:
        ts_str = str(ts)

    changes_raw = row.get("changes") or "{}"
    if isinstance(changes_raw, str):
        try:
            changes = json.loads(changes_raw)
        except (ValueError, TypeError):
            changes = {}
    else:
        changes = changes_raw

    return EditHistoryItemDTO(
        id=row.get("id") or "",
        timestamp=ts_str,
        userName=row.get("userName") or "unknown",
        userEmail=row.get("userEmail") or "unknown",
        changes=changes,
    )
