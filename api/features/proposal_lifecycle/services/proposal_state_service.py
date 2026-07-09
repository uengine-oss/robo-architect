from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from api.features.proposal_lifecycle.proposal_contracts import (
    DDD_STAGE_ORDER,
    append_status_history,
)
from api.features.proposal_lifecycle.services import lifecycle_steps, proposal_interactions
from api.features.proposal_lifecycle.services import report_contract_data as rc
from api.platform.neo4j import get_session
from api.platform.observability.smart_logger import SmartLogger

PHASE_ORDER = [
    "START_OR_RESUME",
    "SCOPE",
    "STRATEGIC_DDD",
    "STRATEGIC_DIFF",
    "TACTICAL_DDD",
    "TACTICAL_DIFF",
    "CONSTITUTION",
    "CONTEXT",
    "TASKS",
    "IMPLEMENT",
    "TEST",
    "SUBMIT",
    "ACCEPT",
]


def _json(data: Any) -> str:
    return json.dumps(data if data is not None else {}, ensure_ascii=False)


def _parse(raw: Any, default: Any) -> Any:
    if raw is None:
        return default
    if isinstance(raw, (dict, list)):
        return raw
    try:
        return json.loads(raw)
    except Exception:
        return default


def get_node(proposal_id: str) -> dict | None:
    with get_session() as session:
        rec = session.run(
            "MATCH (p:Proposal {id:$id}) RETURN p {.*} AS p",
            id=proposal_id,
        ).single()
    return dict(rec["p"]) if rec else None


def hydrate_for_response(node: dict) -> dict:
    proposal_id = node.get("id")
    if not proposal_id:
        return node
    hydrated = dict(node)
    drafts = proposal_interactions.pending_drafts(proposal_id)
    interactions = proposal_interactions.recent_interactions(proposal_id)
    hydrated["draftArtifacts"] = _json(drafts) if drafts else None
    hydrated["interactions"] = _json(interactions) if interactions else None
    return hydrated


def initialize_lifecycle(proposal_id: str, *, phase: str = "START_OR_RESUME") -> None:
    with get_session() as session:
        session.run(
            """
            MATCH (p:Proposal {id:$id})
            SET p.lifecycleStatus = coalesce(p.lifecycleStatus, 'ACTIVE'),
                p.currentPhase = coalesce(p.currentPhase, $phase),
                p.resumeToken = coalesce(p.resumeToken, $resumeToken),
                p.skillVersion = coalesce(p.skillVersion, $skillVersion),
                p.schemaVersion = coalesce(p.schemaVersion, $schemaVersion),
                p.pendingQuestionId = coalesce(p.pendingQuestionId, null),
                p.pendingDraftId = coalesce(p.pendingDraftId, null)
            """,
            id=proposal_id,
            phase=phase,
            resumeToken=f"{proposal_id}:start",
            skillVersion=proposal_interactions.SKILL_VERSION,
            schemaVersion=proposal_interactions.SCHEMA_VERSION,
        )


def set_lifecycle(
    proposal_id: str,
    *,
    lifecycle_status: str | None = None,
    current_phase: str | None = None,
    current_stage: str | None = None,
    clear_pending_question: bool = False,
    clear_pending_draft: bool = False,
) -> None:
    sets = []
    params: dict[str, Any] = {"id": proposal_id}
    if lifecycle_status:
        sets.append("p.lifecycleStatus = $lifecycleStatus")
        params["lifecycleStatus"] = lifecycle_status
    if current_phase:
        sets.append("p.currentPhase = $currentPhase")
        params["currentPhase"] = current_phase
    if current_stage is not None:
        sets.append("p.currentStage = $currentStage")
        params["currentStage"] = current_stage
    if clear_pending_question:
        sets.append("p.pendingQuestionId = null")
    if clear_pending_draft:
        sets.append("p.pendingDraftId = null")
    if not sets:
        return
    sets.append("p.resumeToken = $resumeToken")
    params["resumeToken"] = f"{proposal_id}:{datetime.now(timezone.utc).timestamp()}"
    with get_session() as session:
        session.run(f"MATCH (p:Proposal {{id:$id}}) SET {', '.join(sets)}", **params)
    SmartLogger.log(
        "INFO",
        f"proposal lifecycle updated: {proposal_id}",
        category="proposal_lifecycle.state.updated",
        params={"proposalId": proposal_id, "updates": {k: v for k, v in params.items() if k != "id"}},
    )


