from __future__ import annotations

import json

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from api.features.proposal_lifecycle.services.plan_runner import (
    stream_plan, confirm_plan, precheck, _load_plan_inputs,
)
from api.features.proposal_lifecycle.proposal_contracts import ConfirmPlanRequest, ProposalResponse
from api.features.proposal_lifecycle.routes.proposals_crud import _parse_effects
from api.platform.neo4j import get_session
from api.platform.observability.smart_logger import SmartLogger

router = APIRouter()


# get_proposal 과 동일한 슬라이스(노드 + EFFECT). 확정 후 갱신된 proposal(특히
# planStale=false)을 그대로 반환해 프런트가 currentProposal 을 정확히 갱신하게 한다.
_PROPOSAL_WITH_EFFECTS = """
MATCH (p:Proposal {id: $id})
OPTIONAL MATCH (p)-[e:EFFECT]->(t)
RETURN p {.*} AS p,
       collect({
           nodeId: t.id,
           nodeLabel: labels(t)[0],
           nodeTitle: COALESCE(t.title, t.name, t.action, ''),
           reason: e.reason,
           impactLevel: e.impactLevel,
           changeType: e.changeType
       }) AS effects
"""


def _load_proposal_response(proposal_id: str) -> ProposalResponse:
    with get_session() as session:
        record = session.run(_PROPOSAL_WITH_EFFECTS, id=proposal_id).single()
    if not record:
        raise HTTPException(status_code=404, detail=f"Proposal {proposal_id} not found")
    return ProposalResponse.from_neo4j(record["p"], _parse_effects(record["effects"]))


@router.get("/{proposal_id}/plan")
async def get_plan(proposal_id: str):
    """저장된 Plan 을 반환한다.

    확정된 implementationPlan 이 없으면, Generate Plan 이 만든 미확정 draft 를
    반환해 새로고침 후에도 리뷰/확정 전 상태를 복원한다.
    """
    inputs = _load_plan_inputs(proposal_id)
    if inputs is None:
        raise HTTPException(status_code=404, detail="Proposal not found")
    confirmed_plan = inputs.get("prev_plan")
    draft = inputs.get("plan_draft") if isinstance(inputs.get("plan_draft"), dict) else None
    return {
        "implementationPlan": confirmed_plan or (draft or {}).get("implementationPlan"),
        "confirmed": bool(confirmed_plan),
        "planDraft": draft,
    }


@router.get("/{proposal_id}/stream/plan")
async def stream_plan_sse(proposal_id: str):
    """Plan 단계(Tactical+아키텍처+임팩트)를 SSE 로 스트리밍한다.

    전제조건(승인된 Strategic Diff + Constitution) 미충족이면 409 로 즉시 거절해
    프런트가 인터뷰로 라우팅할 수 있게 한다(FR-010)."""
    err = precheck(proposal_id)
    if err and err.get("code") in ("constitution_required", "strategic_required"):
        raise HTTPException(status_code=409, detail={"reason": err["code"], "message": err["message"]})

    # 043 — ODA 모드면 적합성 게이트가 차단 상태일 때 plan 진행 불가(FR-007).
    from api.features.proposal_lifecycle.services import oda_conformance
    oda_err = oda_conformance.ensure_can_proceed(proposal_id)
    if oda_err and oda_err.get("reason") == "oda_conformance_failed":
        raise HTTPException(status_code=409, detail=oda_err)

    async def event_stream():
        async for event_type, data in stream_plan(proposal_id):
            payload = json.dumps(data, ensure_ascii=False)
            yield f"event: {event_type}\ndata: {payload}\n\n"

    SmartLogger.log("INFO", f"SSE plan stream started: {proposal_id}",
                    category="proposal_lifecycle.plan.stream_start",
                    params={"proposalId": proposal_id})
    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.post("/{proposal_id}/plan/confirm", response_model=ProposalResponse)
async def confirm_plan_route(proposal_id: str, body: ConfirmPlanRequest):
    """검토 완료된 plan 을 확정 저장하고, 갱신된 Proposal(planStale=false)을 반환한다."""
    confirm_plan(proposal_id, body.implementationPlan, body.tacticalDiff, body.impactMap)
    return _load_proposal_response(proposal_id)
