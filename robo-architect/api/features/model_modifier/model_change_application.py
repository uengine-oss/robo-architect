from __future__ import annotations

from typing import Any, Dict

from api.platform.neo4j import get_session
from api.platform.observability.smart_logger import SmartLogger
from api.platform.ui_wireframe_template import normalize_ui_template


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

                if template is not None:
                    ui_name = str(change.get("targetName") or "UI").strip() or "UI"
                    raw_template = str(template)
                    normalized, report = normalize_ui_template(raw_template, ui_name=ui_name, theme_hint=ui_name)
                    SmartLogger.log(
                        "INFO",
                        "UI template normalized (legacy apply_change)",
                        category="api.model_change.ui_template.normalize",
                        params={
                            "action": "update",
                            "targetId": target_id,
                            "ui_name": ui_name,
                            "len_before": len(raw_template),
                            "len_after": len(normalized),
                            "normalize": report.as_dict(),
                            "template_before": raw_template,
                            "template_after": normalized,
                        },
                    )
                    template = normalized

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


MAX_NAME_LEN = 200
MAX_DESCRIPTION_LEN = 4000
MAX_TEMPLATE_LEN = 50000


_LABELS_BY_TYPE: dict[str, str] = {
    "Command": "Command",
    "Event": "Event",
    "Policy": "Policy",
    "Aggregate": "Aggregate",
    "ReadModel": "ReadModel",
    "UI": "UI",
    "BoundedContext": "BoundedContext",
}


_ALLOWED_UPDATE_FIELDS_BY_LABEL: dict[str, set[str]] = {
    # Default nodes: description + a small set of safe, whitelisted fields (Inspector MVP)
    "Command": {"description", "actor"},
    "Event": {"description", "version"},
    "Policy": {"description"},
    "Aggregate": {"description", "rootEntity"},
    "ReadModel": {"description", "provisioningType"},
    "BoundedContext": {"description"},
    # UI: wireframe + attachment metadata
    "UI": {"description", "template", "attachedToId", "attachedToType", "attachedToName"},
}


def _get_node_info_tx(tx: Any, node_id: str) -> dict[str, Any] | None:
    query = """
    MATCH (n {id: $id})
    RETURN labels(n) as labels,
           n.id as id,
           n.name as name,
           n.description as description,
           n.template as template,
           n.attachedToId as attachedToId,
           n.attachedToType as attachedToType,
           n.attachedToName as attachedToName
    """
    rec = tx.run(query, id=node_id).single()
    if not rec:
        return None
    return {
        "labels": rec.get("labels") or [],
        "id": rec.get("id"),
        "name": rec.get("name"),
        "description": rec.get("description"),
        "template": rec.get("template"),
        "attachedToId": rec.get("attachedToId"),
        "attachedToType": rec.get("attachedToType"),
        "attachedToName": rec.get("attachedToName"),
    }


def _primary_label(labels: list[str]) -> str | None:
    # Prefer known domain labels
    for k in _ALLOWED_UPDATE_FIELDS_BY_LABEL.keys():
        if k in labels:
            return k
    return labels[0] if labels else None


