"""Feature CRUD routes (026 — requirements-tab)."""

from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, HTTPException
from starlette.requests import Request

from api.features.ingestion.event_storming.neo4j_client import get_neo4j_client
from api.features.requirements.impact_hook import create_report, run_impact_analysis
from api.features.requirements.requirements_contracts import (
    FeatureCreateRequest,
    FeatureCreateResponse,
    FeatureDeleteRequest,
    FeatureDeleteResponse,
    FeatureNodeDTO,
    FeatureUpdateRequest,
    FeatureUpdateResponse,
)
from api.platform.neo4j import get_session
from api.platform.observability.request_logging import http_context
from api.platform.observability.smart_logger import SmartLogger

router = APIRouter()


@router.post("/feature", response_model=FeatureCreateResponse, status_code=201)
async def create_feature(req: FeatureCreateRequest, request: Request) -> FeatureCreateResponse:
    """Create a new Feature under a Bounded Context (source='manual')."""
    with get_session() as session:
        bc = session.run(
            "MATCH (bc:BoundedContext {id: $id}) RETURN bc.key AS key",
            id=req.boundedContextId,
        ).single()
    if not bc:
        raise HTTPException(status_code=404, detail=f"Bounded context {req.boundedContextId} not found")

    feature = get_neo4j_client().upsert_feature(
        bc_id=req.boundedContextId,
        bc_key=bc["key"],
        name=req.name,
        description=req.description,
        source="manual",
    )
    if not feature:
        raise HTTPException(status_code=404, detail="Feature creation failed")

    SmartLogger.log(
        "INFO",
        "Feature created.",
        category="requirements.feature.create",
        params={**http_context(request), "feature_id": feature["id"]},
    )
    return FeatureCreateResponse(
        feature=FeatureNodeDTO(
            id=feature["id"],
            name=feature["name"],
            description=feature.get("description"),
            source=feature.get("source") or "manual",
        )
    )


@router.patch("/feature", response_model=FeatureUpdateResponse)
async def update_feature(req: FeatureUpdateRequest, request: Request) -> FeatureUpdateResponse:
    """Rename / re-describe a Feature (034). Child user stories stay attached."""
    name = req.name.strip() if req.name is not None else None
    if req.name is not None and not name:
        raise HTTPException(status_code=422, detail="name must not be empty")

    feature = get_neo4j_client().update_feature(
        req.featureId, name=name, description=req.description
    )
    if not feature:
        raise HTTPException(status_code=404, detail=f"Feature {req.featureId} not found")

    SmartLogger.log(
        "INFO",
        "Feature updated.",
        category="requirements.feature.update",
        params={**http_context(request), "feature_id": req.featureId},
    )
    return FeatureUpdateResponse(
        feature=FeatureNodeDTO(
            id=feature["id"],
            name=feature["name"],
            description=feature.get("description"),
            source=feature.get("source") or "manual",
        )
    )


@router.delete("/feature", response_model=FeatureDeleteResponse)
async def delete_feature(
    req: FeatureDeleteRequest, request: Request, background: BackgroundTasks
) -> FeatureDeleteResponse:
    """Delete a Feature. Child user stories are unassigned or deleted."""
    client = get_neo4j_client()
    deleted, affected = client.delete_feature(req.featureId, disposition=req.userStoryDisposition)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Feature {req.featureId} not found")

    report_id = create_report("delete")
    background.add_task(
        run_impact_analysis,
        report_id,
        trigger="delete",
        user_story_id=affected[0] if affected else None,
    )

    SmartLogger.log(
        "INFO",
        "Feature deleted.",
        category="requirements.feature.delete",
        params={
            **http_context(request),
            "feature_id": req.featureId,
            "disposition": req.userStoryDisposition,
            "affected": len(affected),
        },
    )
    return FeatureDeleteResponse(
        deleted=True, affectedUserStoryIds=affected, impactReportId=report_id
    )
