"""
User Story authoring/management API (feature router)

- Add a user story and generate an initial plan (human review)
- Apply an approved plan to Neo4j
- List unassigned user stories (legacy endpoint)
"""

from __future__ import annotations

import time
import uuid
from typing import Any, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from starlette.requests import Request

from api.platform.neo4j import get_session
from api.platform.observability.request_logging import http_context, summarize_for_log, sha256_text
from api.platform.observability.smart_logger import SmartLogger

router = APIRouter(prefix="/api/user-story", tags=["user-story"])


class AddUserStoryRequest(BaseModel):
    role: str
    action: str
    benefit: Optional[str] = None
    targetBcId: Optional[str] = None
    autoGenerate: bool = True


class ApplyUserStoryRequest(BaseModel):
    userStory: dict
    targetBcId: Optional[str] = None
    changePlan: List[dict]


class AddUserStoryResponse(BaseModel):
    scope: str
    scopeReasoning: str
    keywords: List[str] = Field(default_factory=list)
    relatedObjects: List[dict] = Field(default_factory=list)
    changes: List[dict]
    summary: str


@router.post("/add")
async def add_user_story(request: AddUserStoryRequest, http_request: Request) -> dict[str, Any]:
    from api.features.user_stories.planning_agent.user_story_graph import run_user_story_planning

    t0 = time.perf_counter()
    SmartLogger.log(
        "INFO",
        "User story add requested: generating plan via agent.",
        category="api.user_story.add.request",
        params={
            **http_context(http_request),
            "inputs": {
                "role": request.role,
                "action": request.action,
                "benefit": request.benefit,
                "targetBcId": request.targetBcId,
                "autoGenerate": request.autoGenerate,
                "story_sha256": sha256_text(f"{request.role}|{request.action}|{request.benefit or ''}"),
            },
        },
    )

    try:
        result = run_user_story_planning(
            role=request.role,
            action=request.action,
            benefit=request.benefit or "",
            target_bc_id=request.targetBcId,
            auto_generate=request.autoGenerate,
        )
        SmartLogger.log(
            "INFO",
            "User story add completed: plan generated.",
            category="api.user_story.add.done",
            params={
                **http_context(http_request),
                "duration_ms": int((time.perf_counter() - t0) * 1000),
                "summary": {
                    "scope": result.get("scope"),
                    "keywords_count": len(result.get("keywords") or []),
                    "relatedObjects_count": len(result.get("relatedObjects") or []),
                    "changes_count": len(result.get("changes") or []),
                },
                "result": summarize_for_log(result),
            },
        )
        return result
    except Exception as e:
        SmartLogger.log(
            "ERROR",
            "User story add failed: plan generation error.",
            category="api.user_story.add.error",
            params={
                **http_context(http_request),
                "duration_ms": int((time.perf_counter() - t0) * 1000),
                "error": {"type": type(e).__name__, "message": str(e)},
            },
        )
        raise HTTPException(status_code=500, detail=f"Failed to generate plan: {str(e)}")