_STEP_REASONS = {
    "SCOPE": "Detailed DDD requires a confirmed stagePlan",
    "STRATEGIC_DDD": "next active strategic DDD stage",
    "STRATEGIC_DIFF": "Strategic Diff must be generated, validated, and approved",
    "SUBMIT": "Strategic intent is complete; submit to Plan (internal transition)",
    "TACTICAL_DDD": "next active tactical DDD stage",
    "TACTICAL_DIFF": "Tactical Diff needs independent approval before Constitution",
    "CONSTITUTION": "Constitution interview and implementation plan are required",
    "TASKS": "Implementation tasks must be generated and approved",
    "IMPLEMENT": "Approved tasks are ready for implementation",
    "TEST": "Implementation is complete; run the review/test step",
    "ACCEPT": "Test results are ready; finalize to the live graph",
}


def _reason_for(step: lifecycle_steps.StepDef) -> str:
    return _STEP_REASONS.get(step.phase, "next lifecycle step")


def _retry_context(proposal_id: str, phase: str | None) -> dict | None:
    """현재 phase 의 연속 검증 실패(재생성 루프) 상태(FR-1b/AC-2)."""
    if not phase:
        return None
    try:
        interactions = proposal_interactions.list_interactions(proposal_id)
    except Exception:
        return None
    attempts = 0
    last_violations: list = []
    for item in reversed(interactions):
        kind = item.get("kind")
        item_phase = (item.get("phase") or "").upper()
        if kind == "VALIDATOR_ERROR" and item_phase == phase.upper():
            attempts += 1
            if not last_violations:
                payload = item.get("payload") or {}
                last_violations = payload.get("violations") or []
        elif kind in ("DRAFT", "SYSTEM_NOTE") and item_phase == phase.upper():
            break
        elif kind in ("DRAFT",):
            break
    if attempts == 0:
        return None
    return {
        "attempts": attempts,
        "maxAttempts": lifecycle_steps.MAX_DRAFT_RETRIES,
        "exhausted": attempts >= lifecycle_steps.MAX_DRAFT_RETRIES,
        "lastViolations": last_violations[:8],
    }


def _build_next_step(
    proposal_id: str,
    node: dict,
    step: lifecycle_steps.StepDef,
    *,
    action: str | None = None,
    reason: str | None = None,
) -> dict:
    overrides = lifecycle_steps.rollback_targets(node)
    stale = _parse(node.get("staleArtifacts"), []) or []
    return {
        "phase": step.phase,
        "stage": step.stage,
        "action": action or step.action,
        "requiresUserApproval": step.requires_user_approval,
        "validationRef": step.validation_ref,
        "reason": reason or _reason_for(step),
        "allowedUserOverrides": overrides,
        "retryContext": _retry_context(proposal_id, step.phase),
        "staleArtifacts": stale,
        # 013-report-mcda(FR-6/7): 진행 헤더 파생 필드(서버 SSOT).
        "progressMeta": _progress_meta(node, step, action or step.action, overrides, stale),
    }


# --- 013-report-mcda: progressMeta 파생(FR-6/7, plan Step 4) -----------------


def _step_position(node: dict, step: lifecycle_steps.StepDef) -> tuple[int, int]:
    """(stepIndex 1-based, stepTotal). 모드별 동적 = 이 노드의 active_steps 길이."""
    steps = lifecycle_steps.active_steps(node)
    total = len(steps)
    for i, s in enumerate(steps):
        if s.key() == step.key():
            return i + 1, total
    # 범위 밖(pending/terminal): 진행률 하한/상한 폴백.
    return (total, total) if step.phase == "ACCEPT" else (1, max(total, 1))


def _next_step_label(node: dict, step: lifecycle_steps.StepDef) -> str | None:
    """현재 step 바로 다음 스텝의 한글 라벨(없으면 None = 마지막 단계)."""
    steps = lifecycle_steps.active_steps(node)
    for i, s in enumerate(steps):
        if s.key() == step.key():
            nxt = steps[i + 1] if i + 1 < len(steps) else None
            if nxt is None:
                return None
            label = rc.phase_label(nxt.phase)
            if nxt.stage:
                label += f" · {rc.stage_label(nxt.stage)}"
            return label
    return None


