from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from starlette.requests import Request

from api.features.change_management.change_api_contracts import ApplyChangesRequest, ApplyChangesResponse
from api.platform.neo4j import get_session
from api.platform.observability.request_logging import http_context, summarize_for_log
from api.platform.observability.smart_logger import SmartLogger

router = APIRouter()


@router.post("/apply")
async def apply_changes(payload: ApplyChangesRequest, request: Request) -> ApplyChangesResponse:
    """
    Apply the approved change plan to Neo4j.
    """
    applied_changes: list[dict[str, Any]] = []
    errors: list[str] = []
    SmartLogger.log(
        "INFO",
        "Apply changes requested: capturing full router inputs for reproducibility.",
        category="change.apply.inputs",
        params={**http_context(request), "inputs": summarize_for_log(payload.model_dump(by_alias=True))},
    )

    with get_session() as session:
        # Step 1: Update the user story
        try:
            us_query = """
            MATCH (us:UserStory {id: $user_story_id})
            SET us.role = $role,
                us.action = $action,
                us.benefit = $benefit,
                us.updatedAt = datetime()
            RETURN us.id as id
            """
            session.run(
                us_query,
                user_story_id=payload.userStoryId,
                role=payload.editedUserStory.get("role"),
                action=payload.editedUserStory.get("action"),
                benefit=payload.editedUserStory.get("benefit"),
            )
            applied_changes.append(
                {"action": "update", "targetType": "UserStory", "targetId": payload.userStoryId, "success": True}
            )
            SmartLogger.log(
                "INFO",
                "User story updated: new role/action/benefit written to Neo4j.",
                category="change.apply.user_story.updated",
                params={
                    **http_context(request),
                    "userStoryId": payload.userStoryId,
                    "editedUserStory": summarize_for_log(payload.editedUserStory),
                },
            )
        except Exception as e:
            errors.append(f"Failed to update user story: {str(e)}")
            SmartLogger.log(
                "ERROR",
                "Failed to update user story: Neo4j update raised an exception.",
                category="change.apply.user_story.error",
                params={**http_context(request), "userStoryId": payload.userStoryId, "error": str(e)},
            )

        # Step 2: Apply each change in the plan
        for idx, change in enumerate(payload.changePlan):
            try:
                SmartLogger.log(
                    "INFO",
                    "Applying change item from approved plan.",
                    category="change.apply.item.start",
                    params={
                        **http_context(request),
                        "userStoryId": payload.userStoryId,
                        "index": idx + 1,
                        "total": len(payload.changePlan),
                        "change": summarize_for_log(change),
                    },
                )
                if change.get("action") == "rename":
                    rename_query = """
                    MATCH (n {id: $node_id})
                    SET n.name = $new_name, n.updatedAt = datetime()
                    RETURN n.id as id
                    """
                    session.run(rename_query, node_id=change.get("targetId"), new_name=change.get("to"))
                    applied_changes.append({**change, "success": True})
                    SmartLogger.log(
                        "INFO",
                        "Applied change item: node renamed successfully.",
                        category="change.apply.item.renamed",
                        params={**http_context(request), "change": summarize_for_log(change)},
                    )

                elif change.get("action") == "update":
                    update_query = """
                    MATCH (n {id: $node_id})
                    SET n.description = $description, n.updatedAt = datetime()
                    RETURN n.id as id
                    """
                    session.run(
                        update_query,
                        node_id=change.get("targetId"),
                        description=change.get("description", ""),
                    )
                    applied_changes.append({**change, "success": True})
                    SmartLogger.log(
                        "INFO",
                        "Applied change item: node updated successfully.",
                        category="change.apply.item.updated",
                        params={**http_context(request), "change": summarize_for_log(change)},
                    )

                elif change.get("action") == "create":
                    target_type = change.get("targetType")
                    target_id = change.get("targetId")
                    target_name = change.get("targetName")
                    target_bc_id = change.get("targetBcId")

                    if target_type == "Policy":
                        create_query = """
                        MERGE (pol:Policy {id: $pol_id})
                        SET pol.name = $name,
                            pol.description = $description,
                            pol.createdAt = datetime()
                        WITH pol
                        OPTIONAL MATCH (bc:BoundedContext {id: $bc_id})
                        WHERE bc IS NOT NULL
                        MERGE (bc)-[:HAS_POLICY]->(pol)
                        RETURN pol.id as id
                        """
                        session.run(
                            create_query,
                            pol_id=target_id,
                            name=target_name,
                            description=change.get("description", ""),
                            bc_id=target_bc_id,
                        )
                    elif target_type == "Command":
                        create_query = """
                        MERGE (cmd:Command {id: $cmd_id})
                        SET cmd.name = $name,
                            cmd.description = $description,
                            cmd.createdAt = datetime()
                        RETURN cmd.id as id
                        """
                        session.run(
                            create_query,
                            cmd_id=target_id,
                            name=target_name,
                            description=change.get("description", ""),
                        )
                    elif target_type == "Event":
                        create_query = """
                        MERGE (evt:Event {id: $evt_id})
                        SET evt.name = $name,
                            evt.description = $description,
                            evt.version = 1,
                            evt.createdAt = datetime()
                        RETURN evt.id as id
                        """
                        session.run(
                            create_query,
                            evt_id=target_id,
                            name=target_name,
                            description=change.get("description", ""),
                        )
                    else:
                        SmartLogger.log(
                            "WARNING",
                            "Create change item used an unsupported targetType: no node was created.",
                            category="change.apply.item.create.unsupported",
                            params={
                                **http_context(request),
                                "targetType": target_type,
                                "change": summarize_for_log(change),
                            },
                        )

                    applied_changes.append({**change, "success": True})
                    SmartLogger.log(
                        "INFO",
                        "Applied change item: node create attempted.",
                        category="change.apply.item.created",
                        params={**http_context(request), "change": summarize_for_log(change)},
                    )

                elif change.get("action") == "connect":
                    connection_type = change.get("connectionType", "TRIGGERS")
                    source_id = change.get("sourceId")
                    target_id = change.get("targetId")

                    if connection_type == "TRIGGERS":
                        connect_query = """
                        MATCH (evt:Event {id: $source_id})
                        MATCH (pol:Policy {id: $target_id})
                        MERGE (evt)-[:TRIGGERS {priority: 1, isEnabled: true, createdAt: datetime()}]->(pol)
                        RETURN evt.id as id
                        """
                        session.run(connect_query, source_id=source_id, target_id=target_id)
                    elif connection_type == "INVOKES":
                        connect_query = """
                        MATCH (pol:Policy {id: $source_id})
                        MATCH (cmd:Command {id: $target_id})
                        MERGE (pol)-[:INVOKES {isAsync: true, createdAt: datetime()}]->(cmd)
                        RETURN pol.id as id
                        """
                        session.run(connect_query, source_id=source_id, target_id=target_id)
                    elif connection_type == "IMPLEMENTS":
                        connect_query = """
                        MATCH (us:UserStory {id: $source_id})
                        MATCH (n {id: $target_id})
                        MERGE (us)-[:IMPLEMENTS {createdAt: datetime()}]->(n)
                        RETURN us.id as id
                        """
                        session.run(connect_query, source_id=source_id, target_id=target_id)
                    else:
                        SmartLogger.log(
                            "WARNING",
                            "Connect change item used an unsupported connectionType: no relationship was created.",
                            category="change.apply.item.connect.unsupported",
                            params={
                                **http_context(request),
                                "connectionType": connection_type,
                                "change": summarize_for_log(change),
                            },
                        )

                    applied_changes.append({**change, "success": True})
                    SmartLogger.log(
                        "INFO",
                        "Applied change item: relationship connect attempted.",
                        category="change.apply.item.connected",
                        params={**http_context(request), "change": summarize_for_log(change)},
                    )

                elif change.get("action") == "delete":
                    delete_query = """
                    MATCH (n {id: $node_id})
                    SET n.deleted = true, n.deletedAt = datetime()
                    RETURN n.id as id
                    """
                    session.run(delete_query, node_id=change.get("targetId"))
                    applied_changes.append({**change, "success": True})
                    SmartLogger.log(
                        "INFO",
                        "Applied change item: node soft-deleted successfully.",
                        category="change.apply.item.deleted",
                        params={**http_context(request), "change": summarize_for_log(change)},
                    )
                else:
                    SmartLogger.log(
                        "WARNING",
                        "Apply skipped: change item has unsupported 'action'.",
                        category="change.apply.item.unsupported",
                        params={**http_context(request), "change": summarize_for_log(change)},
                    )

            except Exception as e:
                errors.append(f"Failed to apply {change.get('action')} on {change.get('targetId')}: {str(e)}")
                applied_changes.append({**change, "success": False, "error": str(e)})
                SmartLogger.log(
                    "ERROR",
                    "Failed to apply change item",
                    category="change.apply",
                    params={
                        **http_context(request),
                        "userStoryId": payload.userStoryId,
                        "action": change.get("action"),
                        "targetId": change.get("targetId"),
                        "error": str(e),
                    },
                )

    SmartLogger.log(
        "INFO",
        "Apply changes completed",
        category="change.apply",
        params={
            **http_context(request),
            "userStoryId": payload.userStoryId,
            "appliedChanges": len(applied_changes),
            "errors": len(errors),
        },
    )
    return ApplyChangesResponse(success=len(errors) == 0, appliedChanges=applied_changes, errors=errors)


