"""Canonical tacticalDiff contract validation for Proposal Plan drafts."""

from __future__ import annotations

import re
from typing import Any


_CAMEL_CASE = re.compile(r"^[a-z][A-Za-z0-9]*$")
_VALID_LABELS = {"Aggregate", "Command", "Event", "ReadModel", "Policy", "UI", "Invariant"}
_LEGACY_REF_KEYS = {
    "aggregate": "aggregateId",
    "boundedContext": "boundedContextId",
    "emittedBy": "commandId",
    "trigger": "triggerEventId",
    "invokes": "invokeCommandId",
    "traces": "userStoryRefs",
}


def validate_tactical_diff_contract(tactical_diff: list[dict] | None) -> list[dict]:
    """Return contract violations for generated tacticalDiff.

    This intentionally validates the persisted preview contract, not just display
    fields. Broken drafts must not reach Neo4j because preview projection and
    apply logic both depend on these refs and structured properties.
    """
    if not isinstance(tactical_diff, list) or not tactical_diff:
        return [{"path": "tacticalDiff", "code": "empty", "message": "tacticalDiff must be a non-empty list"}]

    violations: list[dict] = []
    by_id = {
        str(item.get("nodeId")): item
        for item in tactical_diff
        if isinstance(item, dict) and item.get("nodeId")
    }
    event_props_by_command: dict[str, set[str]] = {}
    aggregate_props_by_id: dict[str, set[str]] = {}

    for index, item in enumerate(tactical_diff):
        if not isinstance(item, dict):
            violations.append(_violation(index, "item", "not_object", "tacticalDiff item must be an object"))
            continue
        label = item.get("nodeLabel")
        if label == "Aggregate":
            aggregate_props_by_id[str(item.get("nodeId") or "")] = _property_names(item.get("properties"))
        if label == "Event":
            command_id = _text(item.get("commandId"))
            if command_id:
                event_props_by_command.setdefault(command_id, set()).update(_property_names(item.get("properties")))

    for index, item in enumerate(tactical_diff):
        if not isinstance(item, dict):
            continue
        label = _text(item.get("nodeLabel"))
        title = _text(item.get("nodeTitle"))
        path = f"tacticalDiff[{index}]({label or '?'}:{title or '?'})"

        for legacy, canonical in _LEGACY_REF_KEYS.items():
            if item.get(legacy) is not None and item.get(canonical) is None:
                violations.append({
                    "path": f"{path}.{legacy}",
                    "code": "legacy_alias",
                    "message": f"Use canonical '{canonical}' instead of legacy '{legacy}'",
                })

        if label not in _VALID_LABELS:
            violations.append({"path": f"{path}.nodeLabel", "code": "invalid_label", "message": "Unknown nodeLabel"})
        if not item.get("nodeId"):
            violations.append({"path": f"{path}.nodeId", "code": "required", "message": "nodeId is required"})
        if not title:
            violations.append({"path": f"{path}.nodeTitle", "code": "required", "message": "nodeTitle is required"})

        if label in {"Aggregate", "ReadModel", "Policy", "UI"}:
            _require_ref(violations, path, item, "boundedContextId", by_id, allow_external=True)
        if label == "Command":
            _require_ref(violations, path, item, "aggregateId", by_id)
        if label == "Event":
            _require_ref(violations, path, item, "commandId", by_id)
        if label == "Policy":
            _require_ref(violations, path, item, "triggerEventId", by_id)
            _require_ref(violations, path, item, "invokeCommandId", by_id)

        if label in {"Aggregate", "Command", "Event", "ReadModel"}:
            violations.extend(_validate_properties(path, item.get("properties")))

        fields = item.get("fields") if isinstance(item.get("fields"), dict) else {}
        if label == "Aggregate":
            if not _text(fields.get("rootEntity")):
                violations.append({
                    "path": f"{path}.fields.rootEntity",
                    "code": "required",
                    "message": "Aggregate fields.rootEntity is required",
                })
        elif label == "Command":
            input_schema = fields.get("inputSchema")
            if not isinstance(input_schema, dict) or not input_schema:
                violations.append({
                    "path": f"{path}.fields.inputSchema",
                    "code": "schema_object_required",
                    "message": "Command fields.inputSchema must be a non-empty object",
                })
            else:
                violations.extend(_validate_schema_keys(f"{path}.fields.inputSchema", input_schema))
            if not _non_empty_list(item.get("userStoryRefs")):
                violations.append({
                    "path": f"{path}.userStoryRefs",
                    "code": "required",
                    "message": "Command userStoryRefs is required",
                })
            violations.extend(_validate_gwt(path, item, event_props_by_command, aggregate_props_by_id))
        elif label == "Event":
            payload = fields.get("payload")
            if not isinstance(payload, dict) or not payload:
                violations.append({
                    "path": f"{path}.fields.payload",
                    "code": "schema_object_required",
                    "message": "Event fields.payload must be a non-empty object",
                })
            else:
                violations.extend(_validate_schema_keys(f"{path}.fields.payload", payload))
        elif label == "ReadModel":
            if not _non_empty_list(item.get("userStoryRefs")):
                violations.append({
                    "path": f"{path}.userStoryRefs",
                    "code": "required",
                    "message": "ReadModel userStoryRefs is required",
                })

    return violations


