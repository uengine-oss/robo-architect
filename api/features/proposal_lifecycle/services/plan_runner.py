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
from api.platform.skill_runner import extract_json
from api.features.proposal_lifecycle.proposal_contracts import constitution_hash
from api.features.proposal_lifecycle.services.constitution_runner import read_constitution
from api.features.proposal_lifecycle.services.legacy_stage_capture import stream_stage_skill_lines
from api.features.proposal_lifecycle.services.legacy_evidence import (
    evidence_prompt_block,
    gwt_evidence_ref_errors,
    load_evidence_packet,
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


def tactical_contract_errors(tactical: list[dict]) -> list[str]:
    """Validate required semantic output shape without inventing missing meaning."""
    errors: list[str] = []
    commands = [item for item in tactical if item.get("nodeLabel") == "Command"]
    if not commands:
        return ["tacticalDiff contains no Command"]
    for command in commands:
        title = command.get("nodeTitle") or "<unnamed>"
        if not isinstance(command.get("userStoryRefs"), list) or not command["userStoryRefs"]:
            errors.append(f"Command {title} requires non-empty userStoryRefs")
        scenarios = command.get("gwt")
        if not isinstance(scenarios, list) or not scenarios:
            errors.append(f"Command {title} requires non-empty gwt")
            continue
        if not 2 <= len(scenarios) <= 4:
            errors.append(f"Command {title} requires 2 to 4 gwt scenarios")
        for index, scenario in enumerate(scenarios):
            if not isinstance(scenario, dict) or not scenario.get("scenario"):
                errors.append(f"Command {title} gwt[{index}] requires scenario")
                continue
            if not isinstance(scenario.get("evidenceRefs"), list) or not scenario["evidenceRefs"]:
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
                    # Resolved RULE/EXAMPLE refs use a synthetic child nodeId plus the
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
    )
    evidence_block = evidence_prompt_block(evidence_packet or [])

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

    return (
        "[TASK]\n"
        "승인된 요구를 구현할 Tactical Diff와 Constitution 기반 구현계획을 생성한다.\n\n"
        "[INPUT MEANING]\n"
        "- Strategic Diff: 무엇을 구현하며 각 UserStory ID와 인수조건이 무엇인지 정의한다.\n"
        "- Legacy evidence packet: 이전 단계가 MCP node_detail(view=frame)로 실제 확인한 target의 "
        "semantic frame과 구조화 RULE·symbol·CALL·TABLE/COLUMN/sample이다. 같은 nodeId는 중복 제거됐다.\n"
        "- Constitution: 설계가 준수할 프로젝트 제약이다.\n\n"
        f"Proposal ID: {proposal_id}\n"
        f"Strategic Diff(JSON):\n```json\n{json.dumps(strategic, ensure_ascii=False)}\n```\n\n"
        f"Legacy evidence packet(JSON):\n```json\n{evidence_block}\n```\n"
        "packet에 있는 nodeId는 재조회하지 말고 그대로 사용한다. 필요한 nodeId가 packet에 없거나 "
        "근거 상태가 insufficient/needs_context일 때만 MCP로 갭을 조회한다.\n\n"
        f"Constitution(raw):\n```\n{constitution_raw}\n```\n\n"
        f"{memory_block}"
        f"{coverage_block}"
        f"현재 도메인 구성 요소 목록:\n{node_list or '(없음)'}\n\n"
        "[DECISION RULES]\n"
        "1. packet의 ordered_flow와 RULE condition/effects를 먼저 연결해 입력→검증→분기→CALL/RW→"
        "반환/상태변화→transaction 순서로 이해한다. semantic frame의 slot/profile evidence가 최종 의미 근거이며 "
        "구조가 모호할 때 해당 절대 줄 좌표와 missing_context를 노출한다. slot meaning은 "
        "Analyzer가 검증한 해석이며 profile 구조 사실을 덮어쓰지 않는다.\n"
        "   Then은 분기 중간 대입값이 아니라 이후 공통 후처리·clamp·rollback/commit을 모두 적용한 "
        "최종 반환/상태여야 한다. 범위 조건만으로 최종 상수 반환을 일반화하지 않는다.\n"
        "2. GWT의 값·상태·호출·읽기/쓰기는 packet slot/profile RULE/sample에 있는 것만 확정한다. "
        "샘플 한 행을 전체 제약으로 일반화하지 않는다. 근거가 없으면 fieldValues를 비운다.\n"
        "   범위 조건을 테스트하려고 임의의 대표 숫자·코드를 계산하거나 선택하지 않는다. 실제 sample이나 "
        "RULE 상수가 없으면 조건은 scenario/name에 기호로 쓰고 해당 입력·결과 fieldValues는 비운다.\n"
        "3. 예시 스키마의 이름·상태·숫자를 복사하지 않는다. TABLE/COLUMN 이름을 번역하지 않는다.\n"
        "   실제 필드 하나의 여러 값은 필드명에 suffix를 붙여 쪼개지 말고 시나리오를 나눈다. "
        "예: pay_result_cd=90과 99는 별도 시나리오이며 pay_result_cd_cancel 같은 새 필드는 금지한다. "
        "이름 없는 함수 반환값에 ret/result 같은 합성 필드도 만들지 말고 then.name으로 표현한다.\n"
        "   RET_INVALID/RET_FAIL 같은 함수 반환 sentinel을 cnt/status 등 다른 데이터 필드의 값으로 넣지 않는다. "
        "소스가 동일 필드에 그 값을 직접 대입한 근거가 없으면 then.name으로만 반환을 표현한다.\n"
        "4. 모든 Command는 fields.inputSchema, properties, 비어 있지 않은 userStoryRefs, "
        "정상+근거 있는 경계/실패 gwt, legacyRefs를 갖는다. userStoryRefs는 Strategic Diff의 "
        "실제 UserStory tempId/entityId만 사용한다.\n"
        "5. 각 GWT scenario.evidenceRefs는 그 시나리오 판단에 실제 사용한 packet evidence_id만 넣는다. "
        "RULE evidence_id를 최소 1개 포함하고, 값·호출·TABLE sample을 사용했다면 대응 SYMBOL/CALL/TABLE "
        "evidence_id도 함께 넣는다. 다른 분기의 값이나 같은 함수 전체 원문을 포괄 근거로 인용하지 않는다.\n"
        "6. legacyRefs의 RULE 근거는 evidenceId·ruleId와 packet narrative text를 정확히 보존한다.\n\n"
        "   각 Command는 근거 함수 nodeId와 그 함수에서 실제 사용한 RULE 1개 이상을 정확히 인용하고, "
        "packet.tables의 직접 TABLE id를 access에 따라 reads/writes role로 모두 붙인다. TABLE 이름을 바꾸지 않는다.\n\n"
        "[OUTPUT]\n"
        "robo-proposal-plan 스킬의 단일 JSON 계약대로 tacticalDiff와 implementationPlan을 출력한다.\n"
        "Command.gwt는 반드시 아래와 같은 JSON 배열이다. normal/boundary/failure 키로 감싼 객체나 "
        "Given/When/Then 문자열은 허용하지 않는다.\n"
        '"gwt":[{"scenario":"...","evidenceRefs":["<exact RULE evidence_id>"],'
        '"given":{"name":"...","fieldValues":{}},'
        '"when":{"name":"...","fieldValues":{}},"then":{"name":"...","fieldValues":{}}}]\n'
        "Command마다 2~4개만 쓴다: 근거 있는 정상 1개와 가장 중요한 경계/실패 1개 이상. "
        "분기 전체 목록은 invariant/description에 보존하고 GWT 수를 늘려 복제하지 않는다.\n\n"
        "[FINAL CHECK]\n"
        "각 Command에 userStoryRefs와 구조화 GWT가 있는지, 각 scenario가 정확한 evidenceRefs를 갖고 "
        "모든 fieldValue가 그 인용 근거로 입증되는지, "
        "세 입력 함수가 의미상 대응 요소에 배분됐는지 자체 점검한 뒤 출력한다. 각 scalar fieldValue는 "
        "서버가 evidence/Strategic 입력의 실제 등장 여부를 검사하며 파생·추정값은 거부한다."
    )


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
    data = extract_json(raw)
    if not data or not isinstance(data, dict):
        yield "error", {"code": "PLAN_PARSE_FAILED", "message": "구현계획 결과 파싱 실패"}
        return

    # architecture_only 면 스킬이 tacticalDiff 를 내지 않는다 → 기존(확정) 전술을 그대로 사용.
    tactical = normalize_tactical_diff(data.get("tacticalDiff") or existing_tactical)
    plan = data.get("implementationPlan", {})
    if not architecture_only:
        contract_errors = tactical_contract_errors(tactical)
        contract_errors.extend(gwt_evidence_ref_errors(tactical, evidence_packet))
        contract_errors.extend(ungrounded_gwt_values(tactical, evidence_packet, strategic))
        contract_errors.extend(tactical_evidence_ref_errors(tactical, evidence_packet))
        if contract_errors:
            yield "error", {
                "code": "PLAN_TACTICAL_CONTRACT_FAILED",
                "message": "Plan tactical diff is incomplete.",
                "errors": contract_errors,
            }
            return
        missing_refs = missing_plan_legacy_refs(strategic, tactical)
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
