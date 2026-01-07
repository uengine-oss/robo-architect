from __future__ import annotations

import re
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
    "Property": "Property",
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
    # Property: field schema metadata
    # NOTE: parentType/parentId are accepted as metadata for safer targeting / diff readability,
    # but are NOT applied (we do not allow changing a property's parent via update).
    "Property": {"name", "description", "type", "isKey", "isForeignKey", "isRequired", "parentType", "parentId"},
}


def _get_node_info_tx(tx: Any, node_id: str) -> dict[str, Any] | None:
    query = """
    MATCH (n {id: $id})
    RETURN labels(n) as labels,
           n.id as id,
           n.name as name,
           n.description as description,
           n.type as type,
           n.isKey as isKey,
           n.isForeignKey as isForeignKey,
           n.isRequired as isRequired,
           n.parentType as parentType,
           n.parentId as parentId,
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
        "type": rec.get("type"),
        "isKey": rec.get("isKey"),
        "isForeignKey": rec.get("isForeignKey"),
        "isRequired": rec.get("isRequired"),
        "parentType": rec.get("parentType"),
        "parentId": rec.get("parentId"),
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
        # For Property updates, we can resolve missing/placeholder targetId using (parentType,parentId,targetName).
        target_type = str(change.get("targetType") or "").strip()
        updates = change.get("updates") if isinstance(change.get("updates"), dict) else {}
        has_selector = bool(
            target_type == "Property"
            and str(updates.get("parentType") or "").strip()
            and str(updates.get("parentId") or "").strip()
            and str(change.get("targetName") or "").strip()
        )
        if not has_selector:
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


def _normalize_for_match(s: str | None) -> str:
    raw = (s or "").strip().lower()
    if not raw:
        return ""
    # lower + remove whitespace + remove common separators
    return re.sub(r"[\s_\-./:|\\]+", "", raw)


def _levenshtein_distance(a: str, b: str) -> int:
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)
    # O(|a|*|b|) DP, acceptable for small candidate sets
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, start=1):
        cur = [i]
        for j, cb in enumerate(b, start=1):
            cost = 0 if ca == cb else 1
            cur.append(min(cur[j - 1] + 1, prev[j] + 1, prev[j - 1] + cost))
        prev = cur
    return prev[-1]


def _levenshtein_sim(a: str, b: str) -> float:
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    dist = _levenshtein_distance(a, b)
    denom = max(len(a), len(b))
    return max(0.0, 1.0 - (dist / float(denom)))


def _jaro_winkler(a: str, b: str) -> float:
    # Minimal JW implementation (no external deps)
    if a == b:
        return 1.0
    if not a or not b:
        return 0.0

    a_len = len(a)
    b_len = len(b)
    match_distance = max(a_len, b_len) // 2 - 1

    a_matches = [False] * a_len
    b_matches = [False] * b_len

    matches = 0
    for i in range(a_len):
        start = max(0, i - match_distance)
        end = min(i + match_distance + 1, b_len)
        for j in range(start, end):
            if b_matches[j]:
                continue
            if a[i] != b[j]:
                continue
            a_matches[i] = True
            b_matches[j] = True
            matches += 1
            break

    if matches == 0:
        return 0.0

    # Transpositions
    t = 0
    k = 0
    for i in range(a_len):
        if not a_matches[i]:
            continue
        while not b_matches[k]:
            k += 1
        if a[i] != b[k]:
            t += 1
        k += 1
    transpositions = t / 2.0

    jaro = (
        (matches / a_len + matches / b_len + (matches - transpositions) / matches) / 3.0
    )

    # Winkler boost
    prefix = 0
    for i in range(min(4, a_len, b_len)):
        if a[i] == b[i]:
            prefix += 1
        else:
            break
    p = 0.1
    return jaro + prefix * p * (1.0 - jaro)


def _combined_similarity(a_raw: str | None, b_raw: str | None) -> dict[str, float]:
    a = _normalize_for_match(a_raw)
    b = _normalize_for_match(b_raw)
    jw = _jaro_winkler(a, b)
    lev = _levenshtein_sim(a, b)
    score = 0.7 * jw + 0.3 * lev
    return {"jw": jw, "lev_sim": lev, "score": score}


def _resolve_property_target_id_tx(tx: Any, change: dict[str, Any]) -> tuple[str | None, list[dict[str, Any]], str]:
    """
    Try to resolve Property UUID when change.targetId is missing/invalid.
    Selector: updates.parentType, updates.parentId, and change.targetName (existing property name).
    Returns (resolved_id, candidates_debug, selector_debug).
    """
    updates = change.get("updates") if isinstance(change.get("updates"), dict) else {}
    parent_type = str(updates.get("parentType") or "").strip()
    parent_id = str(updates.get("parentId") or "").strip()
    selector_name = str(change.get("targetName") or "").strip()
    selector_dbg = f"parentType={parent_type} parentId={parent_id} targetName={selector_name}"

    if not parent_type or not parent_id or not selector_name:
        return None, [], selector_dbg

    # Candidate set: only within the parent scope
    recs = tx.run(
        """
        MATCH (p:Property {parentType: $pt, parentId: $pid})
        RETURN p.id as id, p.name as name, p.type as type
        """,
        pt=parent_type,
        pid=parent_id,
    ).data() or []

    if not recs:
        return None, [], selector_dbg

    scored: list[dict[str, Any]] = []
    for r in recs:
        pid = r.get("id")
        pname = r.get("name")
        sim = _combined_similarity(selector_name, pname)
        scored.append(
            {
                "id": pid,
                "name": pname,
                "type": r.get("type"),
                **sim,
            }
        )

    scored.sort(key=lambda x: (-float(x.get("score", 0.0)), str(x.get("name") or "")))

    best = scored[0]
    best_score = float(best.get("score", 0.0))
    second_score = float(scored[1].get("score", 0.0)) if len(scored) > 1 else -1.0

    if best_score < 0.92:
        return None, scored[:10], selector_dbg
    if len(scored) > 1 and (best_score - second_score) < 0.02:
        # Ambiguous
        return "__AMBIGUOUS__", scored[:10], selector_dbg

    return str(best.get("id")), scored[:10], selector_dbg


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

    # Property safety: parentType/parentId are metadata-only; they must match the actual parent if provided.
    if label == "Property":
        # Reject attempts to change parent linkage through update.
        if "parentType" in updates and updates.get("parentType") is not None:
            if not isinstance(updates.get("parentType"), str):
                errors.append("parentType must be a string")
            else:
                provided = str(updates.get("parentType") or "").strip()
                actual = str(info.get("parentType") or "").strip()
                if provided and actual and provided != actual:
                    errors.append(f"Property parentType mismatch: {provided} != {actual}")
        if "parentId" in updates and updates.get("parentId") is not None:
            if not isinstance(updates.get("parentId"), str):
                errors.append("parentId must be a string")
            else:
                provided = str(updates.get("parentId") or "").strip()
                actual = str(info.get("parentId") or "").strip()
                if provided and actual and provided != actual:
                    errors.append(f"Property parentId mismatch: {provided} != {actual}")

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

        if field == "name" and value is not None:
            if not isinstance(value, str):
                errors.append("name must be a string")
            else:
                if not value.strip():
                    errors.append("name must be non-empty")
                elif len(value) > MAX_NAME_LEN:
                    errors.append(f"name too long (>{MAX_NAME_LEN})")

        if field == "description" and value is not None:
            if not isinstance(value, str):
                errors.append("description must be a string")
            elif len(value) > MAX_DESCRIPTION_LEN:
                errors.append(f"description too long (>{MAX_DESCRIPTION_LEN})")

        if field == "type" and value is not None:
            if not isinstance(value, str):
                errors.append("type must be a string")
            elif len(value) > MAX_NAME_LEN:
                errors.append(f"type too long (>{MAX_NAME_LEN})")

        if field in ("isKey", "isForeignKey", "isRequired") and value is not None:
            if not isinstance(value, bool):
                errors.append(f"{field} must be a boolean")

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
        "name",
        "description",
        "actor",
        "version",
        "rootEntity",
        "provisioningType",
        # Property fields
        "type",
        "isKey",
        "isForeignKey",
        "isRequired",
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

    # Enrich response for Property updates (frontend needs parent info to update embedded list)
    info_after = _get_node_info_tx(tx, node_id) or {}
    if "Property" in (info_after.get("labels") or []):
        change["targetType"] = "Property"
        change["parentType"] = info_after.get("parentType")
        change["parentId"] = info_after.get("parentId")
        change["name"] = info_after.get("name")
        change["type"] = info_after.get("type")
        change["description"] = info_after.get("description")
        change["isKey"] = info_after.get("isKey")
        change["isForeignKey"] = info_after.get("isForeignKey")
        change["isRequired"] = info_after.get("isRequired")

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

    # Enrich response for Property rename (frontend needs parent info to update embedded list)
    info_after = _get_node_info_tx(tx, node_id) or {}
    if "Property" in (info_after.get("labels") or []):
        change["targetType"] = "Property"
        change["parentType"] = info_after.get("parentType")
        change["parentId"] = info_after.get("parentId")
        change["name"] = info_after.get("name")
        change["type"] = info_after.get("type")
        change["description"] = info_after.get("description")
        change["isKey"] = info_after.get("isKey")
        change["isForeignKey"] = info_after.get("isForeignKey")
        change["isRequired"] = info_after.get("isRequired")


def _apply_delete_tx(tx: Any, change: dict[str, Any]) -> None:
    node_id = str(change.get("targetId"))
    info = _get_node_info_tx(tx, node_id) or {}
    labels = info.get("labels") or []
    if "Property" in labels:
        # Enrich response so frontend can remove it from parent's embedded list
        change["targetType"] = "Property"
        change["targetName"] = info.get("name") or change.get("targetName")
        change["parentType"] = info.get("parentType")
        change["parentId"] = info.get("parentId")
        # For Property, hard delete so the same (parentType,parentId,name) can be re-created later.
        tx.run(
            """
            MATCH (p:Property {id: $id})
            DETACH DELETE p
            """,
            id=node_id,
        )
        return

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
    elif connection_type == "REFERENCES":
        # Property FK reference: only allow tgt.isKey=true, and enforce src.isForeignKey=true
        rec = tx.run(
            """
            MATCH (tgt:Property {id: $target_id})
            RETURN tgt.isKey as isKey
            """,
            target_id=target_id,
        ).single()
        if not rec or not bool(rec.get("isKey")):
            raise ValueError("REFERENCES target must have isKey=true")

        tx.run(
            """
            MATCH (src:Property {id: $source_id})
            MATCH (tgt:Property {id: $target_id})
            SET src.isForeignKey = true
            MERGE (src)-[:REFERENCES]->(tgt)
            """,
            source_id=source_id,
            target_id=target_id,
        )
        # Enrich response so frontend can mark source property as FK in embedded list
        src_info = _get_node_info_tx(tx, str(source_id)) or {}
        if "Property" in (src_info.get("labels") or []):
            change["sourceParentType"] = src_info.get("parentType")
            change["sourceParentId"] = src_info.get("parentId")
            change["sourcePropertyIsForeignKey"] = True
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
        if target_type == "Property":
            parent_type = str(updates.get("parentType") or "").strip()
            parent_id = str(updates.get("parentId") or "").strip()
            prop_name = str(updates.get("name") or target_name or "").strip()
            prop_type = str(updates.get("type") or "").strip()

            if not parent_type or parent_type not in ("Aggregate", "Command", "Event", "ReadModel"):
                raise ValueError("Property create requires updates.parentType in Aggregate|Command|Event|ReadModel")
            if not parent_id:
                raise ValueError("Property create requires updates.parentId")
            if not prop_name:
                raise ValueError("Property create requires updates.name (or targetName)")
            if not prop_type:
                raise ValueError("Property create requires updates.type")

            prop_description = str(updates.get("description") or "")
            is_key = bool(updates.get("isKey", False))
            is_fk = bool(updates.get("isForeignKey", False))
            is_required = bool(updates.get("isRequired", False))

            rec = tx.run(
                """
                MERGE (p:Property {parentType: $parent_type, parentId: $parent_id, name: $name})
                ON CREATE SET p.id = randomUUID()
                SET p.type = $type,
                    p.description = $description,
                    p.isKey = $is_key,
                    p.isForeignKey = $is_fk,
                    p.isRequired = $is_required,
                    p.parentType = $parent_type,
                    p.parentId = $parent_id
                WITH p
                MATCH (parent {id: $parent_id})
                WHERE $parent_type IN labels(parent)
                MERGE (parent)-[:HAS_PROPERTY]->(p)
                RETURN p.id as id
                """,
                parent_type=parent_type,
                parent_id=parent_id,
                name=prop_name,
                type=prop_type,
                description=prop_description,
                is_key=is_key,
                is_fk=is_fk,
                is_required=is_required,
            ).single()
            if not rec or not rec.get("id"):
                raise ValueError("failed to create Property")

            # Ensure applied response uses the canonical UUID id
            change["targetId"] = str(rec.get("id"))
            change["targetType"] = "Property"
            change["targetName"] = prop_name
            change["updates"] = {
                **updates,
                "id": str(rec.get("id")),
                "name": prop_name,
                "type": prop_type,
                "description": prop_description,
                "isKey": is_key,
                "isForeignKey": is_fk,
                "isRequired": is_required,
                "parentType": parent_type,
                "parentId": parent_id,
            }
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
                # ---------------------------------------------------------------------
                # Fallback targetId resolution (accuracy-first; ambiguous => hard error)
                # ---------------------------------------------------------------------
                if action in ("update", "rename", "delete"):
                    # Try to resolve Property UUID when targetId is missing/placeholder/non-existent
                    target_type = str(change.get("targetType") or "").strip()
                    target_id = str(change.get("targetId") or "").strip()
                    exists = bool(target_id and _get_node_info_tx(tx, target_id))
                    # NOTE: For Property rename we prefer action=update (updates.name). For action=rename,
                    # targetName is the *new* name, so do not try to resolve by name.
                    if target_type == "Property" and action != "rename" and not exists:
                        resolved, candidates, selector_dbg = _resolve_property_target_id_tx(tx, change)
                        if resolved == "__AMBIGUOUS__":
                            msg = (
                                "모호한 Property 대상입니다. 여러 후보가 유사합니다.\n"
                                f"- selector: {selector_dbg}\n"
                                f"- targetId(provided): {target_id or '(empty)'}\n"
                                f"- candidates(top): {candidates}"
                            )
                            SmartLogger.log(
                                "WARNING",
                                "Property target resolve ambiguous; aborting atomic apply.",
                                category="api.model_change.target_resolve.ambiguous",
                                params={
                                    "action": action,
                                    "selector": selector_dbg,
                                    "providedTargetId": target_id,
                                    "candidates": candidates,
                                },
                            )
                            errors.append(msg)
                            break
                        if resolved:
                            SmartLogger.log(
                                "INFO",
                                "Property target resolved via fallback.",
                                category="api.model_change.target_resolve",
                                params={
                                    "action": action,
                                    "selector": selector_dbg,
                                    "providedTargetId": target_id,
                                    "resolvedTargetId": resolved,
                                    "candidates": candidates,
                                },
                            )
                            change["targetId"] = resolved
                        else:
                            # Explicit error (avoid generic "target not found" for troubleshooting)
                            msg = (
                                "Property 대상을 자동 보정할 수 없습니다(유사도 임계값 미달 또는 후보 없음).\n"
                                f"- selector: {selector_dbg}\n"
                                f"- targetId(provided): {target_id or '(empty)'}\n"
                                f"- candidates(top): {candidates}"
                            )
                            SmartLogger.log(
                                "WARNING",
                                "Property target resolve failed (no confident match); aborting atomic apply.",
                                category="api.model_change.target_resolve.none",
                                params={
                                    "action": action,
                                    "selector": selector_dbg,
                                    "providedTargetId": target_id,
                                    "candidates": candidates,
                                },
                            )
                            errors.append(msg)
                            break

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
                    if str(change.get("targetType")) == "Property":
                        updates = change.get("updates") or {}
                        if not (change.get("targetName") or updates.get("name")):
                            errors.append("create Property requires targetName or updates.name")
                    else:
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