def _derive_choices(
    step: lifecycle_steps.StepDef,
    overrides: list[dict],
    stale: list,
) -> list[dict]:
    """상태 기반 결정론 choices. 순서 고정: approve→amend→skip→rollback."""
    choices: list[dict] = []
    if step.requires_user_approval and step.action in (
        lifecycle_steps.GENERATE_DRAFT,
        lifecycle_steps.AWAIT_APPROVAL,
    ):
        choices.append({"id": "approve", "label": f"{rc.EMOJI_APPROVE} 승인",
                        "hint": "현재 단계 산출물을 확정합니다", "kind": "approve"})
        choices.append({"id": "amend", "label": f"{rc.EMOJI_AMEND} 수정",
                        "hint": "피드백을 반영해 다시 생성합니다", "kind": "amend"})
    if step.stage and step.stage.upper() != "DISCOVER":
        choices.append({"id": f"skip:{step.stage}", "label": f"{rc.EMOJI_SKIP} 건너뛰기",
                        "hint": f"{rc.stage_label(step.stage)} 단계를 생략합니다", "kind": "skip"})
    stale_note = f" {rc.EMOJI_WARN} 무효화 대상 있음" if stale else ""
    for target in overrides:
        tphase = target.get("phase")
        tstage = target.get("stage")
        label_target = rc.phase_label(tphase)
        if tstage:
            label_target += f" · {rc.stage_label(tstage)}"
        choices.append({
            "id": f"rollback:{tphase}" + (f":{tstage}" if tstage else ""),
            "label": f"{rc.EMOJI_ROLLBACK} 되돌리기 → {label_target}",
            "hint": f"{label_target}(으)로 롤백{stale_note}",
            "kind": "rollback",
        })
    return choices


def _bold_label(label: str) -> str:
    """선택지 라벨 텍스트를 볼드로(이모지는 앞의 시각 액센트로 유지, C1)."""
    parts = label.split(" ", 1)
    if len(parts) == 2:
        return f"{parts[0]} **{parts[1]}**"
    return f"**{label}**"


def _progress_meta(
    node: dict,
    step: lifecycle_steps.StepDef,
    action: str,
    overrides: list[dict],
    stale: list,
) -> dict:
    step_index, step_total = _step_position(node, step)
    phase_label = rc.phase_label(step.phase)
    stage_label = rc.stage_label(step.stage) if step.stage else None
    next_label = _next_step_label(node, step)
    choices = _derive_choices(step, overrides, stale)
    is_stage = bool(step.stage)
    header = _render_progress_header(step_index, step_total, phase_label, stage_label, next_label, stale)
    footer = _render_choices_footer(step_index, step_total, phase_label, stage_label, next_label, choices, is_stage)
    return {
        "stepIndex": step_index,
        "stepTotal": step_total,
        "phaseLabel": phase_label,
        "stageLabel": stage_label,
        "nextLabel": next_label,
        "choices": choices,
        # 014-report-design: 진행(상단 얇은 한 줄) / 선택지(하단 푸터)로 분리(D1 layout).
        "headerMarkdown": header,
        "footerMarkdown": footer,
    }


def _render_progress_header(
    step_index: int,
    step_total: int,
    phase_label: str,
    stage_label: str | None,
    next_label: str | None,
    stale: list,
) -> str:
    """상단 얇은 진행 한 줄(+조건부 무효화 인용) — target-ui-progress(D2)."""
    current = f"**{phase_label}**" + (f"({stage_label})" if stage_label else "")
    next_txt = next_label if next_label else "마지막 단계"
    line = f"{rc.EMOJI_PROGRESS} **진행 {step_index}/{step_total}** · 현재: {current} → 다음: {next_txt}"
    if stale:
        line += (f"\n\n> {rc.EMOJI_WARN} **무효화 대상**: {', '.join(str(s) for s in stale)}"
                 " — 앞 단계 확정으로 재생성이 필요합니다.")
    return line


