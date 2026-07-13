"""Canonical tacticalDiff contract validation for Proposal Plan drafts."""

from __future__ import annotations

import re
from typing import Any


_CAMEL_CASE = re.compile(r"^[a-z][A-Za-z0-9]*$")
# VO/Enum 의 타입명(속성 `type` 으로 참조되는 이름)은 영어 PascalCase.
_PASCAL_CASE = re.compile(r"^[A-Z][A-Za-z0-9]*$")
# `List<Money>` / `Set<OrderStatus>` / `Optional<Address>` 같은 컨테이너 표기에서 원소 타입 추출.
_TYPE_WRAPPER = re.compile(r"^[A-Za-z]+\s*<\s*([A-Za-z0-9]+)\s*>$")
_VALID_LABELS = {
    "Aggregate", "Command", "Event", "ReadModel", "Policy", "UI", "Invariant",
    # 015-issue2: 전술 설계의 모델 요소 — Aggregate 에 종속되며 속성 타입으로 참조된다.
    "ValueObject", "Enumeration",
}
# 속성 `type` 이 VO/Enum 타입을 참조할 수 있는(=활용처가 되는) 라벨.
_TYPE_CONSUMER_LABELS = {"Aggregate", "Command", "Event", "ReadModel"}
_LEGACY_REF_KEYS = {
    "aggregate": "aggregateId",
    "boundedContext": "boundedContextId",
    "emittedBy": "commandId",
    "trigger": "triggerEventId",
    "invokes": "invokeCommandId",
    "traces": "userStoryRefs",
}


