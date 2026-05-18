"""User Story authoring routes (026 — requirements-tab).

propose → confirm honours Constitution IV (human-in-the-loop): natural-language
input is decomposed by the LLM into proposals that mutate nothing; only the
explicit confirm call persists. Manual typed input skips propose.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, BackgroundTasks, HTTPException
from starlette.requests import Request

from api.features.ingestion.event_storming.neo4j_client import get_neo4j_client
from api.features.requirements.feature_grouping_llm import decompose_requirement
from api.features.requirements.impact_hook import create_report, run_impact_analysis
from api.features.requirements.requirements_contracts import (
    UserStoryConfirmRequest,
    UserStoryConfirmResponse,
    UserStoryDeleteRequest,
    UserStoryDeleteResponse,
    UserStoryMoveRequest,
    UserStoryMoveResponse,
    UserStoryProposeRequest,
    UserStoryProposeResponse,
)
from api.features.requirements.tree_service import user_story_node_dto
from api.platform.neo4j import get_session
from api.platform.observability.request_logging import http_context
from api.platform.observability.smart_logger import SmartLogger

router = APIRouter()


@router.post("/user-story/propose", response_model=UserStoryProposeResponse)
async def propose_user_story(
    req: UserStoryProposeRequest, request: Request
) -> UserStoryProposeResponse:
    """Decompose natural-language text into proposed user stories. No mutation."""
    proposals, warnings = decompose_requirement(req.text, req.targetBoundedContextId)
    SmartLogger.log(
        "INFO",
        "User story proposal generated.",
        category="requirements.user_story.propose",
        params={**http_context(request), "proposals": len(proposals), "warnings": len(warnings)},
    )
    return UserStoryProposeResponse(proposals=proposals, warnings=warnings)


@router.post("/user-story/confirm", response_model=UserStoryConfirmResponse, status_code=201)
async def confirm_user_story(
    req: UserStoryConfirmRequest, request: Request, background: BackgroundTasks
) -> UserStoryConfirmResponse:
    """Persist a user story (from a proposal or manual input)."""
    client = get_neo4j_client()
    us_id = str(uuid.uuid4())
    client.create_user_story(
        id=us_id,
        role=req.role,
        action=req.action,
        benefit=req.benefit or "",
        priority=req.priority or "medium",
        status="draft",
    )

    if req.boundedContextId:
        client.link_user_story_to_bc(us_id, req.boundedContextId)

    feature_id = req.featureId
    # Create a brand-new feature if the planner accepted a proposed name.
    if not feature_id and req.newFeatureName and req.boundedContextId:
        with get_session() as session:
            bc = session.run(
                "MATCH (bc:BoundedContext {id: $id}) RETURN bc.key AS key",
                id=req.boundedContextId,
            ).single()
        if bc:
            feature = client.upsert_feature(
                bc_id=req.boundedContextId,
                bc_key=bc["key"],
                name=req.newFeatureName,
                source="manual",
            )
            feature_id = feature["id"] if feature else None

    if feature_id:
        client.link_user_story_to_feature(us_id, feature_id, source="manual")

    report_id = create_report("add")
    background.add_task(run_impact_analysis, report_id, trigger="add", user_story_id=us_id)

    dto = user_story_node_dto(us_id)
    if dto is None:
        raise HTTPException(status_code=500, detail="User story creation failed")

    SmartLogger.log(
        "INFO",
        "User story confirmed.",
        category="requirements.user_story.confirm",
        params={**http_context(request), "user_story_id": us_id, "feature_id": feature_id},
    )
    return UserStoryConfirmResponse(userStory=dto, impactReportId=report_id)


@router.patch("/user-story/move", response_model=UserStoryMoveResponse)
async def move_user_story(
    req: UserStoryMoveRequest, request: Request, background: BackgroundTasks
) -> UserStoryMoveResponse:
    """Re-assign a user story to a different Feature (drag-n-drop)."""
    client = get_neo4j_client()
    with get_session() as session:
        info = session.run(
            """
            MATCH (f:Feature {id: $fid})
            OPTIONAL MATCH (us:UserStory {id: $usid})-[:IMPLEMENTS]->(curBc:BoundedContext)
            RETURN f.boundedContextId AS targetBcId, curBc.id AS currentBcId,
                   us.id AS usExists
            """,
            fid=req.targetFeatureId,
            usid=req.userStoryId,
        ).single()
    if not info or not info["targetBcId"]:
        raise HTTPException(status_code=404, detail="User story or target feature not found")
    if not info["usExists"]:
        raise HTTPException(status_code=404, detail=f"User story {req.userStoryId} not found")

    target_bc = info["targetBcId"]
    current_bc = info["currentBcId"]
    bc_changed = target_bc != current_bc

    if bc_changed:
        # Re-point the IMPLEMENTS(BC) edge to the target feature's BC.
        with get_session() as session:
            session.run(
                """
                MATCH (us:UserStory {id: $usid})
                OPTIONAL MATCH (us)-[old:IMPLEMENTS]->(:BoundedContext)
                DELETE old
                """,
                usid=req.userStoryId,
            )
        client.link_user_story_to_bc(req.userStoryId, target_bc)

    client.link_user_story_to_feature(req.userStoryId, req.targetFeatureId, source="manual")

    report_id = None
    if bc_changed:
        report_id = create_report("move")
        background.add_task(
            run_impact_analysis, report_id, trigger="move", user_story_id=req.userStoryId
        )

    dto = user_story_node_dto(req.userStoryId)
    if dto is None:
        raise HTTPException(status_code=404, detail=f"User story {req.userStoryId} not found")

    SmartLogger.log(
        "INFO",
        "User story moved.",
        category="requirements.user_story.move",
        params={
            **http_context(request),
            "user_story_id": req.userStoryId,
            "target_feature_id": req.targetFeatureId,
            "bc_changed": bc_changed,
        },
    )
    return UserStoryMoveResponse(
        userStory=dto, boundedContextChanged=bc_changed, impactReportId=report_id
    )


@router.delete("/user-story", response_model=UserStoryDeleteResponse)
async def delete_user_story(
    req: UserStoryDeleteRequest, request: Request, background: BackgroundTasks
) -> UserStoryDeleteResponse:
    """Delete a user story."""
    with get_session() as session:
        exists = session.run(
            "MATCH (us:UserStory {id: $id}) RETURN us.id AS id", id=req.userStoryId
        ).single()
        if not exists:
            raise HTTPException(status_code=404, detail=f"User story {req.userStoryId} not found")

    report_id = create_report("delete")
    # Analyze impact BEFORE deleting (the traversal needs the node to exist).
    run_impact_analysis(report_id, trigger="delete", user_story_id=req.userStoryId)

    with get_session() as session:
        session.run("MATCH (us:UserStory {id: $id}) DETACH DELETE us", id=req.userStoryId)

    SmartLogger.log(
        "INFO",
        "User story deleted.",
        category="requirements.user_story.delete",
        params={**http_context(request), "user_story_id": req.userStoryId},
    )
    return UserStoryDeleteResponse(deleted=True, impactReportId=report_id)
