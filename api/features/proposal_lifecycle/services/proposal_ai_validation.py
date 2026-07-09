"""Validation helpers for Proposal AI skill outputs."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from api.features.proposal_lifecycle.services import report_contract_data as rc
from api.features.proposal_lifecycle.services.tactical_contract import (
    format_tactical_contract_feedback,
    validate_tactical_diff_contract,
)


class SkillScenario(str, Enum):
    SIMPLIFIED_STRATEGIC = "SIMPLIFIED_STRATEGIC"
    SIMPLIFIED_TACTICAL = "SIMPLIFIED_TACTICAL"
    DETAILED_STRATEGIC_FROM_DDD = "DETAILED_STRATEGIC_FROM_DDD"
    DETAILED_TACTICAL_FROM_DDD = "DETAILED_TACTICAL_FROM_DDD"


@dataclass
class ValidationResult:
    valid: bool
    violations: list[dict] = field(default_factory=list)
    warnings: list[dict] = field(default_factory=list)
    normalized_output: Any = None


def retry_count_for_scenario(scenario: str | SkillScenario | None) -> int:
    value = str(scenario.value if isinstance(scenario, SkillScenario) else scenario or "")
    if value in {
        SkillScenario.DETAILED_STRATEGIC_FROM_DDD.value,
        SkillScenario.DETAILED_TACTICAL_FROM_DDD.value,
    }:
        return 2
    return 1


def format_validation_feedback(violations: list[dict], limit: int = 30) -> str:
    shown = violations[:limit]
    lines = [f"- {v.get('path')}: {v.get('message') or v.get('code')}" for v in shown]
    if len(violations) > limit:
        lines.append(f"- ... and {len(violations) - limit} more")
    return "\n".join(lines)


def violation_summary(violations: list[dict], limit: int = 5) -> str:
    if not violations:
        return ""
    return "; ".join(
        f"{v.get('path')}={v.get('code')}" for v in violations[:limit]
    )


def validation_error_payload(
    code: str,
    message: str,
    violations: list[dict],
    *,
    limit: int = 8,
) -> dict:
    return {
        "code": code,
        "message": message,
        "violationSummary": violation_summary(violations),
        "violations": violations[:limit],
    }


def normalize_tactical_diff(raw: object) -> list[dict]:
    """Normalize common LLM tactical variants into the canonical list contract."""
    normalized: list[dict] = []
    for index, item in enumerate(_coerce_tactical_items(raw)):
        label = _pascal_label(
            item.get("nodeLabel")
            or item.get("entityType")
            or item.get("type")
            or item.get("label")
        )
        title = _title_from_item(item, label)
        node_id = _node_id_from_item(item, label, title, index)
        change_type = str(item.get("changeType") or item.get("op") or "CREATE").upper()
        if change_type not in {"CREATE", "MODIFY", "DELETE"}:
            change_type = "MODIFY"
        impact_level = str(item.get("impactLevel") or "MEDIUM").upper()
        if impact_level not in {"HIGH", "MEDIUM", "LOW", "NONE"}:
            impact_level = "MEDIUM"

        canonical = dict(item)
        canonical["nodeId"] = node_id
        canonical["nodeLabel"] = label
        canonical["nodeTitle"] = title
        canonical["changeType"] = change_type
        canonical["impactLevel"] = impact_level
        canonical.setdefault("reason", item.get("reason") or f"Generated {label}")
        normalized.append(canonical)
    return normalized


def validate_strategic_output(data: object, *, allow_clarify: bool = False) -> ValidationResult:
    output = _unwrap_output(data)
    if not isinstance(output, dict):
        return _invalid("result", "not_object", "AI output must be a JSON object")

    action = str(output.get("action") or "done")
    if action == "clarify":
        if allow_clarify and isinstance(output.get("questions"), list) and output["questions"]:
            return ValidationResult(True, normalized_output=output)
        return _invalid("questions", "required", "Clarify output requires non-empty questions")
    if action != "done":
        return _invalid("action", "invalid", "action must be 'done' or 'clarify'")

    strategic = output.get("strategicDiff")
    violations: list[dict] = []
    if not isinstance(strategic, dict):
        violations.append(_v("strategicDiff", "required", "strategicDiff object is required"))
        return ValidationResult(False, violations=violations)

    if not any(strategic.get(k) for k in ("epics", "features", "userStories", "processes")):
        violations.append(_v("strategicDiff", "empty", "strategicDiff must contain design intent items"))

    for key in ("epics", "features", "userStories", "processes"):
        items = strategic.get(key, [])
        if items is None:
            continue
        if not isinstance(items, list):
            violations.append(_v(f"strategicDiff.{key}", "not_array", f"{key} must be an array"))
            continue
        for index, item in enumerate(items):
            path = f"strategicDiff.{key}[{index}]"
            if not isinstance(item, dict):
                violations.append(_v(path, "not_object", "strategicDiff item must be an object"))
                continue
            for field_name in ("op", "entityType", "entityTitle"):
                if not item.get(field_name):
                    violations.append(_v(f"{path}.{field_name}", "required", f"{field_name} is required"))
            op = str(item.get("op") or "").upper()
            if op and op not in {"CREATE", "MODIFY", "DELETE"}:
                violations.append(_v(f"{path}.op", "invalid", "op must be CREATE, MODIFY, or DELETE"))
            if op == "CREATE" and not (item.get("tempId") or item.get("entityId")):
                violations.append(_v(f"{path}.tempId", "required", "CREATE items require tempId"))
            if key == "features" and not item.get("epicId"):
                violations.append(_v(f"{path}.epicId", "required", "Feature must reference an Epic/BC"))
            if key == "userStories":
                for field_name in ("featureId", "boundedContextId", "role", "action", "benefit"):
                    if not item.get(field_name):
                        violations.append(_v(f"{path}.{field_name}", "required", f"{field_name} is required"))

    normalized = {
        "action": "done",
        "strategicDiff": strategic,
        "journeys": output.get("journeys", []),
    }
    return ValidationResult(not violations, violations=violations, normalized_output=normalized)


def validate_plan_output(data: object, *, existing_tactical: list | None = None, architecture_only: bool = False) -> ValidationResult:
    output = _unwrap_output(data)
    if not isinstance(output, dict):
        return _invalid("result", "not_object", "AI output must be a JSON object")

    violations: list[dict] = []
    plan = output.get("implementationPlan")
    if not isinstance(plan, dict) or not plan:
        violations.append(_v("implementationPlan", "required", "implementationPlan object is required"))
    else:
        violations.extend(validate_implementation_plan(plan))

    tactical = list(existing_tactical or [])
    if not architecture_only:
        tactical = normalize_tactical_diff(output.get("tacticalDiff"))
        violations.extend(validate_tactical_diff_contract(tactical))

    normalized = {
        "tacticalDiff": tactical,
        "implementationPlan": plan or {},
        "impactMap": output.get("impactMap", []),
    }
    return ValidationResult(not violations, violations=violations, normalized_output=normalized)


def validate_tactical_output(data: object) -> ValidationResult:
    output = _unwrap_output(data)
    if not isinstance(output, dict):
        return _invalid("result", "not_object", "AI output must be a JSON object")
    tactical = normalize_tactical_diff(output.get("tacticalDiff"))
    violations = validate_tactical_diff_contract(tactical)
    return ValidationResult(not violations, violations=violations, normalized_output={"tacticalDiff": tactical})


def validate_implementation_plan(plan: dict) -> list[dict]:
    violations: list[dict] = []
    decisions = plan.get("architectureDecisions")
    gaps = plan.get("constitutionGaps") if isinstance(plan.get("constitutionGaps"), list) else []
    if not isinstance(decisions, list) or not decisions:
        violations.append(_v("implementationPlan.architectureDecisions", "required", "architectureDecisions are required"))
        return violations

    required = {"DEPLOYMENT_ENV", "INGRESS", "SERVICE_MESH_FRAMEWORK", "FRONTEND", "REPO_MAPPING"}
    covered = {
        d.get("aspect")
        for d in decisions
        if isinstance(d, dict) and d.get("aspect") and (d.get("decision") or d.get("constitutionRef"))
    }
    covered.update(str(g) for g in gaps if g)
    missing = sorted(required - covered)
    for aspect in missing:
        violations.append(_v(f"implementationPlan.{aspect}", "required", "Architecture aspect must have a decision or constitutionGap"))
    return violations


def validate_stage_artifact(stage: str, artifact: object) -> ValidationResult:
    stage = stage.upper()
    if not isinstance(artifact, dict):
        return _invalid("artifact", "not_object", f"{stage} artifact must be an object")
    # 015-report-issue: 봉투({DiscoverArtifact:{...}})로 들어와도 언랩해 검증(렌더와 동일 규약).
    artifact = rc.unwrap_stage_artifact(stage, artifact)

    required_arrays = {
        "DISCOVER": "events",
        "DECOMPOSE": "subDomains",
        "STRATEGIZE": "classifications",
        "CONNECT": "interactions",
        "DEFINE": "contexts",
        "TACTICAL": "aggregates",
    }
    key = required_arrays.get(stage)
    violations: list[dict] = []
    warnings: list[dict] = []
    if key:
        value = artifact.get(key)
        if not isinstance(value, list) or not value:
            violations.append(_v(f"{stage}.{key}", "required", f"{stage} requires non-empty {key}"))

    if stage == "STRATEGIZE":
        for index, item in enumerate(artifact.get("classifications") or []):
            if isinstance(item, dict) and item.get("kind") not in {"CORE", "SUPPORTING", "GENERIC"}:
                violations.append(_v(f"STRATEGIZE.classifications[{index}].kind", "invalid", "kind must be CORE, SUPPORTING, or GENERIC"))
    elif stage == "DEFINE":
        for index, ctx in enumerate(artifact.get("contexts") or []):
            if isinstance(ctx, dict) and len(ctx.get("ubiquitousLanguage") or []) < 5:
                warnings.append(_v(f"DEFINE.contexts[{index}].ubiquitousLanguage", "quality", "At least five ubiquitous language terms are recommended", severity="warning"))
    elif stage == "TACTICAL":
        for index, aggregate in enumerate(artifact.get("aggregates") or []):
            if isinstance(aggregate, dict) and len(aggregate.get("invariants") or []) < 2:
                warnings.append(_v(f"TACTICAL.aggregates[{index}].invariants", "quality", "At least two invariants are recommended", severity="warning"))

    return ValidationResult(not violations, violations=violations, warnings=warnings, normalized_output=artifact)


def tactical_feedback(violations: list[dict]) -> str:
    return format_tactical_contract_feedback(violations)


_TACTICAL_COLLECTION_LABELS = {
    "aggregates": "Aggregate",
    "commands": "Command",
    "events": "Event",
    "readModels": "ReadModel",
    "readmodels": "ReadModel",
    "policies": "Policy",
    "invariants": "Invariant",
    "uis": "UI",
    "ui": "UI",
    "screens": "UI",
}


def _coerce_tactical_items(raw: object) -> list[dict]:
    if isinstance(raw, list):
        return [item for item in raw if isinstance(item, dict)]
    if not isinstance(raw, dict):
        return []
    if isinstance(raw.get("items"), list):
        return [item for item in raw["items"] if isinstance(item, dict)]

    items: list[dict] = []
    for key, label in _TACTICAL_COLLECTION_LABELS.items():
        values = raw.get(key)
        if not isinstance(values, list):
            continue
        for value in values:
            if isinstance(value, dict):
                item = dict(value)
                item.setdefault("nodeLabel", label)
                items.append(item)
    return items


def _pascal_label(value: object) -> str:
    text = str(value or "").strip()
    aliases = {
        "aggregate": "Aggregate",
        "command": "Command",
        "event": "Event",
        "readmodel": "ReadModel",
        "read_model": "ReadModel",
        "policy": "Policy",
        "invariant": "Invariant",
        "ui": "UI",
        "screen": "UI",
        "valueobject": "ValueObject",
        "value_object": "ValueObject",
    }
    return aliases.get(text.lower(), text[:1].upper() + text[1:] if text else "Aggregate")


def _title_from_item(item: dict, label: str) -> str:
    for key in (
        "nodeTitle", "entityTitle", "title", "displayName", "name",
        "aggregateName", "commandName", "eventName", "readModelName", "policyName",
    ):
        value = item.get(key)
        if value:
            return str(value)
    fields = item.get("fields") if isinstance(item.get("fields"), dict) else {}
    for key in ("name", "title", "rootEntity"):
        value = fields.get(key)
        if value:
            return str(value)
    return label


def _node_id_from_item(item: dict, label: str, title: str, index: int) -> str:
    for key in ("nodeId", "tempId", "entityId", "id"):
        value = item.get(key)
        if value:
            return str(value)
    slug = "".join(ch if ch.isalnum() else "-" for ch in title).strip("-") or str(index + 1)
    return f"{label.upper()}-{slug}"


def _unwrap_output(data: object) -> object:
    if not isinstance(data, dict):
        return data
    result = data.get("result")
    if isinstance(result, dict):
        merged = dict(result)
        if data.get("action") and not merged.get("action"):
            merged["action"] = data.get("action")
        return merged
    return data


def _invalid(path: str, code: str, message: str) -> ValidationResult:
    return ValidationResult(False, violations=[_v(path, code, message)])


def _v(path: str, code: str, message: str, *, severity: str = "blocking") -> dict:
    return {"path": path, "code": code, "message": message, "severity": severity}