def _validate_common(change: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if not change.get("action"):
        errors.append("Missing action")
    if not change.get("targetId"):
        errors.append("Missing targetId")
    if change.get("action") == "rename":
        new_name = change.get("targetName")
        if not isinstance(new_name, str) or not new_name.strip():
            errors.append("rename requires targetName (new name)")
        elif len(new_name) > MAX_NAME_LEN:
            errors.append(f"targetName too long (>{MAX_NAME_LEN})")
    if change.get("action") in ("update", "create"):
        updates = change.get("updates")
        if updates is None:
            change["updates"] = {}
        if not isinstance(change.get("updates"), dict):
            errors.append("updates must be an object")
    return errors


def _validate_update_tx(tx: Any, change: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    node_id = str(change.get("targetId"))
    info = _get_node_info_tx(tx, node_id)
    if not info:
        return [f"target not found: {node_id}"]

    label = _primary_label(info.get("labels") or [])
    if not label:
        return [f"target has no labels: {node_id}"]

    updates = change.get("updates") or {}
    if not updates:
        return ["update requires non-empty updates"]

    # E2: deterministic normalization for UI templates (before field validation)
    # This prevents rejections on length/doc-root/style-scope violations by auto-correcting them.
    if label == "UI" and isinstance(updates.get("template"), str):
        ui_name = str(info.get("name") or info.get("id") or "UI")
        raw = str(updates.get("template") or "")
        normalized, report = normalize_ui_template(raw, ui_name=ui_name, theme_hint=ui_name)
        if normalized != raw or report.fallback_used:
            SmartLogger.log(
                "INFO",
                "UI template normalized (validation)",
                category="api.model_change.ui_template.normalize",
                params={
                    "phase": "validate_update",
                    "targetId": node_id,
                    "ui_name": ui_name,
                    "len_before": len(raw),
                    "len_after": len(normalized),
                    "normalize": report.as_dict(),
                    "template_before": raw,
                    "template_after": normalized,
                },
            )
        updates["template"] = normalized
        change["updates"] = updates

    allowed = _ALLOWED_UPDATE_FIELDS_BY_LABEL.get(label, {"description"})
    for field, value in updates.items():
        if field not in allowed:
            errors.append(f"field not allowed for {label}: {field}")
            continue

        if field == "description" and value is not None:
            if not isinstance(value, str):
                errors.append("description must be a string")
            elif len(value) > MAX_DESCRIPTION_LEN:
                errors.append(f"description too long (>{MAX_DESCRIPTION_LEN})")

        if field == "template" and value is not None:
            if not isinstance(value, str):
                errors.append("template must be a string")
            elif len(value) > MAX_TEMPLATE_LEN:
                errors.append(f"template too long (>{MAX_TEMPLATE_LEN})")

        if field in ("actor", "rootEntity") and value is not None:
            if not isinstance(value, str):
                errors.append(f"{field} must be a string")
            elif len(value) > MAX_NAME_LEN:
                errors.append(f"{field} too long (>{MAX_NAME_LEN})")

        if field == "version" and value is not None:
            if isinstance(value, (int, float)):
                # ok
                pass
            elif isinstance(value, str):
                if len(value) > 50:
                    errors.append("version too long (>50)")
            else:
                errors.append("version must be a string or number")

        if field == "provisioningType" and value is not None:
            if not isinstance(value, str):
                errors.append("provisioningType must be a string")
            else:
                allowed_types = {"CQRS", "API", "GraphQL", "SharedDB"}
                if value not in allowed_types:
                    errors.append(f"provisioningType must be one of {sorted(allowed_types)}")

        if field in ("attachedToId", "attachedToType", "attachedToName") and value is not None:
            if not isinstance(value, str):
                errors.append(f"{field} must be a string")

    # Relationship integrity: attachedToId must exist when provided (non-empty)
    attached_to_id = updates.get("attachedToId")
    if isinstance(attached_to_id, str) and attached_to_id.strip():
        rec = tx.run("MATCH (n {id: $id}) RETURN n.id as id", id=attached_to_id).single()
        if not rec:
            errors.append(f"attachedToId does not exist: {attached_to_id}")

    return errors


def _apply_update_tx(tx: Any, change: dict[str, Any]) -> None:
    node_id = str(change.get("targetId"))
    updates: dict[str, Any] = change.get("updates") or {}

    # Normalize UI template if present (E2, deterministic)
    if "template" in updates and updates.get("template") is not None:
        info = _get_node_info_tx(tx, node_id) or {}
        ui_name = str(info.get("name") or info.get("id") or "UI")
        raw = str(updates.get("template") or "")
        normalized, report = normalize_ui_template(raw, ui_name=ui_name, theme_hint=ui_name)
        if normalized != raw or report.fallback_used:
            SmartLogger.log(
                "INFO",
                "UI template normalized (apply_update)",
                category="api.model_change.ui_template.normalize",
                params={
                    "phase": "apply_update",
                    "targetId": node_id,
                    "ui_name": ui_name,
                    "len_before": len(raw),
                    "len_after": len(normalized),
                    "normalize": report.as_dict(),
                    "template_before": raw,
                    "template_after": normalized,
                },
            )
        updates["template"] = normalized

    # Build SET clauses for whitelisted property names
    set_clauses: list[str] = ["n.updatedAt = datetime()"]
    params: dict[str, Any] = {"id": node_id}
    for k in [
        "description",
        "actor",
        "version",
        "rootEntity",
        "provisioningType",
        "template",
        "attachedToId",
        "attachedToType",
        "attachedToName",
    ]:
        if k in updates:
            set_clauses.append(f"n.{k} = ${k}")
            params[k] = updates.get(k)

    query = f"""
    MATCH (n {{id: $id}})
    SET {", ".join(set_clauses)}
    RETURN n.id as id
    """
    tx.run(query, **params)

    # Update ATTACHED_TO relationship if UI and attachedToId changed
    if "attachedToId" in updates:
        # Remove existing ATTACHED_TO
        tx.run(
            """
            MATCH (ui:UI {id: $id})
            OPTIONAL MATCH (ui)-[r:ATTACHED_TO]->()
            DELETE r
            """,
            id=node_id,
        )
        attached_to_id = updates.get("attachedToId")
        if isinstance(attached_to_id, str) and attached_to_id.strip():
            tx.run(
                """
                MATCH (ui:UI {id: $id})
                MATCH (target {id: $target_id})
                MERGE (ui)-[:ATTACHED_TO]->(target)
                """,
                id=node_id,
                target_id=attached_to_id,
            )


def _apply_rename_tx(tx: Any, change: dict[str, Any]) -> None:
    node_id = str(change.get("targetId"))
    new_name = str(change.get("targetName") or "")
    tx.run(
        """
        MATCH (n {id: $id})
        SET n.name = $name, n.updatedAt = datetime()
        RETURN n.id as id
        """,
        id=node_id,
        name=new_name,
    )


def _apply_delete_tx(tx: Any, change: dict[str, Any]) -> None:
    node_id = str(change.get("targetId"))
    tx.run(
        """
        MATCH (n {id: $id})
        SET n.deleted = true, n.deletedAt = datetime()
        RETURN n.id as id
        """,
        id=node_id,
    )


def _apply_connect_tx(tx: Any, change: dict[str, Any]) -> None:
    source_id = change.get("sourceId")
    target_id = change.get("targetId")
    connection_type = change.get("connectionType", "TRIGGERS")
    if not source_id or not target_id:
        raise ValueError("connect requires sourceId and targetId")

    if connection_type == "TRIGGERS":
        tx.run(
            """
            MATCH (evt:Event {id: $source_id})
            MATCH (pol:Policy {id: $target_id})
            MERGE (evt)-[:TRIGGERS]->(pol)
            """,
            source_id=source_id,
            target_id=target_id,
        )
    elif connection_type == "INVOKES":
        tx.run(
            """
            MATCH (pol:Policy {id: $source_id})
            MATCH (cmd:Command {id: $target_id})
            MERGE (pol)-[:INVOKES]->(cmd)
            """,
            source_id=source_id,
            target_id=target_id,
        )
    elif connection_type == "EMITS":
        tx.run(
            """
            MATCH (cmd:Command {id: $source_id})
            MATCH (evt:Event {id: $target_id})
            MERGE (cmd)-[:EMITS]->(evt)
            """,
            source_id=source_id,
            target_id=target_id,
        )
    else:
        raise ValueError(f"unsupported connectionType: {connection_type}")


def _apply_create_tx(tx: Any, change: dict[str, Any]) -> None:
    target_id = str(change.get("targetId"))
    target_type = str(change.get("targetType") or "Command")
    target_name = str(change.get("targetName") or "NewNode")
    bc_id = change.get("bcId") or change.get("targetBcId")
    updates: dict[str, Any] = change.get("updates") or {}

    # For create, we still accept top-level description/template for backward compatibility
    description = updates.get("description", change.get("description", "")) or ""

    if len(target_name) > MAX_NAME_LEN:
        raise ValueError(f"targetName too long (>{MAX_NAME_LEN})")
    if isinstance(description, str) and len(description) > MAX_DESCRIPTION_LEN:
        raise ValueError(f"description too long (>{MAX_DESCRIPTION_LEN})")

    if target_type == "Command":
        tx.run(
            """
            MERGE (n:Command {id: $id})
            SET n.name = $name, n.description = $description, n.createdAt = datetime()
            """,
            id=target_id,
            name=target_name,
            description=description,
        )
    elif target_type == "Event":
        tx.run(
            """
            MERGE (n:Event {id: $id})
            SET n.name = $name, n.description = $description, n.version = 1, n.createdAt = datetime()
            """,
            id=target_id,
            name=target_name,
            description=description,
        )
    elif target_type == "Policy":
        tx.run(
            """
            MERGE (n:Policy {id: $id})
            SET n.name = $name, n.description = $description, n.createdAt = datetime()
            """,
            id=target_id,
            name=target_name,
            description=description,
        )
    elif target_type == "UI":
        raw_template = updates.get("template", change.get("template", "")) or ""
        template, report = normalize_ui_template(str(raw_template), ui_name=target_name, theme_hint=target_name)
        if len(template) > MAX_TEMPLATE_LEN:
            raise ValueError(f"template too long (>{MAX_TEMPLATE_LEN})")
        if template != str(raw_template) or report.fallback_used:
            SmartLogger.log(
                "INFO",
                "UI template normalized (apply_create)",
                category="api.model_change.ui_template.normalize",
                params={
                    "phase": "apply_create",
                    "targetId": target_id,
                    "ui_name": target_name,
                    "len_before": len(str(raw_template)),
                    "len_after": len(template),
                    "normalize": report.as_dict(),
                    "template_before": str(raw_template),
                    "template_after": template,
                },
            )

        attached_to_id = updates.get("attachedToId", change.get("attachedToId"))
        attached_to_type = updates.get("attachedToType", change.get("attachedToType", "Command"))
        attached_to_name = updates.get("attachedToName", change.get("attachedToName", ""))

        tx.run(
            """
            MERGE (n:UI {id: $id})
            SET n.name = $name,
                n.description = $description,
                n.template = $template,
                n.attachedToId = $attached_to_id,
                n.attachedToType = $attached_to_type,
                n.attachedToName = $attached_to_name,
                n.createdAt = datetime()
            """,
            id=target_id,
            name=target_name,
            description=description,
            template=template,
            attached_to_id=attached_to_id,
            attached_to_type=attached_to_type,
            attached_to_name=attached_to_name,
        )

        if attached_to_id:
            # ensure single relationship
            tx.run(
                """
                MATCH (ui:UI {id: $id})
                OPTIONAL MATCH (ui)-[r:ATTACHED_TO]->()
                DELETE r
                """,
                id=target_id,
            )
            tx.run(
                """
                MATCH (ui:UI {id: $id})
                MATCH (target {id: $target_id})
                MERGE (ui)-[:ATTACHED_TO]->(target)
                """,
                id=target_id,
                target_id=attached_to_id,
            )
    else:
        raise ValueError(f"unsupported targetType for create: {target_type}")

    # Attach to BC when provided
    if bc_id and target_type in ("Policy", "UI"):
        rel = "HAS_POLICY" if target_type == "Policy" else "HAS_UI"
        tx.run(
            f"""
            MATCH (bc:BoundedContext {{id: $bc_id}})
            MATCH (n:{_LABELS_BY_TYPE[target_type]} {{id: $id}})
            MERGE (bc)-[:{rel}]->(n)
            """,
            bc_id=bc_id,
            id=target_id,
        )


def apply_confirmed_changes_atomic(approved_changes: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[str]]:
    """
    Validate and apply the approved change set in a single Neo4j transaction.
    All-or-nothing: any error => rollback and return errors.
    """
    if not approved_changes:
        return [], []

    errors: list[str] = []

    SmartLogger.log(
        "INFO",
        "Change-apply started: validating and applying changes atomically.",
        category="api.model_change.atomic.start",
        params={"approvedChanges": approved_changes},
    )

    with get_session() as session:
        tx = session.begin_transaction()
        try:
            # Validation pass (within tx for read-your-writes consistency)
            for change in approved_changes:
                errors.extend(_validate_common(change))
                if errors:
                    break

                action = change.get("action")
                if action == "update":
                    errors.extend(_validate_update_tx(tx, change))
                elif action == "connect":
                    # Minimal validation: required fields + nodes exist
                    if not change.get("sourceId") or not change.get("targetId"):
                        errors.append("connect requires sourceId and targetId")
                    else:
                        src = tx.run("MATCH (n {id: $id}) RETURN n.id as id", id=change.get("sourceId")).single()
                        tgt = tx.run("MATCH (n {id: $id}) RETURN n.id as id", id=change.get("targetId")).single()
                        if not src:
                            errors.append(f"source not found: {change.get('sourceId')}")
                        if not tgt:
                            errors.append(f"target not found: {change.get('targetId')}")
                elif action == "delete":
                    info = _get_node_info_tx(tx, str(change.get("targetId")))
                    if not info:
                        errors.append(f"target not found: {change.get('targetId')}")
                elif action == "rename":
                    info = _get_node_info_tx(tx, str(change.get("targetId")))
                    if not info:
                        errors.append(f"target not found: {change.get('targetId')}")
                elif action == "create":
                    # Basic: must have targetType and targetName
                    if not change.get("targetType"):
                        errors.append("create requires targetType")
                    if not change.get("targetName"):
                        errors.append("create requires targetName")
                else:
                    errors.append(f"unsupported action: {action}")

                if errors:
                    break

            if errors:
                SmartLogger.log(
                    "WARNING",
                    "Change-apply validation failed: no changes applied (rollback).",
                    category="api.model_change.atomic.validation_failed",
                    params={"errors": errors, "approvedChanges": approved_changes},
                )
                tx.rollback()
                return [], errors

            # Apply pass
            for change in approved_changes:
                action = change.get("action")
                if action == "rename":
                    _apply_rename_tx(tx, change)
                elif action == "update":
                    _apply_update_tx(tx, change)
                elif action == "delete":
                    _apply_delete_tx(tx, change)
                elif action == "connect":
                    _apply_connect_tx(tx, change)
                elif action == "create":
                    _apply_create_tx(tx, change)

            tx.commit()

        except Exception as e:
            try:
                tx.rollback()
            except Exception:
                pass
            SmartLogger.log(
                "ERROR",
                "Change-apply crashed: transaction rolled back.",
                category="api.model_change.atomic.exception",
                params={"error": str(e), "approvedChanges": approved_changes},
            )
            return [], [str(e)]

    # Flatten updates for frontend sync compatibility
    applied: list[dict[str, Any]] = []
    for change in approved_changes:
        c = dict(change)
        updates = c.get("updates") if isinstance(c.get("updates"), dict) else {}
        for k, v in (updates or {}).items():
            c[k] = v
        applied.append(c)

    SmartLogger.log(
        "INFO",
        "Change-apply completed successfully.",
        category="api.model_change.atomic.done",
        params={"appliedChanges": applied},
    )
    return applied, []