@router.post("/apply")
async def apply_user_story(request: ApplyUserStoryRequest, http_request: Request) -> dict[str, Any]:
    applied_changes: list[dict[str, Any]] = []
    errors: list[str] = []
    user_story_id = f"US-{str(uuid.uuid4())[:8].upper()}"
    t0 = time.perf_counter()

    SmartLogger.log(
        "INFO",
        "User story apply requested: creating user story + applying change plan to Neo4j.",
        category="api.user_story.apply.request",
        params={
            **http_context(http_request),
            "inputs": {
                "targetBcId": request.targetBcId,
                "userStory": summarize_for_log(request.userStory),
                "changePlan": summarize_for_log(request.changePlan),
                "changePlan_count": len(request.changePlan or []),
            },
        },
    )

    with get_session() as session:
        # Create the user story node
        try:
            t_us0 = time.perf_counter()
            session.run(
                """
                CREATE (us:UserStory {
                    id: $us_id,
                    role: $role,
                    action: $action,
                    benefit: $benefit,
                    priority: 'medium',
                    status: 'new',
                    createdAt: datetime()
                })
                RETURN us.id as id
                """,
                us_id=user_story_id,
                role=request.userStory.get("role", ""),
                action=request.userStory.get("action", ""),
                benefit=request.userStory.get("benefit", ""),
            )
            applied_changes.append(
                {
                    "action": "create",
                    "targetType": "UserStory",
                    "targetId": user_story_id,
                    "targetName": f"{request.userStory.get('role')}: {request.userStory.get('action', '')[:30]}...",
                    "success": True,
                    "duration_ms": int((time.perf_counter() - t_us0) * 1000),
                }
            )
            SmartLogger.log(
                "INFO",
                "User story apply: UserStory node created.",
                category="api.user_story.apply.create_user_story",
                params={
                    **http_context(http_request),
                    "userStoryId": user_story_id,
                    "duration_ms": int((time.perf_counter() - t_us0) * 1000),
                },
            )
        except Exception as e:
            SmartLogger.log(
                "ERROR",
                "User story apply failed: could not create UserStory node.",
                category="api.user_story.apply.create_user_story.error",
                params={
                    **http_context(http_request),
                    "userStoryId": user_story_id,
                    "error": {"type": type(e).__name__, "message": str(e)},
                },
            )
            raise HTTPException(status_code=500, detail=f"Failed to create user story: {str(e)}")

        # Connect to BC if specified
        target_bc_id = request.targetBcId
        if target_bc_id:
            try:
                t_bc0 = time.perf_counter()
                session.run(
                    """
                    MATCH (us:UserStory {id: $us_id})
                    MATCH (bc:BoundedContext {id: $bc_id})
                    MERGE (us)-[:IMPLEMENTS]->(bc)
                    RETURN bc.id as id
                    """,
                    us_id=user_story_id,
                    bc_id=target_bc_id,
                )
                applied_changes.append(
                    {
                        "action": "connect",
                        "targetType": "BoundedContext",
                        "targetId": target_bc_id,
                        "connectionType": "IMPLEMENTS",
                        "sourceId": user_story_id,
                        "success": True,
                        "duration_ms": int((time.perf_counter() - t_bc0) * 1000),
                    }
                )
                SmartLogger.log(
                    "INFO",
                    "User story apply: connected UserStory to target BC.",
                    category="api.user_story.apply.connect_bc",
                    params={
                        **http_context(http_request),
                        "userStoryId": user_story_id,
                        "bcId": target_bc_id,
                        "duration_ms": int((time.perf_counter() - t_bc0) * 1000),
                    },
                )
            except Exception as e:
                errors.append(f"Failed to connect to BC: {str(e)}")
                SmartLogger.log(
                    "WARNING",
                    "User story apply: failed to connect UserStory to target BC.",
                    category="api.user_story.apply.connect_bc.error",
                    params={
                        **http_context(http_request),
                        "userStoryId": user_story_id,
                        "bcId": target_bc_id,
                        "error": {"type": type(e).__name__, "message": str(e)},
                    },
                )

        change_timings: list[dict[str, Any]] = []

        # Apply each change in the plan
        for change in request.changePlan:
            try:
                t_change0 = time.perf_counter()
                action = change.get("action")
                target_type = change.get("targetType")
                target_id = change.get("targetId")
                target_name = change.get("targetName")
                target_bc_id = change.get("targetBcId")
                connection_type = change.get("connectionType")
                source_id = change.get("sourceId")

                if action == "create":
                    if target_type == "Aggregate":
                        session.run(
                            """
                            MERGE (agg:Aggregate {id: $agg_id})
                            SET agg.name = $name,
                                agg.rootEntity = $name,
                                agg.description = $description,
                                agg.createdAt = datetime()
                            WITH agg
                            OPTIONAL MATCH (bc:BoundedContext {id: $bc_id})
                            WHERE bc IS NOT NULL
                            MERGE (bc)-[:HAS_AGGREGATE]->(agg)
                            WITH agg
                            MATCH (us:UserStory {id: $us_id})
                            MERGE (us)-[:IMPLEMENTS]->(agg)
                            RETURN agg.id as id
                            """,
                            agg_id=target_id,
                            name=target_name,
                            description=change.get("description", ""),
                            bc_id=target_bc_id,
                            us_id=user_story_id,
                        )
                    elif target_type == "Command":
                        session.run(
                            """
                            MERGE (cmd:Command {id: $cmd_id})
                            SET cmd.name = $name,
                                cmd.actor = $actor,
                                cmd.description = $description,
                                cmd.createdAt = datetime()
                            WITH cmd
                            OPTIONAL MATCH (agg:Aggregate {id: $agg_id})
                            WHERE agg IS NOT NULL
                            MERGE (agg)-[:HAS_COMMAND]->(cmd)
                            RETURN cmd.id as id
                            """,
                            cmd_id=target_id,
                            name=target_name,
                            actor=change.get("actor", "user"),
                            description=change.get("description", ""),
                            agg_id=source_id or change.get("aggregateId"),
                        )
                    elif target_type == "Event":
                        session.run(
                            """
                            MERGE (evt:Event {id: $evt_id})
                            SET evt.name = $name,
                                evt.version = 1,
                                evt.description = $description,
                                evt.createdAt = datetime()
                            WITH evt
                            OPTIONAL MATCH (cmd:Command {id: $cmd_id})
                            WHERE cmd IS NOT NULL
                            MERGE (cmd)-[:EMITS]->(evt)
                            RETURN evt.id as id
                            """,
                            evt_id=target_id,
                            name=target_name,
                            description=change.get("description", ""),
                            cmd_id=source_id or change.get("commandId"),
                        )
                    elif target_type == "Policy":
                        session.run(
                            """
                            MERGE (pol:Policy {id: $pol_id})
                            SET pol.name = $name,
                                pol.description = $description,
                                pol.createdAt = datetime()
                            WITH pol
                            OPTIONAL MATCH (bc:BoundedContext {id: $bc_id})
                            WHERE bc IS NOT NULL
                            MERGE (bc)-[:HAS_POLICY]->(pol)
                            RETURN pol.id as id
                            """,
                            pol_id=target_id,
                            name=target_name,
                            description=change.get("description", ""),
                            bc_id=target_bc_id,
                        )
                    elif target_type == "BoundedContext":
                        session.run(
                            """
                            MERGE (bc:BoundedContext {id: $bc_id})
                            SET bc.name = $name,
                                bc.description = $description,
                                bc.createdAt = datetime()
                            WITH bc
                            MATCH (us:UserStory {id: $us_id})
                            MERGE (us)-[:IMPLEMENTS]->(bc)
                            RETURN bc.id as id
                            """,
                            bc_id=target_id,
                            name=target_name,
                            description=change.get("description", ""),
                            us_id=user_story_id,
                        )
                        target_bc_id = target_id

                    ms = int((time.perf_counter() - t_change0) * 1000)
                    applied_changes.append({**change, "success": True, "duration_ms": ms})
                    change_timings.append({"action": action, "targetType": target_type, "targetId": target_id, "duration_ms": ms, "success": True})

                elif action == "connect":
                    if connection_type == "TRIGGERS":
                        session.run(
                            """
                            MATCH (evt:Event {id: $source_id})
                            MATCH (pol:Policy {id: $target_id})
                            MERGE (evt)-[:TRIGGERS {priority: 1, isEnabled: true}]->(pol)
                            RETURN evt.id as id
                            """,
                            source_id=source_id,
                            target_id=target_id,
                        )
                    elif connection_type == "INVOKES":
                        session.run(
                            """
                            MATCH (pol:Policy {id: $source_id})
                            MATCH (cmd:Command {id: $target_id})
                            MERGE (pol)-[:INVOKES {isAsync: true}]->(cmd)
                            RETURN pol.id as id
                            """,
                            source_id=source_id,
                            target_id=target_id,
                        )
                    elif connection_type == "IMPLEMENTS":
                        session.run(
                            """
                            MATCH (us:UserStory {id: $source_id})
                            MATCH (n {id: $target_id})
                            MERGE (us)-[:IMPLEMENTS]->(n)
                            RETURN us.id as id
                            """,
                            source_id=source_id,
                            target_id=target_id,
                        )

                    ms = int((time.perf_counter() - t_change0) * 1000)
                    applied_changes.append({**change, "success": True, "duration_ms": ms})
                    change_timings.append(
                        {
                            "action": action,
                            "connectionType": connection_type,
                            "targetType": target_type,
                            "targetId": target_id,
                            "sourceId": source_id,
                            "duration_ms": ms,
                            "success": True,
                        }
                    )

                elif action == "update":
                    session.run(
                        """
                        MATCH (n {id: $node_id})
                        SET n.name = $name, n.updatedAt = datetime()
                        RETURN n.id as id
                        """,
                        node_id=target_id,
                        name=target_name,
                    )
                    ms = int((time.perf_counter() - t_change0) * 1000)
                    applied_changes.append({**change, "success": True, "duration_ms": ms})
                    change_timings.append({"action": action, "targetType": target_type, "targetId": target_id, "duration_ms": ms, "success": True})

            except Exception as e:
                errors.append(f"Failed to apply {action} on {change.get('targetId')}: {str(e)}")
                ms = int((time.perf_counter() - t_change0) * 1000) if "t_change0" in locals() else None
                applied_changes.append({**change, "success": False, "error": str(e), "duration_ms": ms})
                change_timings.append(
                    {"action": change.get("action"), "targetType": change.get("targetType"), "targetId": change.get("targetId"), "duration_ms": ms, "success": False, "error": str(e)}
                )
                SmartLogger.log(
                    "WARNING",
                    "User story apply: failed to apply a change.",
                    category="api.user_story.apply.change.error",
                    params={
                        **http_context(http_request),
                        "userStoryId": user_story_id,
                        "change": summarize_for_log(change),
                        "duration_ms": ms,
                        "error": {"type": type(e).__name__, "message": str(e)},
                    },
                )

    total_ms = int((time.perf_counter() - t0) * 1000)
    slowest = sorted(change_timings, key=lambda x: (x.get("duration_ms") or -1), reverse=True)[:10]
    SmartLogger.log(
        "INFO",
        "User story apply completed.",
        category="api.user_story.apply.done",
        params={
            **http_context(http_request),
            "duration_ms": total_ms,
            "userStoryId": user_story_id,
            "summary": {"success": len(errors) == 0, "appliedChanges": len(applied_changes), "errors": len(errors), "slowest_changes_top10": slowest},
        },
    )

    return {"success": len(errors) == 0, "userStoryId": user_story_id, "appliedChanges": applied_changes, "errors": errors}


@router.get("/unassigned")
async def get_unassigned_user_stories(http_request: Request) -> List[dict[str, Any]]:
    query = """
    MATCH (us:UserStory)
    WHERE NOT (us)-[:IMPLEMENTS]->(:BoundedContext)
    RETURN us {.id, .role, .action, .benefit, .priority, .status} as userStory
    ORDER BY us.createdAt DESC
    """
    with get_session() as session:
        t0 = time.perf_counter()
        result = session.run(query)
        items = [dict(record["userStory"]) for record in result]
        SmartLogger.log(
            "INFO",
            "User story unassigned list returned.",
            category="api.user_story.unassigned.done",
            params={**http_context(http_request), "duration_ms": int((time.perf_counter() - t0) * 1000), "count": len(items)},
        )
        return items


