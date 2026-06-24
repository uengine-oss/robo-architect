"""042 — Staged DDD decomposition 모드 라우트.

모드 전환 + 스코프(스테이지 플랜) + 스테이지 실행(SSE) + 확정/생략 + consolidate.
SSE 는 기존 intent/plan 스트림 패턴(Principle III), 변이는 확정 게이트(Principle IV).
"""

from __future__ import annotations

import json

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from api.platform.neo4j import get_session
from api.platform.observability.smart_logger import SmartLogger
from api.features.proposal_lifecycle.proposal_contracts import (
    ProposalResponse, ModeUpgradeRequest, ConfirmStagePlanRequest,
    StageConfirmRequest, StageSkipRequest, DddStage, DecompositionMode,
)
from api.features.proposal_lifecycle.routes.proposals_crud import _parse_effects
from api.features.proposal_lifecycle.services import staged_runner
from api.features.proposal_lifecycle.services.stage_runners import (
    scope as scope_runner,
    discover as discover_runner,
    decompose as decompose_runner,
    strategize as strategize_runner,
    connect as connect_runner,
    define as define_runner,
    tactical as tactical_runner,
)

router = APIRouter()

_STAGE_RUNNERS = {
    DddStage.DISCOVER.value: discover_runner,
    DddStage.DECOMPOSE.value: decompose_runner,
    DddStage.STRATEGIZE.value: strategize_runner,
    DddStage.CONNECT.value: connect_runner,
    DddStage.DEFINE.value: define_runner,
    DddStage.TACTICAL.value: tactical_runner,
}

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


# --- US1: 모드 업그레이드 ---------------------------------------------------

@router.post("/{proposal_id}/mode", response_model=ProposalResponse)
async def upgrade_mode(proposal_id: str, body: ModeUpgradeRequest):
    """Simplified → Detailed DDD 업그레이드. plan 확정 후엔 409(FR-003)."""
    state = staged_runner.load_state(proposal_id)
    if state is None:
        raise HTTPException(status_code=404, detail="Proposal not found")
    # plan 확정 여부 확인(implementationPlan 존재).
    with get_session() as session:
        rec = session.run(
            "MATCH (p:Proposal {id:$id}) RETURN p.implementationPlan AS plan",
            id=proposal_id,
        ).single()
    if rec and rec.get("plan"):
        raise HTTPException(status_code=409, detail={"reason": "plan_confirmed",
                            "message": "이미 확정된 plan 이 있어 모드 업그레이드 불가."})
    with get_session() as session:
        session.run(
            "MATCH (p:Proposal {id:$id}) SET p.decompositionMode=$mode, p.currentStage='SCOPE'",
            id=proposal_id, mode=body.decompositionMode.value,
        )
    SmartLogger.log("INFO", f"mode upgraded: {proposal_id} → {body.decompositionMode.value}",
                    category="proposal_lifecycle.staged.mode_upgrade",
                    params={"proposalId": proposal_id})
    return _load_proposal_response(proposal_id)


# --- US3: 스코프 분류 → 스테이지 플랜 ---------------------------------------

@router.get("/{proposal_id}/stream/scope")
async def stream_scope(proposal_id: str):
    """robo-proposal-scope 실행 → stage_plan SSE(FR-009)."""
    if staged_runner.load_state(proposal_id) is None:
        raise HTTPException(status_code=404, detail="Proposal not found")
    return _sse(scope_runner.stream_scope(proposal_id))


@router.post("/{proposal_id}/stage-plan/confirm", response_model=ProposalResponse)
async def confirm_stage_plan(proposal_id: str, body: ConfirmStagePlanRequest):
    """아키텍트가 확정한 스테이지 플랜을 저장(FR-010/FR-014/FR-015)."""
    stages = [d.model_dump() for d in body.stages]
    err = staged_runner.validate_stage_plan(stages)
    if err:
        raise HTTPException(status_code=422, detail=err)
    # applies/recommendSkip/reason 은 기존 제안값을 보존하고 skipped 만 반영.
    state = staged_runner.load_state(proposal_id)
    existing = ((state or {}).get("stagePlan") or {}).get("stages", [])
    by_stage = {i.get("stage"): dict(i) for i in existing}
    merged = []
    for d in stages:
        base = by_stage.get(d["stage"], {"stage": d["stage"], "applies": True,
                                         "recommendSkip": False, "reason": ""})
        base["skipped"] = d.get("skipped", False)
        merged.append(base)
    plan = {"version": 1, "stages": merged,
            "classifiedReach": ((state or {}).get("stagePlan") or {}).get("classifiedReach")}
    staged_runner.save_stage_plan(proposal_id, plan)
    return _load_proposal_response(proposal_id)