def format_tactical_contract_feedback(violations: list[dict], limit: int = 30) -> str:
    """Compact validator feedback suitable for a retry prompt."""
    shown = violations[:limit]
    lines = [f"- {v.get('path')}: {v.get('message') or v.get('code')}" for v in shown]
    if len(violations) > limit:
        lines.append(f"- ... and {len(violations) - limit} more")
    return "\n".join(lines)


def _violation(index: int, field: str, code: str, message: str) -> dict:
    return {"path": f"tacticalDiff[{index}].{field}", "code": code, "message": message}


def _text(value: Any) -> str:
    return str(value or "").strip()


def _non_empty_list(value: Any) -> bool:
    return isinstance(value, list) and len(value) > 0


def _require_ref(
    violations: list[dict],
    path: str,
    item: dict,
    key: str,
    by_id: dict[str, dict],
    *,
    allow_external: bool = False,
) -> None:
    value = _text(item.get(key))
    if not value:
        violations.append({"path": f"{path}.{key}", "code": "required", "message": f"{key} is required"})
        return
    if allow_external:
        return
    if value not in by_id:
        violations.append({
            "path": f"{path}.{key}",
            "code": "unresolved_ref",
            "message": f"{key} must reference another tacticalDiff nodeId",
        })


def _validate_properties(path: str, props: Any) -> list[dict]:
    violations: list[dict] = []
    if not isinstance(props, list) or not props:
        return [{
            "path": f"{path}.properties",
            "code": "required",
            "message": "properties must be a non-empty list",
        }]
    for idx, prop in enumerate(props):
        ppath = f"{path}.properties[{idx}]"
        if not isinstance(prop, dict):
            violations.append({"path": ppath, "code": "not_object", "message": "Property must be an object"})
            continue
        name = _text(prop.get("name"))
        if not name or not _CAMEL_CASE.match(name):
            violations.append({
                "path": f"{ppath}.name",
                "code": "invalid_property_name",
                "message": "Property name must be English camelCase",
            })
        if not _text(prop.get("type")):
            violations.append({"path": f"{ppath}.type", "code": "required", "message": "Property type is required"})
    return violations


def _validate_schema_keys(path: str, schema: dict) -> list[dict]:
    violations: list[dict] = []
    for name in schema:
        if not isinstance(name, str) or not _CAMEL_CASE.match(name):
            violations.append({
                "path": f"{path}.{name}",
                "code": "invalid_schema_key",
                "message": "Schema keys must be English camelCase",
            })
    return violations


def _property_names(props: Any) -> set[str]:
    if not isinstance(props, list):
        return set()
    return {
        str(prop.get("name"))
        for prop in props
        if isinstance(prop, dict) and prop.get("name")
    }


def _validate_gwt(
    path: str,
    command: dict,
    event_props_by_command: dict[str, set[str]],
    aggregate_props_by_id: dict[str, set[str]],
) -> list[dict]:
    violations: list[dict] = []
    gwt = command.get("gwt")
    if not isinstance(gwt, list) or not gwt:
        return [{
            "path": f"{path}.gwt",
            "code": "required",
            "message": "Command gwt must contain at least one scenario",
        }]

    command_props = _property_names(command.get("properties"))
    aggregate_props = aggregate_props_by_id.get(str(command.get("aggregateId") or ""), set())
    emitted_event_props = event_props_by_command.get(str(command.get("nodeId") or ""), set())
    for idx, scenario in enumerate(gwt):
        spath = f"{path}.gwt[{idx}]"
        if not isinstance(scenario, dict):
            violations.append({"path": spath, "code": "not_object", "message": "GWT scenario must be an object"})
            continue
        for part in ("given", "when", "then"):
            block = scenario.get(part)
            if not isinstance(block, dict):
                violations.append({"path": f"{spath}.{part}", "code": "required", "message": f"{part} block is required"})
                continue
            field_values = block.get("fieldValues")
            if not isinstance(field_values, dict):
                violations.append({
                    "path": f"{spath}.{part}.fieldValues",
                    "code": "required",
                    "message": f"{part}.fieldValues must be an object",
                })
                continue
            allowed = aggregate_props if part == "given" else command_props if part == "when" else emitted_event_props
            if not allowed:
                continue
            for name in field_values:
                if name not in allowed:
                    violations.append({
                        "path": f"{spath}.{part}.fieldValues.{name}",
                        "code": "unknown_field",
                        "message": f"{part}.fieldValues key must match related property names",
                    })
    return violations
