from __future__ import annotations

from typing import Any, Dict

from api.platform.neo4j import get_session


async def apply_change(change: Dict[str, Any]) -> bool:
    action = change.get("action")
    target_id = change.get("targetId")
    if not action or not target_id:
        return False

    try:
        with get_session() as session:
            if action == "rename":
                session.run(
                    """
                    MATCH (n {id: $target_id})
                    SET n.name = $new_name, n.updatedAt = datetime()
                    RETURN n.id as id
                    """,
                    target_id=target_id,
                    new_name=change.get("targetName", ""),
                )
                return True

            if action == "update":
                # Generic update: always allow description updates.
                # UI-specific update: allow template updates (and attachedTo metadata when provided).
                template = change.get("template")
                attached_to_id = change.get("attachedToId")
                attached_to_type = change.get("attachedToType")
                attached_to_name = change.get("attachedToName")

                if template is not None or attached_to_id is not None or attached_to_type is not None or attached_to_name is not None:
                    session.run(
                        """
                        MATCH (n {id: $target_id})
                        SET n.description = coalesce($description, n.description),
                            n.template = coalesce($template, n.template),
                            n.attachedToId = coalesce($attached_to_id, n.attachedToId),
                            n.attachedToType = coalesce($attached_to_type, n.attachedToType),
                            n.attachedToName = coalesce($attached_to_name, n.attachedToName),
                            n.updatedAt = datetime()
                        RETURN n.id as id
                        """,
                        target_id=target_id,
                        description=change.get("description"),
                        template=template,
                        attached_to_id=attached_to_id,
                        attached_to_type=attached_to_type,
                        attached_to_name=attached_to_name,
                    )
                else:
                    session.run(
                        """
                        MATCH (n {id: $target_id})
                        SET n.description = $description, n.updatedAt = datetime()
                        RETURN n.id as id
                        """,
                        target_id=target_id,
                        description=change.get("description", ""),
                    )
                return True

            if action == "delete":
                session.run(
                    """
                    MATCH (n {id: $target_id})
                    SET n.deleted = true, n.deletedAt = datetime()
                    RETURN n.id as id
                    """,
                    target_id=target_id,
                )
                return True

            if action == "create":
                target_type = change.get("targetType", "Command")
                target_name = change.get("targetName", "NewNode")
                bc_id = change.get("bcId") or change.get("targetBcId")

                if target_type == "Command":
                    aggregate_id = change.get("aggregateId")
                    if aggregate_id:
                        session.run(
                            """
                            MERGE (n:Command {id: $target_id})
                            SET n.name = $name, n.description = $description, n.createdAt = datetime()
                            WITH n
                            MATCH (agg:Aggregate {id: $agg_id})
                            MERGE (agg)-[:HAS_COMMAND]->(n)
                            RETURN n.id as id
                            """,
                            target_id=target_id,
                            name=target_name,
                            description=change.get("description", ""),
                            agg_id=aggregate_id,
                        )
                    else:
                        session.run(
                            """
                            MERGE (n:Command {id: $target_id})
                            SET n.name = $name, n.description = $description, n.createdAt = datetime()
                            RETURN n.id as id
                            """,
                            target_id=target_id,
                            name=target_name,
                            description=change.get("description", ""),
                        )

                elif target_type == "Event":
                    command_id = change.get("commandId")
                    if command_id:
                        session.run(
                            """
                            MERGE (n:Event {id: $target_id})
                            SET n.name = $name, n.description = $description, n.version = 1, n.createdAt = datetime()
                            WITH n
                            MATCH (cmd:Command {id: $cmd_id})
                            MERGE (cmd)-[:EMITS]->(n)
                            RETURN n.id as id
                            """,
                            target_id=target_id,
                            name=target_name,
                            description=change.get("description", ""),
                            cmd_id=command_id,
                        )
                    else:
                        session.run(
                            """
                            MERGE (n:Event {id: $target_id})
                            SET n.name = $name, n.description = $description, n.version = 1, n.createdAt = datetime()
                            RETURN n.id as id
                            """,
                            target_id=target_id,
                            name=target_name,
                            description=change.get("description", ""),
                        )

                elif target_type == "Policy":
                    if bc_id:
                        session.run(
                            """
                            MERGE (n:Policy {id: $target_id})
                            SET n.name = $name, n.description = $description, n.createdAt = datetime()
                            WITH n
                            MATCH (bc:BoundedContext {id: $bc_id})
                            MERGE (bc)-[:HAS_POLICY]->(n)
                            RETURN n.id as id
                            """,
                            target_id=target_id,
                            name=target_name,
                            description=change.get("description", ""),
                            bc_id=bc_id,
                        )
                    else:
                        session.run(
                            """
                            MERGE (n:Policy {id: $target_id})
                            SET n.name = $name, n.description = $description, n.createdAt = datetime()
                            RETURN n.id as id
                            """,
                            target_id=target_id,
                            name=target_name,
                            description=change.get("description", ""),
                        )
                else:
                    # UI wireframe node
                    if target_type == "UI":
                        attached_to_id = change.get("attachedToId")
                        attached_to_type = change.get("attachedToType", "Command")
                        attached_to_name = change.get("attachedToName", "")
                        template = change.get("template", "")

                        if bc_id:
                            session.run(
                                """
                                MERGE (n:UI {id: $target_id})
                                SET n.name = $name,
                                    n.description = $description,
                                    n.template = $template,
                                    n.attachedToId = $attached_to_id,
                                    n.attachedToType = $attached_to_type,
                                    n.attachedToName = $attached_to_name,
                                    n.createdAt = datetime()
                                WITH n
                                MATCH (bc:BoundedContext {id: $bc_id})
                                MERGE (bc)-[:HAS_UI]->(n)
                                RETURN n.id as id
                                """,
                                target_id=target_id,
                                name=target_name,
                                description=change.get("description", ""),
                                template=template,
                                attached_to_id=attached_to_id,
                                attached_to_type=attached_to_type,
                                attached_to_name=attached_to_name,
                                bc_id=bc_id,
                            )

                            # Create ATTACHED_TO relationship when possible.
                            if attached_to_id:
                                attach_query = f"""
                                MATCH (ui:UI {{id: $ui_id}})
                                MATCH (target:{attached_to_type} {{id: $attached_to_id}})
                                MERGE (ui)-[:ATTACHED_TO]->(target)
                                """
                                session.run(attach_query, ui_id=target_id, attached_to_id=attached_to_id)
                        else:
                            session.run(
                                """
                                MERGE (n:UI {id: $target_id})
                                SET n.name = $name,
                                    n.description = $description,
                                    n.template = $template,
                                    n.attachedToId = $attached_to_id,
                                    n.attachedToType = $attached_to_type,
                                    n.attachedToName = $attached_to_name,
                                    n.createdAt = datetime()
                                RETURN n.id as id
                                """,
                                target_id=target_id,
                                name=target_name,
                                description=change.get("description", ""),
                                template=template,
                                attached_to_id=attached_to_id,
                                attached_to_type=attached_to_type,
                                attached_to_name=attached_to_name,
                            )
                        change["bcId"] = bc_id
                        return True

                    return False

                change["bcId"] = bc_id
                return True

            if action == "connect":
                source_id = change.get("sourceId")
                connection_type = change.get("connectionType", "TRIGGERS")
                if not source_id:
                    return False

                if connection_type == "TRIGGERS":
                    session.run(
                        """
                        MATCH (evt:Event {id: $source_id})
                        MATCH (pol:Policy {id: $target_id})
                        MERGE (evt)-[:TRIGGERS]->(pol)
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
                        MERGE (pol)-[:INVOKES]->(cmd)
                        RETURN pol.id as id
                        """,
                        source_id=source_id,
                        target_id=target_id,
                    )
                elif connection_type == "EMITS":
                    session.run(
                        """
                        MATCH (cmd:Command {id: $source_id})
                        MATCH (evt:Event {id: $target_id})
                        MERGE (cmd)-[:EMITS]->(evt)
                        RETURN cmd.id as id
                        """,
                        source_id=source_id,
                        target_id=target_id,
                    )
                else:
                    return False

                return True

    except Exception:
        return False

    return False


