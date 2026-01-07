"""
Change Planning: Apply Plan

Business capability: apply an approved plan to Neo4j.
"""

from __future__ import annotations

from typing import Any, Dict

from .change_planning_contracts import ChangePlanningPhase, ChangePlanningState
from .change_planning_runtime import get_neo4j_driver, neo4j_session


def apply_changes_node(state: ChangePlanningState) -> Dict[str, Any]:
    """
    Apply the approved changes to Neo4j.
    """
    driver = get_neo4j_driver()
    applied_changes = []

    try:
        with neo4j_session(driver) as session:
            # Update user story
            session.run(
                """
                MATCH (us:UserStory {id: $us_id})
                SET us.role = $role,
                    us.action = $action,
                    us.benefit = $benefit,
                    us.updatedAt = datetime()
            """,
                us_id=state.user_story_id,
                role=state.edited_user_story.get("role"),
                action=state.edited_user_story.get("action"),
                benefit=state.edited_user_story.get("benefit"),
            )
            applied_changes.append(
                {
                    "action": "update",
                    "targetType": "UserStory",
                    "targetId": state.user_story_id,
                    "success": True,
                }
            )

            # Apply each proposed change
            for change in state.proposed_changes:
                try:
                    if change.action == "connect" and change.connectionType == "TRIGGERS":
                        # Create Event -> TRIGGERS -> Policy connection
                        session.run(
                            """
                            MATCH (evt:Event {id: $source_id})
                            MATCH (pol:Policy {id: $target_id})
                            MERGE (evt)-[:TRIGGERS {priority: 1, isEnabled: true}]->(pol)
                        """,
                            source_id=change.sourceId,
                            target_id=change.targetId,
                        )

                    elif change.action == "connect" and change.connectionType == "INVOKES":
                        # Create Policy -> INVOKES -> Command connection
                        session.run(
                            """
                            MATCH (pol:Policy {id: $source_id})
                            MATCH (cmd:Command {id: $target_id})
                            MERGE (pol)-[:INVOKES {isAsync: true}]->(cmd)
                        """,
                            source_id=change.sourceId,
                            target_id=change.targetId,
                        )

                    elif change.action == "create":
                        # Create new node based on type
                        if change.targetType == "Policy":
                            session.run(
                                """
                                MATCH (bc:BoundedContext {id: $bc_id})
                                MERGE (pol:Policy {id: $pol_id})
                                SET pol.name = $name,
                                    pol.description = $description,
                                    pol.createdAt = datetime()
                                MERGE (bc)-[:HAS_POLICY]->(pol)
                            """,
                                bc_id=change.targetBcId,
                                pol_id=change.targetId,
                                name=change.targetName,
                                description=change.description,
                            )
                        # Add more create cases as needed

                    elif change.action == "update":
                        session.run(
                            """
                            MATCH (n {id: $node_id})
                            SET n.name = $name, n.updatedAt = datetime()
                        """,
                            node_id=change.targetId,
                            name=change.targetName,
                        )

                    applied_changes.append(
                        {
                            "action": change.action,
                            "targetType": change.targetType,
                            "targetId": change.targetId,
                            "success": True,
                        }
                    )

                except Exception as e:
                    applied_changes.append(
                        {
                            "action": change.action,
                            "targetType": change.targetType,
                            "targetId": change.targetId,
                            "success": False,
                            "error": str(e),
                        }
                    )

    finally:
        driver.close()

    return {
        "phase": ChangePlanningPhase.COMPLETE,
        "applied_changes": applied_changes,
        "awaiting_approval": False,
    }


