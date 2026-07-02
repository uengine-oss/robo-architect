from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from api.features.proposal_lifecycle.proposal_contracts import DDD_STAGE_ORDER
from api.features.proposal_lifecycle.services import proposal_interactions
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


def next_step(proposal_id: str, *, mode: str | None = None, phase: str | None = None) -> dict:
    node = get_node(proposal_id)
    if node is None:
        return {"status": "not-found", "proposalId": proposal_id}

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
        return {
            "status": "ok",
            "nextStep": {"phase": explicit_phase, "stage": node.get("currentStage")},
            "reason": "explicit phase takes precedence over persisted state",
        }

    if node.get("pendingQuestionId"):
        return {
            "status": "ok",
            "nextStep": {"phase": node.get("currentPhase") or "START_OR_RESUME", "action": "answer_question"},
            "reason": "pending question must be answered before continuing",
        }
    if node.get("pendingDraftId"):
        return {
            "status": "ok",
            "nextStep": {"phase": node.get("currentPhase") or "START_OR_RESUME", "action": "confirm_or_reject_draft"},
            "reason": "pending draft must be confirmed or rejected before final artifact promotion",
        }

    decomposition_mode = mode or node.get("decompositionMode") or "SIMPLIFIED"
    if decomposition_mode in ("DETAILED", "DETAILED_DDD"):
        stage = _next_stage(node)
        if not node.get("stagePlan"):
            return {"status": "ok", "nextStep": {"phase": "SCOPE", "stage": None}, "reason": "Detailed DDD requires stagePlan"}
        if stage:
            phase_name = "STRATEGIC_DDD" if stage in DDD_STAGE_ORDER[:3] else "TACTICAL_DDD"
            return {"status": "ok", "nextStep": {"phase": phase_name, "stage": stage}, "reason": "next active DDD stage"}
        if not node.get("strategicDiff"):
            return {"status": "ok", "nextStep": {"phase": "STRATEGIC_DIFF"}, "reason": "DDD strategic artifacts need consolidation"}
        if not node.get("tacticalDiff"):
            return {"status": "ok", "nextStep": {"phase": "TACTICAL_DIFF"}, "reason": "DDD tactical artifacts need consolidation"}

    if not node.get("strategicDiff"):
        return {"status": "ok", "nextStep": {"phase": "STRATEGIC_DIFF"}, "reason": "Strategic Diff is missing"}
    if node.get("status") == "DRAFT":
        return {"status": "ok", "nextStep": {"phase": "SUBMIT"}, "reason": "Intent is ready to submit to Plan"}
    if not node.get("implementationPlan"):
        return {"status": "ok", "nextStep": {"phase": "CONSTITUTION"}, "reason": "Plan requires Constitution and implementation plan"}
    if not node.get("tasksJson"):
        return {"status": "ok", "nextStep": {"phase": "TASKS"}, "reason": "Implementation tasks are missing"}
    if node.get("status") == "SUBMITTED":
        return {"status": "ok", "nextStep": {"phase": "IMPLEMENT"}, "reason": "Proposal is ready for implementation"}
    if node.get("status") == "TESTING":
        return {"status": "ok", "nextStep": {"phase": "TEST"}, "reason": "Implementation completed; tests are pending"}
    if node.get("status") == "PENDING_ACCEPTANCE":
        return {"status": "ok", "nextStep": {"phase": "ACCEPT"}, "reason": "Test results are ready for acceptance"}
    return {"status": "ok", "nextStep": {"phase": "START_OR_RESUME"}, "reason": "No blocking lifecycle action detected"}


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
    phase = "TACTICAL_DIFF" if field == "strategicDiff" else "CONSTITUTION"
    with get_session() as session:
        rec = session.run(
            f"""
            MATCH (p:Proposal {{id:$id}})
            SET p.{field}=$payload,
                p.currentPhase=$phase,
                p.lifecycleStatus='ACTIVE'
            RETURN p {{.*}} AS p
            """,
            id=proposal_id,
            payload=_json(payload),
            phase=phase,
        ).single()
    return hydrate_for_response(dict(rec["p"])) if rec else {}


def save_tasks(proposal_id: str, tasks: list[dict]) -> dict:
    with get_session() as session:
        rec = session.run(
            """
            MATCH (p:Proposal {id:$id})
            SET p.tasksJson=$tasks,
                p.currentPhase='IMPLEMENT',
                p.lifecycleStatus='ACTIVE'
            RETURN p {.*} AS p
            """,
            id=proposal_id,
            tasks=json.dumps(tasks or [], ensure_ascii=False),
        ).single()
    return hydrate_for_response(dict(rec["p"])) if rec else {}


def save_test_result(proposal_id: str, test_result: dict) -> dict:
    with get_session() as session:
        rec = session.run(
            """
            MATCH (p:Proposal {id:$id})
            SET p.testResults=$testResults,
                p.currentPhase='ACCEPT',
                p.lifecycleStatus='ACTIVE',
                p.status=CASE WHEN p.status = 'TESTING' THEN 'PENDING_ACCEPTANCE' ELSE p.status END
            RETURN p {.*} AS p
            """,
            id=proposal_id,
            testResults=_json(test_result),
        ).single()
    return hydrate_for_response(dict(rec["p"])) if rec else {}


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