def validate_tactical_diff_contract(
    tactical_diff: list[dict] | None,
    *,
    known_bc_ids: set[str] | None = None,
) -> list[dict]:
    """Return contract violations for generated tacticalDiff.

    This intentionally validates the persisted preview contract, not just display
    fields. Broken drafts must not reach Neo4j because preview projection and
    apply logic both depend on these refs and structured properties.

    `known_bc_ids` (optional): BoundedContext ids the graph can actually resolve —
    the strategic Diff's Epic/BoundedContext tempIds plus live BoundedContext ids.
    When provided, `boundedContextId` must be one of them; otherwise Accept would
    create Aggregates dangling outside any BoundedContext.
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
    # 015-issue2: 선언된 VO/Enum 타입명 → 정의 경로(활용 검증용) / 소비된 타입명 집합.
    declared_types: dict[str, str] = {}
    consumed_types: set[str] = set()
    label_counts: dict[str, int] = {}

    for index, item in enumerate(tactical_diff):
        if not isinstance(item, dict):
            violations.append(_violation(index, "item", "not_object", "tacticalDiff item must be an object"))
            continue
        label = item.get("nodeLabel")
        label_counts[str(label)] = label_counts.get(str(label), 0) + 1
        if label == "Aggregate":
            aggregate_props_by_id[str(item.get("nodeId") or "")] = _property_names(item.get("properties"))
        if label == "Event":
            command_id = _text(item.get("commandId"))
            if command_id:
                event_props_by_command.setdefault(command_id, set()).update(_property_names(item.get("properties")))
        if label in {"ValueObject", "Enumeration"}:
            fields = item.get("fields") if isinstance(item.get("fields"), dict) else {}
            type_name = _text(fields.get("typeName"))
            if type_name:
                declared_types[type_name] = f"tacticalDiff[{index}]({label}:{_text(item.get('nodeTitle')) or '?'})"
        if label in _TYPE_CONSUMER_LABELS:
            consumed_types.update(_property_types(item.get("properties")))

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
            _require_bc_ref(violations, path, item, by_id, known_bc_ids)
        if label == "Command":
            _require_ref(violations, path, item, "aggregateId", by_id)
        if label == "Event":
            _require_ref(violations, path, item, "commandId", by_id)
        if label == "Policy":
            _require_ref(violations, path, item, "triggerEventId", by_id)
            _require_ref(violations, path, item, "invokeCommandId", by_id)
        # 015-issue2/6: VO/Enum/Invariant 는 Aggregate 종속 — 이 참조로 그래프에 매달린다.
        if label in {"ValueObject", "Enumeration", "Invariant"}:
            _require_ref(violations, path, item, "aggregateId", by_id)

        if label in {"Aggregate", "Command", "Event", "ReadModel", "ValueObject"}:
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
        elif label in {"ValueObject", "Enumeration"}:
            violations.extend(_validate_model_type(path, label, fields))

    violations.extend(_validate_type_coverage(label_counts, declared_types, consumed_types))
    return violations


def _validate_model_type(path: str, label: str, fields: dict) -> list[dict]:
    """015-issue2: ValueObject/Enumeration 의 typeName(+ Enum items) 검증."""
    violations: list[dict] = []
    type_name = _text(fields.get("typeName"))
    if not type_name or not _PASCAL_CASE.match(type_name):
        violations.append({
            "path": f"{path}.fields.typeName",
            "code": "invalid_type_name",
            "message": (
                f"{label} fields.typeName is required and must be English PascalCase "
                "(it is the name other nodes reference in properties[].type)"
            ),
        })
    if label == "Enumeration":
        items = fields.get("items")
        if not _non_empty_list(items) or not all(_text(i) for i in items):
            violations.append({
                "path": f"{path}.fields.items",
                "code": "required",
                "message": 'Enumeration fields.items must be a non-empty list of literal names (e.g. ["PENDING","PAID"])',
            })
    return violations


def _validate_type_coverage(
    label_counts: dict[str, int],
    declared_types: dict[str, str],
    consumed_types: set[str],
) -> list[dict]:
    """015-issue2: Aggregate 가 있으면 VO/Enum 을 반드시 설계하고, 선언한 타입은 속성으로 활용한다."""
    violations: list[dict] = []
    if not label_counts.get("Aggregate"):
        return violations
    for label, key in (("ValueObject", "valueObject"), ("Enumeration", "enumeration")):
        if not label_counts.get(label):
            violations.append({
                "path": f"tacticalDiff.{key}",
                "code": "required",
                "message": (
                    f"tacticalDiff must contain at least one {label} node when Aggregates exist "
                    f"(model the domain's {label}s and reference them from properties[].type)"
                ),
            })
    for type_name, defined_at in sorted(declared_types.items()):
        if type_name not in consumed_types:
            violations.append({
                "path": f"{defined_at}.fields.typeName",
                "code": "unused_type",
                "message": (
                    f"Declared type '{type_name}' is never used — some Aggregate/Command/Event/ReadModel "
                    f"property must have type '{type_name}' (or a container like 'List<{type_name}>')"
                ),
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


def _require_bc_ref(
    violations: list[dict],
    path: str,
    item: dict,
    by_id: dict[str, dict],
    known_bc_ids: set[str] | None,
) -> None:
    """boundedContextId 검증. 015-issue6: 그래프가 해소 가능한 BC 만 허용한다.

    Accept 시 `BC-order` 같은 유령 참조는 어떤 BoundedContext 에도 매칭되지 않아
    Aggregate 가 BC 밖에 떠 버린다(라이브 반영 실패). 전략 Diff 의 Epic tempId
    (Epic ≡ BoundedContext 컨테이너) 또는 실재 BC id 만 허용한다.
    """
    value = _text(item.get("boundedContextId"))
    if not value:
        violations.append({
            "path": f"{path}.boundedContextId",
            "code": "required",
            "message": "boundedContextId is required",
        })
        return
    if value in by_id:
        return
    if known_bc_ids is None:
        return
    if value not in known_bc_ids:
        known = ", ".join(sorted(known_bc_ids)[:8]) or "(none)"
        violations.append({
            "path": f"{path}.boundedContextId",
            "code": "unresolved_bounded_context",
            "message": (
                f"boundedContextId '{value}' does not exist. Use an Epic tempId from this proposal's "
                f"strategicDiff (Epic ≡ BoundedContext) or a live BoundedContext id. Known: {known}"
            ),
        })


def _property_types(props: Any) -> set[str]:
    """properties[].type 에서 참조된 타입명 집합(컨테이너 표기 원소 타입 포함)."""
    out: set[str] = set()
    if not isinstance(props, list):
        return out
    for prop in props:
        if not isinstance(prop, dict):
            continue
        raw = _text(prop.get("type"))
        if not raw:
            continue
        out.add(raw)
        wrapped = _TYPE_WRAPPER.match(raw)
        if wrapped:
            out.add(wrapped.group(1))
    return out


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
            if block is None:
                violations.append({
                    "path": f"{spath}.{part}",
                    "code": "required",
                    "message": (
                        f"{part} block is required — expected an object like "
                        '{"fieldValues": {"propertyName": value}}'
                    ),
                })
                continue
            if not isinstance(block, dict):
                violations.append({
                    "path": f"{spath}.{part}",
                    "code": "invalid_type",
                    "message": (
                        f"{part} must be an object like "
                        '{"fieldValues": {"propertyName": value}} — got '
                        f"{type(block).__name__}"
                    ),
                })
                continue
            field_values = block.get("fieldValues")
            if field_values is None:
                violations.append({
                    "path": f"{spath}.{part}.fieldValues",
                    "code": "required",
                    "message": f"{part}.fieldValues object is required (keys must match related property names)",
                })
                continue
            if not isinstance(field_values, dict):
                violations.append({
                    "path": f"{spath}.{part}.fieldValues",
                    "code": "invalid_type",
                    "message": (
                        f"{part}.fieldValues must be an object mapping property names to "
                        f"values — got {type(field_values).__name__}"
                    ),
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