# --- US2: 스테이지 실행 / 확정 / 생략 ---------------------------------------

@router.get("/{proposal_id}/stream/stage/{stage}")
async def stream_stage(proposal_id: str, stage: str, feedback: str | None = None):
    """단일 스테이지 스킬 실행(SSE). 직전 스테이지 미완료면 409.

    feedback 가 주어지면 스킬 프롬프트에 '사용자 피드백(재생성)'으로 주입해 같은 단계를
    피드백 반영본으로 다시 생성한다(단계별 유저 피드백)."""
    stage = stage.upper()
    runner = _STAGE_RUNNERS.get(stage)
    if not runner:
        raise HTTPException(status_code=404, detail=f"Unknown stage {stage}")
    if staged_runner.load_state(proposal_id) is None:
        raise HTTPException(status_code=404, detail="Proposal not found")
    if staged_runner.prior_stage_incomplete(proposal_id, stage):
        raise HTTPException(status_code=409, detail={"reason": "prior_stage_incomplete",
                            "message": "직전 단계 산출물이 없습니다."})
    return _sse(runner.stream(proposal_id, feedback))


@router.post("/{proposal_id}/stage/{stage}/confirm", response_model=ProposalResponse)
async def confirm_stage(proposal_id: str, stage: str, body: StageConfirmRequest):
    """편집된 산출물 확정 → 지속 전략 메모리 승격 + currentStage 전진(FR-006/FR-016/FR-019)."""
    stage = stage.upper()
    if stage not in _STAGE_RUNNERS:
        raise HTTPException(status_code=404, detail=f"Unknown stage {stage}")
    # 충돌 해소 + 메모리 승격은 strategic_memory 가 담당(US4).
    from api.features.proposal_lifecycle.services import strategic_memory
    err = strategic_memory.apply_stage_confirmation(
        proposal_id, stage, body.artifact,
        [c.model_dump() for c in body.conflictResolutions],
    )
    if err:
        raise HTTPException(status_code=409, detail=err)
    staged_runner.save_stage_artifact(proposal_id, stage, body.artifact)
    staged_runner.log_stage(proposal_id, stage, "confirm")
    return _load_proposal_response(proposal_id)


@router.post("/{proposal_id}/stage/{stage}/skip", response_model=ProposalResponse)
async def skip_stage(proposal_id: str, stage: str, body: StageSkipRequest):
    """스테이지 생략(Discover 불가, FR-014)."""
    stage = stage.upper()
    if stage not in _STAGE_RUNNERS:
        raise HTTPException(status_code=404, detail=f"Unknown stage {stage}")
    err = staged_runner.validate_stage_plan([{"stage": stage, "skipped": True}])
    if err:
        raise HTTPException(status_code=422, detail=err)
    staged_runner.mark_stage_skipped(proposal_id, stage)
    staged_runner.log_stage(proposal_id, stage, "skip")
    return _load_proposal_response(proposal_id)


# --- US6: consolidate → 표준 strategicDiff/tacticalDiff ----------------------

@router.post("/{proposal_id}/staged/consolidate", response_model=ProposalResponse)
async def consolidate(proposal_id: str):
    """스테이지 산출물을 표준 Strategic/Tactical Diff 로 수렴(FR-007/FR-023)."""
    from api.features.proposal_lifecycle.services import staged_consolidate
    err = staged_consolidate.consolidate(proposal_id)
    if err:
        raise HTTPException(status_code=400, detail=err)
    return _load_proposal_response(proposal_id)