def _render_choices_footer(
    step_index: int,
    step_total: int,
    phase_label: str,
    stage_label: str | None,
    next_label: str | None,
    choices: list[dict],
    is_stage: bool,
) -> str:
    """본문 하단 푸터 — 진행 재요약 + 액션 목록형 선택지(target-ui-choices/layout, D1)."""
    if not choices:
        return ""
    current = phase_label + (f"({stage_label})" if stage_label else "")
    next_txt = next_label if next_label else "마지막 단계"
    lines = ["---", "",
             f"{rc.EMOJI_PROGRESS} **진행 {step_index}/{step_total}** · 현재: **{current}** → 다음: **{next_txt}**",
             "", "## 다음 행동 선택", ""]
    for idx, c in enumerate(choices, start=1):
        lines.append(f"{idx}. {_bold_label(c['label'])} — {c['hint']}")
    # skip(스테이지 한정)이 있을 때만 조건 인용을 붙인다(target-ui-choices: 비-스테이지 예시는 인용 없음).
    has_skip = is_stage and any(c["kind"] == "skip" for c in choices)
    has_rollback = any(c["kind"] == "rollback" for c in choices)
    if has_skip:
        note = f"{rc.EMOJI_SKIP} 건너뛰기는 스테이지 단계에서만 제공되며"
        if has_rollback:
            note += f", {rc.EMOJI_ROLLBACK} 되돌리기의 롤백 대상은 현재 단계에 따라 달라집니다"
        lines.append("")
        lines.append(f"> {note}.")
    return "\n".join(lines)


def next_step(proposal_id: str, *, mode: str | None = None, phase: str | None = None) -> dict:
    node = get_node(proposal_id)
    if node is None:
        return {"status": "not-found", "proposalId": proposal_id}

    # --- 사용자 명시 phase override (FR-8): 전이 가드 하에서만 허용 ------------
    explicit_phase = _normalize_phase(phase)
    if phase and explicit_phase is None:
        return {
            "status": "blocked",
            "nextStep": None,
            "reason": {"reason": "unknown_phase", "message": f"Unknown phase: {phase}"},
        }
    if explicit_phase:
        conflict = _explicit_phase_conflict(node, explicit_phase)
        if conflict:
            return {"status": "blocked", "nextStep": None, "reason": conflict}
        if lifecycle_steps.prior_requirement_unmet(node, explicit_phase, node.get("currentStage")):
            return {
                "status": "blocked",
                "nextStep": None,
                "reason": {
                    "reason": "invalid-transition",
                    "message": f"Cannot jump forward to {explicit_phase}; prior required steps are incomplete.",
                },
            }
        step = lifecycle_steps.step_for(mode or node.get("decompositionMode"), explicit_phase, node.get("currentStage"))
        if step is None:
            return {
                "status": "blocked",
                "nextStep": None,
                "reason": {"reason": "unknown_phase", "message": f"Phase {explicit_phase} not in step table for this mode"},
            }
        return {
            "status": "ok",
            "nextStep": _build_next_step(proposal_id, node, step, reason="explicit user-requested phase (guarded)"),
            "reason": "explicit phase accepted under transition guard",
        }

    # --- pending 우선 처리 ---------------------------------------------------
    if node.get("pendingQuestionId"):
        step = lifecycle_steps.next_incomplete_step(node) or lifecycle_steps.step_for(
            node.get("decompositionMode"), node.get("currentPhase") or "STRATEGIC_DIFF"
        )
        if step is None:
            step = lifecycle_steps.StepDef(node.get("currentPhase") or "CONSTITUTION", None, lifecycle_steps.ASK_QUESTION, True, None)
        return {
            "status": "ok",
            "nextStep": _build_next_step(
                proposal_id, node, step,
                action=lifecycle_steps.ASK_QUESTION,
                reason="a pending question must be answered before continuing",
            ),
            "reason": "pending question awaiting answer",
        }
    if node.get("pendingDraftId"):
        step = lifecycle_steps.next_incomplete_step(node) or lifecycle_steps.step_for(
            node.get("decompositionMode"), node.get("currentPhase") or "STRATEGIC_DIFF"
        )
        if step is None:
            step = lifecycle_steps.StepDef(node.get("currentPhase") or "STRATEGIC_DIFF", None, lifecycle_steps.AWAIT_APPROVAL, True, None)
        return {
            "status": "ok",
            "nextStep": _build_next_step(
                proposal_id, node, step,
                action=lifecycle_steps.AWAIT_APPROVAL,
                reason="a validated draft is awaiting user approval",
            ),
            "reason": "validated draft awaiting approval",
        }

    # --- 스텝 테이블 파생(단일 원천, FR-3/FR-4) ------------------------------
    step = lifecycle_steps.next_incomplete_step(node)
    if step is None:
        complete_step = lifecycle_steps.StepDef("ACCEPT", None, lifecycle_steps.FINALIZE, False, None)
        return {
            "status": "ok",
            "nextStep": {
                "phase": "ACCEPT", "stage": None, "action": lifecycle_steps.FINALIZE,
                "requiresUserApproval": False, "validationRef": None,
                "reason": "lifecycle complete", "allowedUserOverrides": [],
                "retryContext": None, "staleArtifacts": [],
                "progressMeta": _progress_meta(node, complete_step, lifecycle_steps.FINALIZE, [], []),
            },
            "reason": "no blocking lifecycle action detected",
        }
    return {"status": "ok", "nextStep": _build_next_step(proposal_id, node, step), "reason": _reason_for(step)}


