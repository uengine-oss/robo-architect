"""
robo-proposal-plan 스킬 호출 서비스.
승인된 Strategic Diff + Constitution → Tactical Diff + 아키텍처 구현계획 + 임팩트.

Intent 단계(전략 분해)와 분리된 Plan 단계. Constitution 없으면 진행 불가(409).
"""

from __future__ import annotations

import json
from typing import AsyncGenerator, Optional

from api.platform.neo4j import get_session
from api.platform.neo4j_helpers import load_domain_nodes
from api.platform.observability.smart_logger import SmartLogger
from api.platform.skill_runner import run_skill_lines, extract_json
from api.features.proposal_lifecycle.proposal_contracts import constitution_hash
from api.features.proposal_lifecycle.services.constitution_runner import read_constitution

_SKILL_ROOT = "robo-proposals"
_SKILL_NAME = "robo-proposal-plan"


def _load_plan_inputs(proposal_id: str) -> Optional[dict]:
    with get_session() as session:
        rec = session.run(
            "MATCH (p:Proposal {id: $id}) RETURN p.strategicDiff AS sd, "
            "p.projectRoot AS projectRoot, p.implementationPlan AS plan, "
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
        "tactical": _parse(rec.get("td"), []),
        "mode": rec.get("mode") or "SIMPLIFIED",
    }


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

    set_parts = ["p.implementationPlan = $plan"]
    params: dict = {"id": proposal_id, "plan": json.dumps(implementation_plan, ensure_ascii=False)}
    if c_hash:
        set_parts.append("p.constitutionHash = $chash")
        params["chash"] = c_hash
    if tactical_diff is not None:
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
    async for line in run_skill_lines(_SKILL_ROOT, _SKILL_NAME, human_prompt):
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
    tactical = data.get("tacticalDiff") or existing_tactical
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
