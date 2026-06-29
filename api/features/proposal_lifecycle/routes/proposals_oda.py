"""043 — ODA 표준 분해 모드 라우트.

intent/plan SSE(표준 근거 분해/설계) + 적합성 게이트 조회 + 면제(waive).
SSE 는 기존 패턴(Principle III), 면제는 사람 확정 게이트(Principle IV).
"""

from __future__ import annotations

import json

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from api.platform.neo4j import get_session
from api.features.proposal_lifecycle.proposal_contracts import (
    ProposalResponse, WaiveConformanceRequest,
)
from api.features.proposal_lifecycle.routes.proposals_crud import _parse_effects
from api.features.proposal_lifecycle.services import oda_runner, oda_conformance

router = APIRouter()

_PROPOSAL_WITH_EFFECTS = """
MATCH (p:Proposal {id: $id})
OPTIONAL MATCH (p)-[e:EFFECT]->(t)
RETURN p {.*} AS p,
       collect({
           nodeId: t.id, nodeLabel: labels(t)[0],
           nodeTitle: COALESCE(t.title, t.name, t.action, ''),
           reason: e.reason, impactLevel: e.impactLevel, changeType: e.changeType
       }) AS effects
"""


def _load_proposal_response(proposal_id: str) -> ProposalResponse:
    with get_session() as session:
        record = session.run(_PROPOSAL_WITH_EFFECTS, id=proposal_id).single()
    if not record:
        raise HTTPException(status_code=404, detail=f"Proposal {proposal_id} not found")
    return ProposalResponse.from_neo4j(record["p"], _parse_effects(record["effects"]))


def _sse(gen):
    async def event_stream():
        async for event_type, data in gen:
            yield f"event: {event_type}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"
    return StreamingResponse(event_stream(), media_type="text/event-stream")


def _exists(proposal_id: str) -> bool:
    with get_session() as session:
        rec = session.run("MATCH (p:Proposal {id:$id}) RETURN p.id AS id",
                          id=proposal_id).single()
    return rec is not None


# --- US1: intent (표준 정합성 + 전략 diff + 1차 적합성) ----------------------

@router.get("/{proposal_id}/stream/oda/intent")
async def stream_oda_intent(proposal_id: str):
    if not _exists(proposal_id):
        raise HTTPException(status_code=404, detail="Proposal not found")
    return _sse(oda_runner.stream_oda_intent(proposal_id))


# --- US3: plan (전술 diff + 표준 산출물 + 최종 게이트) -----------------------

@router.get("/{proposal_id}/stream/oda/plan")
async def stream_oda_plan(proposal_id: str):
    if not _exists(proposal_id):
        raise HTTPException(status_code=404, detail="Proposal not found")
    # 게이트가 차단 상태면 plan 진행 불가(FR-007).
    err = oda_conformance.ensure_can_proceed(proposal_id)
    if err and err.get("reason") == "oda_conformance_failed":
        raise HTTPException(status_code=409, detail=err)
    return _sse(oda_runner.stream_oda_plan(proposal_id))


# --- US2: 적합성 게이트 조회 / 면제 -----------------------------------------

@router.get("/{proposal_id}/oda/conformance", response_model=ProposalResponse)
async def get_conformance(proposal_id: str):
    return _load_proposal_response(proposal_id)


@router.post("/{proposal_id}/oda/waive", response_model=ProposalResponse)
async def waive_conformance(proposal_id: str, body: WaiveConformanceRequest):
    """FAIL 게이트를 명시 면제(FR-008). 사유 필수."""
    if not (body.reason or "").strip():
        raise HTTPException(status_code=422, detail={"reason": "reason_required"})
    err = oda_conformance.apply_waiver(proposal_id, body.reason.strip())
    if err:
        code = 404 if err.get("reason") == "not_found" else 422
        raise HTTPException(status_code=code, detail=err)
    return _load_proposal_response(proposal_id)