def refresh_current_phase(proposal_id: str) -> dict | None:
    """canonical 저장/전이 후 currentPhase/currentStage 를 스텝 테이블에서 재파생(FR-5)."""
    node = get_node(proposal_id)
    if not node:
        return None
    step = lifecycle_steps.next_incomplete_step(node)
    if step is None:
        set_lifecycle(proposal_id, current_phase="ACCEPT", current_stage=None)
        return {"phase": "ACCEPT", "stage": None}
    set_lifecycle(proposal_id, current_phase=step.phase, current_stage=step.stage)
    return {"phase": step.phase, "stage": step.stage}


def auto_submit_if_ready(proposal_id: str) -> bool:
    """전략 Diff 확정 후 DRAFT→SUBMITTED 내부 자동 전이(FR-6, 042 라이프사이클)."""
    node = get_node(proposal_id)
    if not node or (node.get("status") or "DRAFT") != "DRAFT":
        return False
    if not lifecycle_steps._truthy(node.get("strategicDiff")):
        return False
    history = append_status_history(node.get("statusHistory") or "[]", "DRAFT", "SUBMITTED", "mcp-auto")
    with get_session() as session:
        session.run(
            """
            MATCH (p:Proposal {id:$id})
            SET p.status='SUBMITTED', p.statusHistory=$history, p.lifecycleStatus='ACTIVE'
            """,
            id=proposal_id,
            history=history,
        )
    SmartLogger.log(
        "INFO",
        f"proposal auto-submitted on strategic completion: {proposal_id}",
        category="proposal_lifecycle.state.updated",
        params={"proposalId": proposal_id, "transition": "DRAFT->SUBMITTED", "trigger": "strategic_diff_confirmed"},
    )
    return True


def rollback(proposal_id: str, target_phase: str, target_stage: str | None = None) -> dict:
    """사용자 명시 되돌리기(FR-7b): 대상 이후 하류 canonical 산출물을 무효화하고 stale 표식."""
    node = get_node(proposal_id)
    if not node:
        return {"status": "not-found", "proposalId": proposal_id}
    target_phase = (target_phase or "").strip().upper()
    target_stage = target_stage.strip().upper() if target_stage else None
    allowed = lifecycle_steps.rollback_targets(node)
    if not any(t["phase"] == target_phase and (t["stage"] or None) == target_stage for t in allowed):
        return {
            "status": "invalid-transition",
            "reason": "rollback_not_allowed",
            "message": f"{target_phase}/{target_stage} is not an allowed rollback target.",
            "allowedUserOverrides": allowed,
        }

    downstream = lifecycle_steps.downstream_of(node, target_phase, target_stage)
    stale: list[str] = []
    sets: list[str] = []
    params: dict[str, Any] = {"id": proposal_id}
    remove_stages: list[str] = []
    revert_to_draft = False
    for step in downstream:
        field = step.canonical_field
        if step.phase == "SUBMIT":
            revert_to_draft = True
            continue
        if not field:
            continue
        if field == "stageArtifacts":
            if step.stage:
                remove_stages.append(step.stage)
                stale.append(f"stage:{step.stage}")
            continue
        sets.append(f"p.{field}=null")
        stale.append(field)
        if field == "implementationPlan":
            sets.append("p.planStale=true")

    arts = _parse(node.get("stageArtifacts"), {}) or {}
    for s in remove_stages:
        arts.pop(s, None)
    if remove_stages:
        sets.append("p.stageArtifacts=$arts")
        params["arts"] = _json(arts)

    if revert_to_draft:
        sets.append("p.status='DRAFT'")

    sets.append("p.staleArtifacts=$stale")
    params["stale"] = _json(stale)
    sets.append("p.currentPhase=$phase")
    params["phase"] = target_phase
    sets.append("p.currentStage=$stage")
    params["stage"] = target_stage
    sets.append("p.pendingDraftId=null")
    sets.append("p.pendingQuestionId=null")
    sets.append("p.lifecycleStatus='ACTIVE'")

    with get_session() as session:
        session.run(f"MATCH (p:Proposal {{id:$id}}) SET {', '.join(sets)}", **params)

    proposal_interactions.record_interaction(
        proposal_id,
        phase=target_phase,
        kind="SYSTEM_NOTE",
        status="RESOLVED",
        payload={"event": "rollback", "target": {"phase": target_phase, "stage": target_stage}, "staleArtifacts": stale},
    )
    SmartLogger.log(
        "INFO",
        f"proposal rolled back: {proposal_id} -> {target_phase}",
        category="proposal_lifecycle.state.updated",
        params={"proposalId": proposal_id, "rollbackTarget": target_phase, "staleArtifacts": stale},
    )
    return {"status": "ok", "target": {"phase": target_phase, "stage": target_stage}, "staleArtifacts": stale}


