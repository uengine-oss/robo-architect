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
        canonical["nodeId"] = node_id
        canonical["nodeLabel"] = label
        canonical["nodeTitle"] = title
        canonical["changeType"] = change_type
        canonical["impactLevel"] = impact_level
        canonical.setdefault("reason", item.get("reason") or f"Plan generated {label}")
        normalized.append(canonical)
    return normalized


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


def _build_plan_prompt(proposal_id: str, strategic: dict, constitution_raw: str,
                       domain_nodes: list[dict], architecture_only: bool = False,
                       tactical: Optional[list] = None) -> str:
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
            f"현재 도메인 구성 요소 목록:\n{node_list or '(없음)'}\n\n"
            "전술 분해는 위에 **이미 확정**되어 있다. **다시 도출하지 말 것.** "
            "이 전술 설계와 Constitution 위에서 **구현계획(implementationPlan)만** JSON 으로 산출하라: "
            "architectureDecisions(배포환경/ingress/service mesh·프레임워크/프론트엔드/레포매핑) + "
            "다수 컨텍스트면 interContextIntegrations/messagingChannel/serviceDevEnvironments. "
            '출력은 {"implementationPlan": {...}} 형태로, tacticalDiff 는 출력하지 마라.'
        )

    return (
        f"Proposal ID: {proposal_id}\n"
        f"승인된 Strategic Diff(JSON):\n```json\n{json.dumps(strategic, ensure_ascii=False)}\n```\n\n"
        f"Constitution(raw):\n```\n{constitution_raw}\n```\n\n"
        f"{memory_block}"
        f"현재 도메인 구성 요소 목록:\n{node_list or '(없음)'}\n\n"
        "위 Strategic Diff 와 Constitution 을 바탕으로 Tactical Diff 와 "
        "Constitution 기반 구현계획(architectureDecisions + 다수 컨텍스트면 "
        "interContextIntegrations/messagingChannel/serviceDevEnvironments)을 JSON 으로 출력하라."
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
    human_prompt = _build_plan_prompt(proposal_id, strategic, constitution_raw, domain_nodes,
                                      architecture_only, existing_tactical)

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
