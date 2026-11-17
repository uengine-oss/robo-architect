"""
robo-proposal-plan 스킬 호출 서비스.
승인된 Strategic Diff + Constitution → Tactical Diff + 아키텍처 구현계획 + 임팩트.

Intent 단계(전략 분해)와 분리된 Plan 단계. Constitution 없으면 진행 불가(409).
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import AsyncGenerator, Optional

from api.platform.neo4j import get_session
from api.platform.neo4j_helpers import load_domain_nodes
from api.platform.observability.smart_logger import SmartLogger
from api.platform.skill_runner import extract_json, extract_json_candidates
from api.features.proposal_lifecycle.proposal_contracts import constitution_hash
from api.features.proposal_lifecycle.services.constitution_runner import read_constitution
from api.features.proposal_lifecycle.services.legacy_stage_capture import stream_stage_skill_lines
from api.features.proposal_lifecycle.services.legacy_evidence import (
    evidence_prompt_block,
    gwt_evidence_ref_errors,
    has_grounded_legacy_evidence,
    load_evidence_packet,
    optional_legacy_evidence_instruction,
    optional_legacy_refs_instruction,
    tactical_evidence_ref_errors,
    ungrounded_gwt_values,
)

_SKILL_ROOT = "robo-proposals"
_SKILL_NAME = "robo-proposal-plan"


def _load_plan_inputs(proposal_id: str) -> Optional[dict]:
    with get_session() as session:
        rec = session.run(
            "MATCH (p:Proposal {id: $id}) RETURN p.strategicDiff AS sd, "
            "p.projectRoot AS projectRoot, p.implementationPlan AS plan, p.planDraft AS planDraft, "
            "p.tacticalDiff AS td, p.decompositionMode AS mode",
            id=proposal_id,
        ).single()
    if not rec:
        return None

    def _parse(raw, default):
        try:
            return json.loads(raw) if raw else default
        except Exception:
            return default

    return {
        "strategic": _parse(rec.get("sd"), {}),
        "projectRoot": rec.get("projectRoot"),
        "prev_plan": _parse(rec.get("plan"), None),
        "plan_draft": _parse(rec.get("planDraft"), None),
        "tactical": _parse(rec.get("td"), []),
        "mode": rec.get("mode") or "SIMPLIFIED",
    }


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


def _pascal_label(value: object) -> str:
    text = str(value or "").strip()
    if not text:
        return "Aggregate"
    lowered = text.lower()
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
    if lowered in aliases:
        return aliases[lowered]
    return text[:1].upper() + text[1:]


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


def _coerce_tactical_items(raw: object) -> list[dict]:
    """Accept the canonical list and common LLM variants, then return item dicts."""
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


def normalize_tactical_diff(raw: object) -> list[dict]:
    """Normalize generated tactical diff into the canonical UI/backend contract.

    The proposal skill contract requires nodeId/nodeLabel/nodeTitle, but LLM output can
    drift. We recover those fields conservatively here so UI rendering and downstream
    proposal tooling never see `undefined:undefined`.
    """
    normalized: list[dict] = []
    for index, item in enumerate(_coerce_tactical_items(raw)):
        label = _pascal_label(item.get("nodeLabel") or item.get("entityType") or item.get("type") or item.get("label"))
        title = _title_from_item(item, label)
        node_id = _node_id_from_item(item, label, title, index)
        change_type = str(item.get("changeType") or item.get("op") or "CREATE").upper()
        if change_type not in {"CREATE", "MODIFY", "DELETE"}:
            change_type = "MODIFY"
        impact_level = str(item.get("impactLevel") or "MEDIUM").upper()
        if impact_level not in {"HIGH", "MEDIUM", "LOW", "NONE"}:
            impact_level = "MEDIUM"

        canonical = dict(item)
        # A model may place canonical node-level transport fields inside
        # ``fields``. Move those exact values without interpreting or creating
        # domain meaning, and keep only actual domain fields in ``fields``.
        nested_fields = canonical.get("fields")
        if isinstance(nested_fields, dict):
            nested_fields = dict(nested_fields)
            for key in ("properties", "userStoryRefs", "gwt", "legacyRefs"):
                if key not in canonical and key in nested_fields:
                    canonical[key] = nested_fields.pop(key)
            canonical["fields"] = nested_fields
        canonical["nodeId"] = node_id
        canonical["nodeLabel"] = label
        canonical["nodeTitle"] = title
        canonical["changeType"] = change_type
        canonical["impactLevel"] = impact_level
        canonical.setdefault("reason", item.get("reason") or f"Plan generated {label}")
        normalized.append(canonical)
    return normalized


# 설계 요소 라벨 중 도메인 속성을 갖는 것들. output-schema.md 는 이들에 대해
# "이름만 있는 빈 노드 금지"를 요구한다.
_PROPERTY_BEARING_LABELS = ("Aggregate", "Command", "Event", "ReadModel")


def property_shape_warnings(tactical: list[dict]) -> list[str]:
    """properties 원소가 계약 형태(dict)인지 점검한다 — 실패가 아니라 경고다.

    계약(output-schema.md)은 `[{"name","type","isKey",...}]` 객체 배열을 요구하지만
    모델이 `["orderId"]` 문자열 배열을 내는 경우가 실측됐다. 저장 측
    (`proposal_apply._normalize_property`)이 이름만이라도 살리므로 Plan 을 막지는
    않는다. 다만 타입·isKey 가 없으면 MCP `get_bc_design` 이 얇은 properties 를
    돌려주고 `/robo-implement` 가 빈 스텁을 스캐폴드하므로, 조용히 지나가지 않는다.
    """
    warnings: list[str] = []
    for item in tactical:
        label = item.get("nodeLabel")
        if label not in _PROPERTY_BEARING_LABELS:
            continue
        title = item.get("nodeTitle") or "<unnamed>"
        props = item.get("properties")
        if not isinstance(props, list) or not props:
            warnings.append(f"{label} {title}: properties 가 비어 있음(이름만 있는 빈 노드)")
            continue
        untyped = [x for x in props if not (isinstance(x, dict) and x.get("type"))]
        if untyped:
            warnings.append(
                f"{label} {title}: properties {len(untyped)}/{len(props)} 개에 type 이 없음 "
                f"(계약은 {{name,type,isKey,...}} 객체 배열)"
            )
    return warnings


def readmodel_traceability_errors(tactical: list[dict]) -> list[str]:
    """ReadModel 도 어느 UserStory 를 충족하는지 밝혀야 한다.

    조회·추적성 스토리(search/view/track/export)는 Command 없이 ReadModel + UI 로
    충족되는 것이 정상 설계다. 그런데 계약이 `userStoryRefs` 를 **Command 에만**
    요구해 왔기 때문에, 그런 스토리는 어떤 설계 요소와도 `IMPLEMENTS` 로 연결되지
    못하고 영구히 "설계 미반영" 으로 남았다(실측: 미반영 28건 중 25건이 조회성).

    저장 측(`proposal_apply._link_user_stories`)은 라벨을 가리지 않고 연결할 수
    있으므로, 데이터만 채워지면 된다.
    """
    errors: list[str] = []
    for item in tactical:
        if item.get("nodeLabel") != "ReadModel":
            continue
        refs = item.get("userStoryRefs")
        if not isinstance(refs, list) or not refs:
            title = item.get("nodeTitle") or "<unnamed>"
            errors.append(f"ReadModel {title} requires non-empty userStoryRefs")
    return errors


def tactical_contract_errors(
    tactical: list[dict], *, require_evidence_refs: bool = False,
) -> list[str]:
    """Validate required semantic output shape without inventing missing meaning."""
    errors: list[str] = []
    aggregates = [item for item in tactical if item.get("nodeLabel") == "Aggregate"]
    for aggregate in aggregates:
        title = aggregate.get("nodeTitle") or "<unnamed>"
        props = aggregate.get("properties")
        if not isinstance(props, list) or not props:
            errors.append(f"Aggregate {title} requires non-empty properties")
            continue
        if not all(isinstance(prop, dict) and prop.get("name") and prop.get("type") for prop in props):
            errors.append(f"Aggregate {title} requires typed property objects")
        if not any(isinstance(prop, dict) and prop.get("isKey") is True for prop in props):
            errors.append(f"Aggregate {title} requires an isKey property")
    commands = [item for item in tactical if item.get("nodeLabel") == "Command"]
    if not commands:
        return ["tacticalDiff contains no Command"]
    for command in commands:
        title = command.get("nodeTitle") or "<unnamed>"
        fields = command.get("fields")
        if not isinstance(fields, dict) or not isinstance(fields.get("inputSchema"), dict):
            errors.append(f"Command {title} requires fields.inputSchema object")
        if not isinstance(command.get("properties"), list):
            errors.append(f"Command {title} requires properties array")
        if not isinstance(command.get("userStoryRefs"), list) or not command["userStoryRefs"]:
            errors.append(f"Command {title} requires non-empty userStoryRefs")
        scenarios = command.get("gwt")
        if not isinstance(scenarios, list) or not scenarios:
            errors.append(f"Command {title} requires non-empty gwt")
            continue
        if not 1 <= len(scenarios) <= 4:
            errors.append(f"Command {title} requires 1 to 4 grounded gwt scenarios")
        for index, scenario in enumerate(scenarios):
            if not isinstance(scenario, dict) or not scenario.get("scenario"):
                errors.append(f"Command {title} gwt[{index}] requires scenario")
                continue
            if (require_evidence_refs
                    and (not isinstance(scenario.get("evidenceRefs"), list)
                         or not scenario["evidenceRefs"])):
                errors.append(f"Command {title} gwt[{index}] requires non-empty evidenceRefs")
            for phase in ("given", "when", "then"):
                value = scenario.get(phase)
                if not isinstance(value, dict) or not value.get("name"):
                    errors.append(f"Command {title} gwt[{index}].{phase} requires name")
                elif not isinstance(value.get("fieldValues"), dict):
                    errors.append(f"Command {title} gwt[{index}].{phase}.fieldValues must be an object")
    return errors


def _save_plan_draft(proposal_id: str, implementation_plan: dict,
                     tactical_diff: list[dict], impact_map: list[dict]) -> dict:
    """Persist generated-but-unconfirmed Plan artifacts for refresh recovery."""
    draft = {
        "implementationPlan": implementation_plan or {},
        "tacticalDiff": tactical_diff or [],
        "impactMap": impact_map or [],
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "confirmed": False,
    }
    with get_session() as session:
        session.run(
            "MATCH (p:Proposal {id: $id}) SET p.planDraft = $draft",
            id=proposal_id,
            draft=json.dumps(draft, ensure_ascii=False),
        )
    SmartLogger.log("INFO", f"plan_draft_saved: {proposal_id}",
                    category="proposal_lifecycle.plan.draft_saved",
                    params={"proposalId": proposal_id,
                            "tacticalCount": len(tactical_diff or []),
                            "impactCount": len(impact_map or [])})
    return draft


def _count_contexts(strategic: dict) -> int:
    """Strategic Diff 의 Epic(=BoundedContext) 수 — 마이크로서비스 완전성 판정용."""
    if not isinstance(strategic, dict):
        return 1
    return max(1, len(strategic.get("epics", []) or []))


def _legacy_ref_ids(value: object) -> set[str]:
    """Collect explicit source node ids without inferring semantic ownership."""
    found: set[str] = set()
    if isinstance(value, dict):
        refs = value.get("legacyRefs")
        if isinstance(refs, list):
            for ref in refs:
                if isinstance(ref, str) and ref.strip():
                    found.add(ref.strip())
                elif isinstance(ref, dict):
                    # Resolved Rule scenario refs use a synthetic child nodeId plus the
                    # actually inspected function in parentId.  Plan source coverage is
                    # function/table coverage, not a requirement to repeat every chosen
                    # strategic scenario as a tactical element ID.
                    node_id = (
                        ref.get("parentId") or ref.get("nodeId")
                        or ref.get("node_id") or ref.get("id")
                    )
                    if isinstance(node_id, str) and node_id.strip():
                        found.add(node_id.strip())
        for key, child in value.items():
            if key != "legacyRefs":
                found.update(_legacy_ref_ids(child))
    elif isinstance(value, list):
        for child in value:
            found.update(_legacy_ref_ids(child))
    return found


def missing_plan_legacy_refs(strategic: dict, tactical: list[dict]) -> list[str]:
    """Fail closed when Simplified decomposition silently drops inspected source functions."""
    required = _legacy_ref_ids(strategic)
    carried = _legacy_ref_ids(tactical)
    return sorted(required - carried)


def _build_plan_prompt(proposal_id: str, strategic: dict, constitution_raw: str,
                       domain_nodes: list[dict], architecture_only: bool = False,
                       tactical: Optional[list] = None,
                       evidence_packet: Optional[list[dict]] = None) -> str:
    node_list = "\n".join(
        f"- id: {n['id']}, type: {n.get('label', '')}, name: {n.get('name', '')}"
        for n in (domain_nodes or [])
    )
    # 042 — 지속 전략 메모리(있으면)를 읽기 전용 입력으로 포함해, Simplified/Detailed 모두
    # 기록된 전략(Core/Supporting/Generic·결합 posture 등)을 존중하게 한다(FR-025).
    from api.features.constitution.services import constitution_store as _cstore
    memory = _cstore.get_project_strategic_memory() or {}
    memory_block = (
        f"전략 메모리(JSON, 기록된 전략 존중):\n```json\n{json.dumps(memory, ensure_ascii=False)}\n```\n\n"
        if memory else ""
    )

    required_refs = sorted(_legacy_ref_ids(strategic))
    coverage_block = (
        "Strategic legacyRefs 보존 필수 목록(JSON):\n"
        f"```json\n{json.dumps(required_refs, ensure_ascii=False)}\n```\n"
        "각 ID를 의미상 대응하는 tactical 요소의 legacyRefs에 최소 1회 그대로 보존하라. "
        "대응을 판단할 근거가 없으면 창작하지 말고 결과를 완성하지 말라.\n\n"
    ) if has_grounded_legacy_evidence(evidence_packet) and required_refs else (
        "Analyzer/legacy evidence 보존 필수 목록 없음 — 기본 Architect 설계를 계속한다.\n\n"
    )
    evidence_block = evidence_prompt_block(evidence_packet or [])
    has_evidence = has_grounded_legacy_evidence(evidence_packet)
    legacy_input_meaning = (
        "- Legacy evidence packet: 이전 단계가 실제 확인한 semantic frame과 구조화 근거이며, "
        "이번 GWT의 선택적 보강 입력이다.\n"
        if has_evidence else
        "- Legacy evidence packet: 현재 없음. Architect 기본 설계와 GWT 생성에는 영향이 없다.\n"
    )
    packet_use_rule = (
        "packet에 있는 nodeId는 재조회하지 말고, ordered_flow와 RULE condition/effects를 "
        "입력→검증→분기→CALL/RW→최종 결과 순서로 연결하고 사용한 exact evidence ID만 기록한다. "
        "slot meaning은 Analyzer가 검증한 의미이며 profile 구조 사실을 덮어쓰지 않는다."
        if has_evidence else
        "packet이 없으므로 Strategic Diff·요구사항·Constitution만으로 설계한다. 레거시 의미나 "
        "evidence ID를 추정하지 않는다. 요구사항에 없는 중복·상태·권한 등의 도메인 정책을 "
        "경계/실패 시나리오로 만들지 않는다."
    )
    evidence_ref_example = '["<exact RULE evidence_id>"]' if has_evidence else '[]'

    if architecture_only:
        # 042 — Detailed DDD: 전술 분해(Aggregate/Command/Event)는 DDD 단계에서 이미 확정됐다.
        # 다시 만들지 말고, 그 위에서 Constitution 기반 '구현계획(아키텍처)'만 산출한다.
        return (
            f"Proposal ID: {proposal_id}\n"
            f"승인된 Strategic Diff(JSON):\n```json\n{json.dumps(strategic, ensure_ascii=False)}\n```\n\n"
            f"이미 확정된 Tactical Diff(JSON, DDD 단계 산출 — 재생성 금지):\n```json\n"
            f"{json.dumps(tactical or [], ensure_ascii=False)}\n```\n\n"
            f"Constitution(raw):\n```\n{constitution_raw}\n```\n\n"
            f"{memory_block}"
            f"{coverage_block}"
            f"현재 도메인 구성 요소 목록:\n{node_list or '(없음)'}\n\n"
            "전술 분해는 위에 **이미 확정**되어 있다. **다시 도출하지 말 것.** "
            "이 전술 설계와 Constitution 위에서 **구현계획(implementationPlan)만** JSON 으로 산출하라: "
            "architectureDecisions(배포환경/ingress/service mesh·프레임워크/프론트엔드/레포매핑) + "
            "다수 컨텍스트면 interContextIntegrations/messagingChannel/serviceDevEnvironments. "
            '출력은 {"implementationPlan": {...}} 형태로, tacticalDiff 는 출력하지 마라.'
        )

    prompt = (
        "[TASK]\n"
        "승인된 요구를 구현할 Tactical Diff와 Constitution 기반 구현계획을 생성한다.\n\n"
        "[INPUT MEANING]\n"
        "- Strategic Diff: 무엇을 구현하며 각 UserStory ID와 인수조건이 무엇인지 정의한다.\n"
        f"{legacy_input_meaning}"
        "- Constitution: 설계가 준수할 프로젝트 제약이다.\n\n"
        f"Proposal ID: {proposal_id}\n"
        f"Strategic Diff(JSON):\n```json\n{json.dumps(strategic, ensure_ascii=False)}\n```\n\n"
        f"Legacy evidence packet(JSON):\n```json\n{evidence_block}\n```\n"
        f"{packet_use_rule}\n\n"
        f"Constitution(raw):\n```\n{constitution_raw}\n```\n\n"
        f"{memory_block}"
        f"{coverage_block}"
        f"현재 도메인 구성 요소 목록:\n{node_list or '(없음)'}\n\n"
        "[DECISION RULES]\n"
        f"1. {packet_use_rule}\n"
        "   Then은 분기 중간 대입값이 아니라 이후 공통 후처리·clamp·rollback/commit을 모두 적용한 "
        "최종 반환/상태여야 한다. 범위 조건만으로 최종 상수 반환을 일반화하지 않는다.\n"
        "2. GWT의 값·상태·호출·읽기/쓰기는 현재 권위 입력에 있는 것만 확정한다. "
        "샘플 한 행을 전체 제약으로 일반화하지 않는다. 근거가 없으면 fieldValues를 비운다.\n"
        "   범위 조건을 테스트하려고 임의의 대표 숫자·코드를 계산하거나 선택하지 않는다. 실제 sample이나 "
        "RULE 상수가 없으면 조건은 scenario/name에 기호로 쓰고 해당 입력·결과 fieldValues는 비운다.\n"
        "3. 예시 스키마의 이름·상태·숫자를 복사하지 않는다. TABLE/COLUMN 이름을 번역하지 않는다.\n"
        "   실제 필드 하나의 여러 값은 필드명에 suffix를 붙여 쪼개지 말고 시나리오를 나눈다. "
        "예: pay_result_cd=90과 99는 별도 시나리오이며 pay_result_cd_cancel 같은 새 필드는 금지한다. "
        "이름 없는 함수 반환값에 ret/result 같은 합성 필드도 만들지 말고 then.name으로 표현한다.\n"
        "   RET_INVALID/RET_FAIL 같은 함수 반환 sentinel을 cnt/status 등 다른 데이터 필드의 값으로 넣지 않는다. "
        "소스가 동일 필드에 그 값을 직접 대입한 근거가 없으면 then.name으로만 반환을 표현한다.\n"
        "4. 모든 Command는 fields.inputSchema(JSON object이며 배열 금지), properties(JSON array), "
        "비어 있지 않은 userStoryRefs, "
        "1~4개의 근거 있는 gwt와 legacyRefs를 갖는다. userStoryRefs는 Strategic Diff의 "
        "실제 UserStory tempId/entityId만 사용한다.\n"
        f"5. {optional_legacy_evidence_instruction(evidence_packet)}\n"
        f"6. {optional_legacy_refs_instruction(evidence_packet)}\n\n"
        "[OUTPUT]\n"
        "robo-proposal-plan 스킬의 단일 JSON 계약대로 tacticalDiff와 implementationPlan을 출력한다.\n"
        "Command.gwt는 반드시 아래와 같은 JSON 배열이다. normal/boundary/failure 키로 감싼 객체나 "
        "Given/When/Then 문자열은 허용하지 않는다.\n"
        f'"gwt":[{{"scenario":"...","evidenceRefs":{evidence_ref_example},'
        '"given":{"name":"...","fieldValues":{}},'
        '"when":{"name":"...","fieldValues":{}},"then":{"name":"...","fieldValues":{}}}]\n'
        "Command마다 1~4개만 쓴다. 정상 경로는 1개 이상 쓰고, 경계/실패는 요구사항 또는 packet에 "
        "직접 근거가 있을 때만 추가한다. 시나리오 수를 맞추려고 정책을 만들거나 같은 의미를 복제하지 않는다. "
        "분기 전체 목록은 invariant/description에 보존하고 GWT 수를 늘려 복제하지 않는다.\n\n"
        "[FINAL CHECK]\n"
        "각 Command에 userStoryRefs와 구조화 GWT가 있는지, 현재 사용 가능한 권위 입력으로 "
        "모든 fieldValue가 입증되는지, "
        "세 입력 함수가 의미상 대응 요소에 배분됐는지 자체 점검한 뒤 출력한다. 각 scalar fieldValue는 "
        "서버가 evidence/Strategic 입력의 실제 등장 여부를 검사하며 파생·추정값은 거부한다."
    )
    return prompt


def precheck(proposal_id: str) -> Optional[dict]:
    """Plan 전제조건 검사. 통과면 None, 실패면 {code, message}."""
    inputs = _load_plan_inputs(proposal_id)
    if not inputs:
        return {"code": "NOT_FOUND", "message": f"Proposal {proposal_id} not found"}
    strategic = inputs.get("strategic") or {}
    has_strategic = isinstance(strategic, dict) and any(
        strategic.get(k) for k in ("epics", "features", "userStories", "processes")
    )
    if not has_strategic:
        return {"code": "strategic_required", "message": "승인된 Strategic Diff 가 필요합니다 (Intent 먼저)."}
    if not read_constitution(inputs.get("projectRoot")):
        return {"code": "constitution_required", "message": "프로젝트 Constitution 이 필요합니다."}
    return None


def confirm_plan(proposal_id: str, implementation_plan: dict,
                 tactical_diff: Optional[list] = None,
                 impact_map: Optional[list] = None) -> dict:
    """검토 완료된 plan 을 Proposal 노드에 확정 저장한다(Principle IV)."""
    inputs = _load_plan_inputs(proposal_id)
    project_root = inputs.get("projectRoot") if inputs else None
    strategic = inputs.get("strategic") if inputs else {}
    # 042 — staleness 해시는 헌장 본문 + 전략 메모리 결합(constitution_store 와 동일)을 쓴다.
    # 전략 메모리만 바뀌어도 plan 이 stale 되도록(FR-021) 일관된 원천을 사용.
    from api.features.constitution.services import constitution_store as _cstore
    c_hash = _cstore.project_constitution_hash()

    # plan 에 staleness 스냅샷 stamping.
    implementation_plan = dict(implementation_plan or {})
    implementation_plan["constitutionHash"] = c_hash
    implementation_plan["strategicVersion"] = (strategic or {}).get("version", 1)

    set_parts = ["p.implementationPlan = $plan", "p.planDraft = null"]
    params: dict = {"id": proposal_id, "plan": json.dumps(implementation_plan, ensure_ascii=False)}
    if c_hash:
        set_parts.append("p.constitutionHash = $chash")
        params["chash"] = c_hash
    if tactical_diff is not None:
        # evlink: 확정 저장 전 요소별 legacyRefs 를 provenance 부분집합으로 강제한다.
        from api.features.proposal_lifecycle.services.legacy_element_refs import enforce_proposal_refs
        enforce_proposal_refs(proposal_id, tactical_diff=tactical_diff)
        set_parts.append("p.tacticalDiff = $td")
        params["td"] = json.dumps(tactical_diff, ensure_ascii=False)
    if impact_map is not None:
        set_parts.append("p.impactMap = $im")
        params["im"] = json.dumps(impact_map, ensure_ascii=False)

    with get_session() as session:
        session.run(f"MATCH (p:Proposal {{id: $id}}) SET {', '.join(set_parts)}", **params)

    SmartLogger.log("INFO", f"plan_confirmed: {proposal_id}",
                    category="proposal_lifecycle.plan.confirm",
                    params={"proposalId": proposal_id})
    return {"constitutionHash": c_hash}


# 스킬은 산출물을 한 덩어리로 낼 때도 있고 tacticalDiff / implementationPlan 을
# 별도 ```json 블록으로 나눠 낼 때도 있다(실측: rawItemCount=0 인데 파싱은 성공).
# 가장 큰 후보 하나만 취하면 나머지가 통째로 버려지므로, 빠진 최상위 키만 다른
# 후보에서 채운다. 값을 만들어내지 않고 **있는 것을 잃지 않게** 하는 보정이다.
_PLAN_PAYLOAD_KEYS = ("tacticalDiff", "implementationPlan")


def _looks_like_plan_body(obj: dict) -> bool:
    """봉투 없이 implementationPlan 본문만 온 것인지 형태로 판별한다."""
    markers = ("architectureDecisions", "messagingChannel", "serviceDevEnvironments",
               "interContextIntegrations", "constitutionGaps")
    return sum(1 for m in markers if m in obj) >= 2


def _merge_plan_payload(raw: str):
    """Plan 산출물을 추출한다. 여러 블록에 흩어져 있으면 최상위 키를 합친다."""
    candidates = [c for c in extract_json_candidates(raw) if isinstance(c, dict)]
    if not candidates:
        return None
    # base 는 크기가 아니라 **기대 키를 몇 개 갖고 있는지**로 고른다. 크기만 보면
    # 완전한 산출물보다 더 큰 부분 블록(예: tacticalDiff 만 든 거대한 블록)이 이겨,
    # 이미 채워진 값을 부분 블록의 값이 밀어낸다.
    base = max(candidates,
               key=lambda c: sum(1 for k in _PLAN_PAYLOAD_KEYS if c.get(k)))
    merged = dict(base)
    # 봉투 미착용 방어: 모델이 implementationPlan 본문만 최상위로 내는 경우가 실측됐다
    # (dataKeys = architectureDecisions/messagingChannel/... ). 그대로 두면 계획까지
    # 함께 버려져 진단이 흐려지므로, 형태를 보고 봉투를 씌운다. 값은 만들지 않는다.
    if not any(merged.get(k) for k in _PLAN_PAYLOAD_KEYS) and _looks_like_plan_body(merged):
        merged = {"implementationPlan": dict(base)}
    for key in _PLAN_PAYLOAD_KEYS:
        if merged.get(key):
            continue
        for cand in candidates:
            if isinstance(cand, dict) and cand.get(key):
                merged[key] = cand[key]
                break
    # 계획이 봉투 없이 **별도 블록**으로 온 경우(tacticalDiff 는 제 블록에, 계획 본문은
    # 봉투 없이 다른 블록에). 위 루프는 `implementationPlan` 키를 찾으므로 못 잡는다.
    if not merged.get("implementationPlan"):
        for cand in candidates:
            if cand is not base and _looks_like_plan_body(cand):
                merged["implementationPlan"] = cand
                break
    return merged


async def stream_plan(proposal_id: str) -> AsyncGenerator[tuple[str, dict], None]:
    """Plan 단계 진행을 SSE 이벤트로 yield 한다."""
    err = precheck(proposal_id)
    if err:
        yield "error", err
        return

    inputs = _load_plan_inputs(proposal_id)
    strategic = inputs["strategic"]
    existing_tactical = inputs.get("tactical") or []
    # 042 — Detailed DDD: 전술 설계가 이미 확정돼 있으면 재도출하지 않고 아키텍처만 산출.
    architecture_only = inputs.get("mode") == "DETAILED_DDD" and bool(existing_tactical)

    yield "phase", {"phase": "plan", "message": (
        "이미 도출된 전술 설계 위에 Constitution 기반 구현(아키텍처) 계획 수립 중..."
        if architecture_only else "Constitution 기반 구현계획 수립 중...")}

    constitution_raw = read_constitution(inputs.get("projectRoot")) or ""
    domain_nodes = load_domain_nodes()
    evidence_packet = load_evidence_packet(proposal_id)
    human_prompt = _build_plan_prompt(proposal_id, strategic, constitution_raw, domain_nodes,
                                      architecture_only, existing_tactical, evidence_packet)

    SmartLogger.log("INFO", f"plan_start: {proposal_id}",
                    category="proposal_lifecycle.plan.start",
                    params={"proposalId": proposal_id})

    output_lines: list[str] = []
    suppress_log = False
    async for event, payload in stream_stage_skill_lines(
        proposal_id, "PLAN", _SKILL_ROOT, _SKILL_NAME, human_prompt,
    ):
        if event != "line":
            yield event, payload
            continue
        line = payload
        if line.startswith("TOOL:"):
            continue
        output_lines.append(line)
        stripped = line.strip()
        if stripped.startswith("```") or (not suppress_log and stripped in ("{", "[")):
            suppress_log = True
            continue
        if not suppress_log:
            yield "log_line", {"text": line}

    raw = "\n".join(output_lines)
    data = _merge_plan_payload(raw)
    if not data or not isinstance(data, dict):
        # 파싱 실패는 수 분~십수 분짜리 생성 결과를 통째로 버린다. 원인(잘림·중첩 펜스·
        # 산출물 부재)을 사후에 가릴 수 있도록 raw 의 규모와 앞뒤 끝을 남긴다.
        head, tail = raw[:800], raw[-800:]
        SmartLogger.log(
            "ERROR", f"plan parse failed: {proposal_id} (raw {len(raw)} chars)",
            category="proposal_lifecycle.plan.parse_failed",
            params={"proposalId": proposal_id, "rawLength": len(raw),
                    "fenceCount": raw.count("```"), "backtickCount": raw.count("`"),
                    "rawHead": head, "rawTail": tail},
        )
        yield "error", {
            "code": "PLAN_PARSE_FAILED",
            "message": "구현계획 결과 파싱 실패",
            "diagnostics": {"rawLength": len(raw), "fenceCount": raw.count("```"),
                            "rawTail": tail[-300:]},
        }
        return

    # architecture_only 면 스킬이 tacticalDiff 를 내지 않는다 → 기존(확정) 전술을 그대로 사용.
    tactical = normalize_tactical_diff(data.get("tacticalDiff") or existing_tactical)
    plan = data.get("implementationPlan", {})
    if not architecture_only:
        contract_errors = tactical_contract_errors(
            tactical,
            require_evidence_refs=has_grounded_legacy_evidence(evidence_packet),
        )
        contract_errors.extend(readmodel_traceability_errors(tactical))
        contract_errors.extend(gwt_evidence_ref_errors(tactical, evidence_packet))
        contract_errors.extend(ungrounded_gwt_values(tactical, evidence_packet, strategic))
        contract_errors.extend(tactical_evidence_ref_errors(tactical, evidence_packet))
        if contract_errors:
            # 십수 분짜리 생성이 계약 위반으로 폐기된다. 어떤 항목이 왜 걸렸는지를
            # 터미널에도 남긴다(프런트가 errors 를 못 보여주던 이력이 있다).
            # "contains no Command" 처럼 형태 자체가 어긋난 실패는 위반 문구만으로는
            # 진단이 안 된다. 스킬이 실제로 무엇을 냈는지(정규화 전후 분포와 표본)를 남긴다.
            import collections as _c
            raw_items = data.get("tacticalDiff") or []
            raw_kinds = _c.Counter(
                (x.get("entityType") or x.get("nodeLabel") or x.get("type") or "<없음>")
                for x in raw_items if isinstance(x, dict)
            )
            sample = next((x for x in raw_items if isinstance(x, dict)), None)
            SmartLogger.log(
                "ERROR",
                f"plan contract failed: {proposal_id} ({len(contract_errors)} violations)",
                category="proposal_lifecycle.plan.contract_failed",
                params={"proposalId": proposal_id, "count": len(contract_errors),
                        "errors": contract_errors[:20],
                        # 파싱된 JSON 의 최상위 키 — tacticalDiff 가 다른 이름으로
                        # 왔는지, extract_json 이 엉뚱한 객체를 골랐는지 구분한다.
                        "dataKeys": sorted(data.keys()),
                        "dataPreview": json.dumps(data, ensure_ascii=False)[:600],
                        "rawItemCount": len(raw_items),
                        "rawKinds": dict(raw_kinds),
                        "normalizedLabels": dict(_c.Counter(
                            x.get("nodeLabel") for x in tactical if isinstance(x, dict))),
                        "sampleKeys": sorted(sample.keys()) if sample else None,
                        "sampleItem": json.dumps(sample, ensure_ascii=False)[:500] if sample else None},
            )
            yield "error", {
                "code": "PLAN_TACTICAL_CONTRACT_FAILED",
                "message": "Plan tactical diff is incomplete.",
                "errors": contract_errors,
            }
            return
        # 계약 위반은 아니지만 하류(MCP 스캐폴딩)를 얇게 만드는 형태 문제는 알린다.
        shape_warnings = property_shape_warnings(tactical)
        if shape_warnings:
            SmartLogger.log(
                "WARN", f"plan property shape warnings: {proposal_id}",
                category="proposal_lifecycle.plan.property_shape",
                params={"proposalId": proposal_id, "count": len(shape_warnings),
                        "samples": shape_warnings[:5]},
            )
            yield "log_line", {"text": (
                f"⚠️ properties 형태 경고 {len(shape_warnings)}건 — "
                "type/isKey 가 없으면 구현 스캐폴딩이 빈 스텁이 됩니다."
            )}
            for w in shape_warnings[:5]:
                yield "log_line", {"text": f"   · {w}"}
            if len(shape_warnings) > 5:
                yield "log_line", {"text": f"   · … 외 {len(shape_warnings) - 5}건"}

        missing_refs = (
            missing_plan_legacy_refs(strategic, tactical)
            if has_grounded_legacy_evidence(evidence_packet) else []
        )
        if missing_refs:
            SmartLogger.log(
                "WARN", f"plan source coverage failed: {proposal_id}",
                category="proposal_lifecycle.plan.source_coverage_failed",
                params={"proposalId": proposal_id, "missing": missing_refs},
            )
            yield "error", {
                "code": "PLAN_EVIDENCE_COVERAGE_FAILED",
                "message": "Plan tactical diff omitted inspected legacy source references.",
                "missingLegacyRefs": missing_refs,
            }
            return
    if tactical:
        yield "tactical", {"tacticalDiff": tactical}
    if plan:
        yield "architecture", {"implementationPlan": plan}

    # Impact 분석(038 재사용).
    yield "phase", {"phase": "impact_map", "message": "Impact Map 생성 중..."}
    impact = []
    try:
        from api.features.proposal_lifecycle.services.impact_builder import build_impact_map
        impact = await build_impact_map(proposal_id, tactical) or []
        if impact:
            yield "impact", {"impactMap": impact}
    except Exception as e:
        SmartLogger.log("WARN", f"plan impact build failed: {e}",
                        category="proposal_lifecycle.plan.impact_warn",
                        params={"proposalId": proposal_id, "error": str(e)})

    _save_plan_draft(proposal_id, plan, tactical, impact)

    yield "done", {
        "proposalId": proposal_id,
        "tacticalDiff": tactical,
        "implementationPlan": plan,
        "impactMap": impact,
        "contextCount": _count_contexts(strategic),
    }
    SmartLogger.log("INFO", f"plan_done: {proposal_id}",
                    category="proposal_lifecycle.plan.done",
                    params={"proposalId": proposal_id})