def save_stage_plan(proposal_id: str, stage_plan: dict) -> dict:
    first_stage = _first_active_stage(stage_plan)
    with get_session() as session:
        rec = session.run(
            """
            MATCH (p:Proposal {id:$id})
            SET p.stagePlan=$stagePlan,
                p.currentStage=$currentStage,
                p.currentPhase='STRATEGIC_DDD',
                p.lifecycleStatus='ACTIVE',
                p.pendingDraftId=null
            RETURN p {.*} AS p
            """,
            id=proposal_id,
            stagePlan=_json(stage_plan),
            currentStage=first_stage,
        ).single()
    return hydrate_for_response(dict(rec["p"])) if rec else {}


def save_stage_artifact(proposal_id: str, stage: str, artifact: dict, draft_ref: str | None = None) -> str | None:
    node = get_node(proposal_id) or {}
    artifacts = _parse(node.get("stageArtifacts"), {}) or {}
    artifacts[stage] = artifact
    stage_plan = _parse(node.get("stagePlan"), None)
    next_stage_value = next_stage_after(stage_plan, stage)
    phase = "STRATEGIC_DDD" if next_stage_value in DDD_STAGE_ORDER[:3] else "TACTICAL_DDD"
    if next_stage_value is None:
        phase = "STRATEGIC_DIFF" if stage in DDD_STAGE_ORDER[:3] else "TACTICAL_DIFF"
    if draft_ref:
        proposal_interactions.confirm_draft(proposal_id, draft_ref)
    with get_session() as session:
        session.run(
            """
            MATCH (p:Proposal {id:$id})
            SET p.stageArtifacts=$artifacts,
                p.currentStage=$currentStage,
                p.currentPhase=$currentPhase,
                p.lifecycleStatus='ACTIVE',
                p.pendingDraftId=null
            """,
            id=proposal_id,
            artifacts=_json(artifacts),
            currentStage=next_stage_value,
            currentPhase=phase,
        )
    return next_stage_value


def save_diff(proposal_id: str, diff_type: str, payload: Any) -> dict:
    field = "strategicDiff" if diff_type == "strategic" else "tacticalDiff"
    with get_session() as session:
        session.run(
            f"""
            MATCH (p:Proposal {{id:$id}})
            SET p.{field}=$payload,
                p.lifecycleStatus='ACTIVE'
            """,
            id=proposal_id,
            payload=_json(payload),
        )
    # 전략 Diff 확정 시 DRAFT→SUBMITTED 내부 자동 전이(FR-6) → 이후 phase 재파생.
    if field == "strategicDiff":
        auto_submit_if_ready(proposal_id)
    refresh_current_phase(proposal_id)
    node = get_node(proposal_id)
    return hydrate_for_response(node) if node else {}


def save_tasks(proposal_id: str, tasks: list[dict]) -> dict:
    with get_session() as session:
        session.run(
            """
            MATCH (p:Proposal {id:$id})
            SET p.tasksJson=$tasks,
                p.lifecycleStatus='ACTIVE'
            """,
            id=proposal_id,
            tasks=json.dumps(tasks or [], ensure_ascii=False),
        )
    refresh_current_phase(proposal_id)
    node = get_node(proposal_id)
    return hydrate_for_response(node) if node else {}


