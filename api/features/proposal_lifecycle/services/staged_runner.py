"""042 — Detailed DDD 모드 스테이지 오케스트레이터.

스테이지 플랜(어떤 단계가 적용/생략되는지)과 스테이지 산출물을 Proposal 노드에서 읽고,
다음에 실행할 비생략 스테이지를 계산한다(재개 가능, FR-027). 각 스테이지 본문은
stage_runners/<stage>.py 가 담당하고, 여기서는 순서/상태/영속만 책임진다.

스킬은 에이전트, 백엔드는 파서/시퀀서(Principle X). 모든 변이는 사람 확정 게이트를
거친다(Principle IV) — 이 모듈은 확정된 산출물만 저장한다.
"""

from __future__ import annotations

import json
from typing import Optional

from api.platform.neo4j import get_session
from api.platform.observability.smart_logger import SmartLogger
from api.features.proposal_lifecycle.proposal_contracts import (
    DDD_STAGE_ORDER, NON_OMITTABLE_STAGES, StagePlan,
)
from api.features.proposal_lifecycle.services import proposal_interactions, proposal_state_service


# --- 상태 로드/저장 ---------------------------------------------------------

def load_state(proposal_id: str) -> Optional[dict]:
    with get_session() as session:
        rec = session.run(
            "MATCH (p:Proposal {id:$id}) RETURN "
            "p.decompositionMode AS mode, p.originalPrompt AS prompt, "
            "p.strategicDiff AS sd, p.stagePlan AS plan, "
            "p.stageArtifacts AS arts, p.currentStage AS cur, "
            "p.projectRoot AS projectRoot",
            id=proposal_id,
        ).single()
    if not rec:
        return None

    def _p(v, default):
        try:
            return json.loads(v) if v else default
        except Exception:
            return default

    return {
        "mode": rec.get("mode") or "SIMPLIFIED",
        "prompt": rec.get("prompt") or "",
        "strategic": _p(rec.get("sd"), {}),
        "stagePlan": _p(rec.get("plan"), None),
        "stageArtifacts": _p(rec.get("arts"), {}) or {},
        "stageDraftArtifacts": proposal_interactions.pending_drafts(proposal_id),
        "currentStage": rec.get("cur"),
        "projectRoot": rec.get("projectRoot"),
    }


def save_stage_plan(proposal_id: str, plan: dict) -> None:
    proposal_state_service.save_stage_plan(proposal_id, plan)


def save_stage_artifact(proposal_id: str, stage: str, artifact: dict) -> Optional[str]:
    """확정된 스테이지 산출물을 저장하고 다음 스테이지로 currentStage 를 전진."""
    state = load_state(proposal_id)
    arts = (state or {}).get("stageArtifacts") or {}
    arts[stage] = artifact
    plan = (state or {}).get("stagePlan")
    nxt = next_stage_after(plan, stage)
    cur_phase = "STRATEGIC_DDD" if nxt in DDD_STAGE_ORDER[:3] else "TACTICAL_DDD"
    if nxt is None:
        cur_phase = "STRATEGIC_DIFF" if stage in DDD_STAGE_ORDER[:3] else "TACTICAL_DIFF"
    draft_ref = None
    node = proposal_state_service.get_node(proposal_id) or {}
    if node.get("pendingDraftId"):
        draft_ref = node["pendingDraftId"]
    with get_session() as session:
        session.run(
            "MATCH (p:Proposal {id:$id}) "
            "SET p.stageArtifacts=$arts, p.currentStage=$cur, "
            "p.currentPhase=$phase, p.pendingDraftId=null, p.lifecycleStatus='ACTIVE'",
            id=proposal_id,
            arts=json.dumps(arts, ensure_ascii=False),
            cur=nxt,
            phase=cur_phase,
        )
    if draft_ref:
        proposal_interactions.confirm_draft(proposal_id, draft_ref)
    return nxt


def save_stage_draft_artifact(proposal_id: str, stage: str, artifact: dict) -> None:
    """미확정 스테이지 산출물을 저장해 새로고침 후 재실행을 막는다."""
    proposal_interactions.save_draft(proposal_id, stage, artifact)


