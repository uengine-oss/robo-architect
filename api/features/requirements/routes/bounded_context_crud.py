"""Bounded Context (Epic) CRUD routes (034 — requirement-epic-feature-units).

"Epic" in the Requirements UI is the existing `BoundedContext` node — no new
label. These routes let the UI create and rename a BC, filling the gap where
BCs could previously only be created via the ingestion pipeline.
"""

from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, HTTPException
from starlette.requests import Request

from api.features.ingestion.event_storming.neo4j_client import get_neo4j_client
from api.features.requirements import deletion_archive as da
from api.features.requirements.impact_hook import create_report, run_impact_analysis
from api.features.requirements.requirements_contracts import (
    BoundedContextCreateRequest,
    BoundedContextCreateResponse,
    BoundedContextDeleteRequest,
    BoundedContextDeleteResponse,
    BoundedContextDTO,
    BoundedContextUpdateRequest,
    BoundedContextUpdateResponse,
)
from api.platform.neo4j import get_session
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

    display_name = req.displayName.strip() if req.displayName else None
    bc = get_neo4j_client().create_bounded_context(
        name=name, display_name=display_name or None, description=req.description
    )

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
    display_name = req.displayName.strip() if req.displayName is not None else None
    if req.displayName is not None and not display_name:
        raise HTTPException(status_code=422, detail="displayName must not be empty")

    bc = get_neo4j_client().update_bounded_context(
        req.boundedContextId,
        name=name,
        display_name=display_name,
        description=req.description,
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


@router.delete("/bounded-context", response_model=BoundedContextDeleteResponse)
async def delete_bounded_context(
    req: BoundedContextDeleteRequest, request: Request, background: BackgroundTasks
) -> BoundedContextDeleteResponse:
    """Delete an Epic (BoundedContext) with its Features and User Stories.

    Recoverable: the whole subtree (+ optionally the design it exclusively
    implements) is snapshotted into a :DeletionRecord before the live nodes
    are removed (034 — option B). Restore later via /deletion-records.
    """
    with get_session() as session:
        exists = session.run(
            "MATCH (bc:BoundedContext {id: $id}) RETURN bc.name AS name",
            id=req.boundedContextId,
        ).single()
        if not exists:
            raise HTTPException(
                status_code=404, detail=f"Bounded context {req.boundedContextId} not found"
            )

        ids = da.subtree_ids_for_epic(session, req.boundedContextId)
        us_ids = [
            r["id"]
            for r in session.run(
                """
                MATCH (bc:BoundedContext {id: $id})-[:HAS_FEATURE]->(:Feature)
                      -[:HAS_USER_STORY]->(us:UserStory)
                RETURN DISTINCT us.id AS id
                """,
                id=req.boundedContextId,
            )
        ]
        feat_ids = [
            r["id"]
            for r in session.run(
                "MATCH (bc:BoundedContext {id: $id})-[:HAS_FEATURE]->(f:Feature) RETURN f.id AS id",
                id=req.boundedContextId,
            )
        ]

        if req.removeDesign:
            # US 배타 설계 + BC 직속 설계(Aggregate→Command→Event, 예: DDD 마법사
            # 산출물 — US 없이 BC에 직접 붙음)를 함께 제거해 orphan 방지.
            ids = list(dict.fromkeys(
                ids
                + da.exclusive_design_ids(session, us_ids)
                + da.bc_design_ids(session, req.boundedContextId)
            ))

        batch_id = da.capture(
            session,
            ids,
            scope="epic",
            root_label="BoundedContext",
            root_name=exists["name"],
            actor=http_context(request).get("user"),
        )
        da.detach_delete(session, ids)

    report_id = create_report("delete")
    background.add_task(run_impact_analysis, report_id, trigger="delete")

    SmartLogger.log(
        "INFO",
        "Bounded context (epic) deleted.",
        category="requirements.epic.delete",
        params={
            **http_context(request),
            "bounded_context_id": req.boundedContextId,
            "remove_design": req.removeDesign,
            "restore_batch": batch_id,
        },
    )
    return BoundedContextDeleteResponse(
        deleted=True,
        affectedFeatureIds=feat_ids,
        affectedUserStoryIds=us_ids,
        impactReportId=report_id,
        restoreBatchId=batch_id,
    )