def save_test_result(proposal_id: str, test_result: dict) -> dict:
    with get_session() as session:
        session.run(
            """
            MATCH (p:Proposal {id:$id})
            SET p.testResults=$testResults,
                p.lifecycleStatus='ACTIVE',
                p.status=CASE WHEN p.status = 'TESTING' THEN 'PENDING_ACCEPTANCE' ELSE p.status END
            """,
            id=proposal_id,
            testResults=_json(test_result),
        )
    refresh_current_phase(proposal_id)
    node = get_node(proposal_id)
    return hydrate_for_response(node) if node else {}


def update_implementation_status(proposal_id: str, status: str) -> dict:
    phase = "TEST" if status in ("DONE", "TESTING") else "IMPLEMENT"
    with get_session() as session:
        rec = session.run(
            """
            MATCH (p:Proposal {id:$id})
            SET p.implementationStatus=$implementationStatus,
                p.sandboxStatus=$implementationStatus,
                p.currentPhase=$phase,
                p.lifecycleStatus='ACTIVE'
            RETURN p {.*} AS p
            """,
            id=proposal_id,
            implementationStatus=status,
            phase=phase,
        ).single()
    return hydrate_for_response(dict(rec["p"])) if rec else {}


def mark_terminal(proposal_id: str, lifecycle_status: str, proposal_status: str | None = None) -> dict:
    sets = ["p.lifecycleStatus=$lifecycleStatus", "p.currentPhase='ACCEPT'"]
    params: dict[str, Any] = {"id": proposal_id, "lifecycleStatus": lifecycle_status}
    if proposal_status:
        sets.append("p.status=$proposalStatus")
        params["proposalStatus"] = proposal_status
    with get_session() as session:
        rec = session.run(
            f"MATCH (p:Proposal {{id:$id}}) SET {', '.join(sets)} RETURN p {{.*}} AS p",
            **params,
        ).single()
    return hydrate_for_response(dict(rec["p"])) if rec else {}


def next_stage_after(stage_plan: dict | None, stage: str) -> str | None:
    active = _active_stages(stage_plan)
    if stage not in active:
        try:
            index = DDD_STAGE_ORDER.index(stage)
        except ValueError:
            return active[0] if active else None
        for candidate in DDD_STAGE_ORDER[index + 1:]:
            if candidate in active:
                return candidate
        return None
    index = active.index(stage)
    return active[index + 1] if index + 1 < len(active) else None


def _next_stage(node: dict) -> str | None:
    plan = _parse(node.get("stagePlan"), None)
    artifacts = _parse(node.get("stageArtifacts"), {}) or {}
    for stage in _active_stages(plan):
        if stage not in artifacts:
            return stage
    return None


def _active_stages(stage_plan: dict | None) -> list[str]:
    if not stage_plan:
        return list(DDD_STAGE_ORDER)
    by_stage = {item.get("stage"): item for item in stage_plan.get("stages", [])}
    out = []
    for stage in DDD_STAGE_ORDER:
        item = by_stage.get(stage)
        if item and item.get("applies", True) and not item.get("skipped", False):
            out.append(stage)
    return out


def _first_active_stage(stage_plan: dict | None) -> str | None:
    active = _active_stages(stage_plan)
    return active[0] if active else None


def _normalize_phase(phase: str | None) -> str | None:
    if not phase:
        return None
    normalized = phase.strip().upper().replace("-", "_")
    return normalized if normalized in PHASE_ORDER else None


def _explicit_phase_conflict(node: dict, phase: str) -> dict | None:
    if node.get("pendingQuestionId") and phase not in ("START_OR_RESUME",):
        return {"reason": "pending_question", "message": "Answer the pending question before forcing another phase."}
    if node.get("pendingDraftId") and phase not in ("START_OR_RESUME",):
        return {"reason": "pending_draft", "message": "Confirm or reject the pending draft before forcing another phase."}
    if phase in ("STRATEGIC_DDD", "TACTICAL_DDD") and not node.get("stagePlan"):
        return {"reason": "stage_plan_required", "message": "Detailed DDD phase requires a confirmed stagePlan."}
    return None
