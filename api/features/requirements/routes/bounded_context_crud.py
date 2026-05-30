"""Bounded Context (Epic) CRUD routes (034 — requirement-epic-feature-units).

"Epic" in the Requirements UI is the existing `BoundedContext` node — no new
label. These routes let the UI create and rename a BC, filling the gap where
BCs could previously only be created via the ingestion pipeline.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from starlette.requests import Request

from api.features.ingestion.event_storming.neo4j_client import get_neo4j_client
from api.features.requirements.requirements_contracts import (
    BoundedContextCreateRequest,
    BoundedContextCreateResponse,
    BoundedContextDTO,
    BoundedContextUpdateRequest,
    BoundedContextUpdateResponse,
)
from api.platform.observability.request_logging import http_context
from api.platform.observability.smart_logger import SmartLogger

router = APIRouter()


def _to_dto(bc: dict) -> BoundedContextDTO:
    return BoundedContextDTO(
        id=bc["id"],
        key=bc.get("key"),
        name=bc["name"],
        displayName=bc.get("displayName"),
        description=bc.get("description"),
    )


@router.post("/bounded-context", response_model=BoundedContextCreateResponse, status_code=201)
async def create_bounded_context(
    req: BoundedContextCreateRequest, request: Request
) -> BoundedContextCreateResponse:
    """Create an Epic (BoundedContext). MERGEs on the name-derived key."""
    name = (req.name or "").strip()
    if not name:
        raise HTTPException(status_code=422, detail="name must not be empty")

    bc = get_neo4j_client().create_bounded_context(name=name, description=req.description)

    SmartLogger.log(
        "INFO",
        "Bounded context (epic) created.",
        category="requirements.epic.create",
        params={**http_context(request), "bounded_context_id": bc["id"]},
    )
    return BoundedContextCreateResponse(boundedContext=_to_dto(bc))


@router.patch("/bounded-context", response_model=BoundedContextUpdateResponse)
async def update_bounded_context(
    req: BoundedContextUpdateRequest, request: Request
) -> BoundedContextUpdateResponse:
    """Rename / re-describe an Epic (BoundedContext). Relationships preserved."""
    name = req.name.strip() if req.name is not None else None
    if req.name is not None and not name:
        raise HTTPException(status_code=422, detail="name must not be empty")

    bc = get_neo4j_client().update_bounded_context(
        req.boundedContextId, name=name, description=req.description
    )
    if not bc:
        raise HTTPException(
            status_code=404, detail=f"Bounded context {req.boundedContextId} not found"
        )

    SmartLogger.log(
        "INFO",
        "Bounded context (epic) updated.",
        category="requirements.epic.update",
        params={**http_context(request), "bounded_context_id": req.boundedContextId},
    )
    return BoundedContextUpdateResponse(boundedContext=_to_dto(bc))