def clear_stage_draft_artifact(proposal_id: str, stage: str) -> None:
    state = proposal_state_service.get_node(proposal_id) or {}
    draft_id = state.get("pendingDraftId")
    if draft_id:
        proposal_interactions.reject_draft(proposal_id, draft_id, "stage draft cleared")


def mark_stage_skipped(proposal_id: str, stage: str) -> Optional[str]:
    """플랜에서 해당 스테이지를 skipped 로 표시하고 currentStage 를 전진."""
    state = load_state(proposal_id) or {}
    plan = state.get("stagePlan") or {"stages": []}
    for item in plan.get("stages", []):
        if item.get("stage") == stage:
            item["skipped"] = True
    nxt = next_stage_after(plan, stage)
    with get_session() as session:
        session.run(
            "MATCH (p:Proposal {id:$id}) "
            "SET p.stagePlan=$plan, p.currentStage=$cur, p.lifecycleStatus='ACTIVE'",
            id=proposal_id,
            plan=json.dumps(plan, ensure_ascii=False),
            cur=nxt,
        )
    return nxt


# --- 스테이지 시퀀스 계산 ---------------------------------------------------

def _active_stages(plan: Optional[dict]) -> list[str]:
    """플랜에서 (적용되고 생략되지 않은) 스테이지를 정규 순서대로."""
    if not plan:
        return list(DDD_STAGE_ORDER)
    by_stage = {i.get("stage"): i for i in plan.get("stages", [])}
    out = []
    for s in DDD_STAGE_ORDER:
        item = by_stage.get(s)
        if item is None:
            continue
        if item.get("applies", True) and not item.get("skipped", False):
            out.append(s)
    return out


def _first_active_stage(plan: Optional[dict]) -> Optional[str]:
    active = _active_stages(plan)
    return active[0] if active else None


def next_stage_after(plan: Optional[dict], stage: str) -> Optional[str]:
    active = _active_stages(plan)
    if stage not in active:
        # 생략된 스테이지에서 호출돼도 정규 순서 기준 다음 활성 스테이지를 찾는다.
        try:
            idx = DDD_STAGE_ORDER.index(stage)
        except ValueError:
            return active[0] if active else None
        for s in DDD_STAGE_ORDER[idx + 1:]:
            if s in active:
                return s
        return None
    i = active.index(stage)
    return active[i + 1] if i + 1 < len(active) else None


def resume_point(proposal_id: str) -> Optional[str]:
    """재개 지점: 첫 번째 (비생략) 스테이지 중 산출물이 없는 것(FR-027)."""
    state = load_state(proposal_id)
    if not state:
        return None
    arts = state.get("stageArtifacts") or {}
    for s in _active_stages(state.get("stagePlan")):
        if s not in arts:
            return s
    return None


def validate_stage_plan(stages: list[dict]) -> Optional[dict]:
    """확정 시 검증: 행위 변경 스테이지(Discover)는 완전 생략 불가(FR-014)."""
    for item in stages:
        if item.get("stage") in NON_OMITTABLE_STAGES and item.get("skipped"):
            return {"reason": "discover_not_skippable",
                    "message": "Discover 단계는 행위 변경 Proposal 에서 완전 생략할 수 없습니다."}
    stage_set = {item.get("stage") for item in stages}
    missing = [stage for stage in DDD_STAGE_ORDER if stage not in stage_set]
    if len(stages) > 1 and missing:
        return {
            "reason": "stage_plan_incomplete",
            "message": "stagePlan은 6개 DDD stage를 모두 포함해야 합니다.",
            "missing": missing,
        }
    return None


def prior_stage_incomplete(proposal_id: str, stage: str) -> bool:
    """직전 활성 스테이지의 산출물이 없으면 True (409 가드용)."""
    state = load_state(proposal_id)
    if not state:
        return True
    active = _active_stages(state.get("stagePlan"))
    if stage not in active:
        return False
    i = active.index(stage)
    if i == 0:
        return False
    arts = state.get("stageArtifacts") or {}
    return active[i - 1] not in arts


def log_stage(proposal_id: str, stage: str, event: str) -> None:
    SmartLogger.log("INFO", f"staged {event}: {proposal_id} / {stage}",
                    category=f"proposal_lifecycle.staged.{event}",
                    params={"proposalId": proposal_id, "stage": stage})
