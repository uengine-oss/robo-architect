"""MCP server for Proposal lifecycle state and run-state operations."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from pydantic import ValidationError

from api.features.proposal_lifecycle.proposal_contracts import (
    DDD_STAGE_ORDER,
    DecompositionMode,
    ProposalResponse,
    TestRunResult,
    append_status_history,
    extract_title_from_prompt,
)
from api.features.proposal_lifecycle.services import (
    lifecycle_steps,
    proposal_interactions,
    proposal_state_service,
    report_contract_data,
    report_render,
    staged_runner,
)
from api.features.proposal_lifecycle.services.proposal_ai_validation import (
    declared_bc_ids,
    validate_implementation_plan,
    validate_stage_artifact,
    validate_strategic_output,
    validate_tactical_output,
    violation_summary,
)
from api.features.proposal_lifecycle.services.proposal_id_generator import next_proposal_id
from api.platform.neo4j import get_session
from api.platform.observability.smart_logger import SmartLogger


def build_mcp_server() -> Any | None:
    try:
        from mcp.server.fastmcp import FastMCP  # type: ignore
    except ImportError as e:
        SmartLogger.log(
            "WARN",
            "mcp SDK not importable — /mcp/proposals transport disabled.",
            category="proposal_lifecycle.mcp.sdk_missing",
            params={"error": str(e)},
        )
        return None

    server = FastMCP("robo-proposal", streamable_http_path="/")

    @server.tool(name="proposal_create", description="Create a new Proposal lifecycle node.")
    def proposal_create(
        originalPrompt: str,  # noqa: N803
        title: str | None = None,
        mode: str = "SIMPLIFIED",
        author: str = "mcp",
    ) -> dict[str, Any]:
        proposal_id = next_proposal_id()
        created_at = datetime.now(timezone.utc)
        normalized_mode = _normalize_mode(mode)
        auto_title = title or extract_title_from_prompt(originalPrompt)
        with get_session() as session:
            session.run(
                """
                CREATE (p:Proposal {
                  id:$id,
                  title:$title,
                  originalPrompt:$originalPrompt,
                  author:$author,
                  createdAt: datetime($createdAt),
                  status:'DRAFT',
                  lifecycleStatus:'ACTIVE',
                  currentPhase:'START_OR_RESUME',
                  statusHistory:'[]',
                  clarificationLog:'[]',
                  decompositionMode:$decompositionMode,
                  pendingQuestionId:null,
                  pendingDraftId:null,
                  resumeToken:$resumeToken,
                  skillVersion:$skillVersion,
                  schemaVersion:$schemaVersion
                })
                """,
                id=proposal_id,
                title=auto_title,
                originalPrompt=originalPrompt,
                author=author,
                createdAt=created_at.isoformat(),
                decompositionMode=normalized_mode,
                resumeToken=f"{proposal_id}:start",
                skillVersion=proposal_interactions.SKILL_VERSION,
                schemaVersion=proposal_interactions.SCHEMA_VERSION,
            )
        _log("proposal_create", proposal_id)
        return _state(proposal_id)

    @server.tool(name="proposal_get", description="Return full Proposal lifecycle state.")
    def proposal_get(proposalId: str) -> dict[str, Any]:  # noqa: N803
        result = _state(proposalId)
        if result.get("status") != "not-found":
            result["reportMarkdown"] = _overview_report(proposalId)
        return result

    @server.tool(name="proposal_list", description="List resumable Proposal summaries.")
    def proposal_list(status: str | None = None, limit: int = 50) -> dict[str, Any]:
        where = "WHERE p.status = $status" if status else ""
        params: dict[str, Any] = {"limit": limit}
        if status:
            params["status"] = status
        with get_session() as session:
            rows = session.run(
                f"""
                MATCH (p:Proposal)
                {where}
                RETURN p {{.*}} AS p
                ORDER BY p.createdAt DESC
                LIMIT $limit
                """,
                **params,
            )
            proposals = [_state_from_node(r["p"], include_interactions=False) for r in rows]
        return {"proposals": proposals, "count": len(proposals)}

    @server.tool(name="proposal_next_step", description="Calculate next safe Proposal lifecycle step.")
    def proposal_next_step(
        proposalId: str,  # noqa: N803
        mode: str | None = None,
        phase: str | None = None,
    ) -> dict[str, Any]:
        result = proposal_state_service.next_step(proposalId, mode=mode, phase=phase)
        _log("proposal_next_step", proposalId, result=result.get("status"))
        return result

    @server.tool(name="proposal_save_stage_plan", description="Persist a confirmed Detailed DDD stagePlan.")
    def proposal_save_stage_plan(proposalId: str, stagePlan: dict) -> dict[str, Any]:  # noqa: N803
        err = staged_runner.validate_stage_plan(stagePlan.get("stages", []))
        if err:
            return {"status": "invalid", "error": err}
        proposal_state_service.save_stage_plan(proposalId, stagePlan)
        proposal_interactions.record_interaction(
            proposalId,
            phase="SCOPE",
            kind="SYSTEM_NOTE",
            status="RESOLVED",
            payload={"event": "stagePlanSaved", "stagePlan": stagePlan},
        )
        _log("proposal_save_stage_plan", proposalId)
        return _state(proposalId)

    @server.tool(name="proposal_skip_stage", description="Mark a Detailed DDD stage as skipped.")
    def proposal_skip_stage(proposalId: str, stage: str, reason: str | None = None) -> dict[str, Any]:  # noqa: N803
        if stage.upper() == "DISCOVER":
            return {
                "status": "invalid",
                "error": {
                    "reason": "discover_not_skippable",
                    "message": "Discover stage cannot be fully skipped for behavior-changing Proposals.",
                },
            }
        next_stage = staged_runner.mark_stage_skipped(proposalId, stage.upper())
        proposal_interactions.record_interaction(
            proposalId,
            phase="SCOPE",
            kind="SYSTEM_NOTE",
            status="RESOLVED",
            payload={"event": "stageSkipped", "stage": stage.upper(), "reason": reason, "nextStage": next_stage},
        )
        _log("proposal_skip_stage", proposalId, stage=stage.upper())
        return {"status": "ok", "nextStep": proposal_state_service.next_step(proposalId).get("nextStep"), "proposal": _state(proposalId)}

    @server.tool(name="proposal_save_draft", description="Validate then save a pending draft artifact. Invalid drafts are rejected (not stored).")
    def proposal_save_draft(proposalId: str, phase: str, artifact: dict) -> dict[str, Any]:  # noqa: N803
        normalized_phase = phase.upper()
        # 015-report-issue: DDD 스테이지 초안이 상위 phase(STRATEGIC_DDD/TACTICAL_DDD)로 들어오면
        # 봉투 키로 스테이지 이름을 복원해 정규화한다. 이래야 검증·저장·승격·렌더가 일관되게
        # 스테이지 기준으로 동작(상위 phase 면 검증/렌더가 조용히 건너뛰어짐).
        inferred_stage = report_contract_data.stage_from_envelope(artifact)
        if inferred_stage and normalized_phase not in set(DDD_STAGE_ORDER):
            normalized_phase = inferred_stage
        node = proposal_state_service.get_node(proposalId)
        if node is None:
            return {"status": "not-found", "proposalId": proposalId}
        # FR-7: 하드 전이 가드 — 직전 필수 스텝 미완료면 초안 생성 차단.
        stage_hint = normalized_phase if normalized_phase in set(DDD_STAGE_ORDER) else node.get("currentStage")
        if lifecycle_steps.prior_requirement_unmet(node, _phase_of(normalized_phase), stage_hint):
            return {
                "status": "invalid-transition",
                "reason": "prior_requirement_unmet",
                "message": f"Prior required steps for {normalized_phase} are incomplete; cannot draft yet.",
            }
        # FR-1 (P1): 저장 **전** 검증. 실패 시 초안 미저장 + 위반 반환 → 스킬 재생성 루프.
        validation = _validate_artifact_for_phase(proposalId, normalized_phase, artifact)
        if validation:
            proposal_interactions.record_interaction(
                proposalId,
                phase=normalized_phase or "UNKNOWN",
                kind="VALIDATOR_ERROR",
                status="RESOLVED",
                payload=validation,
            )
            return _with_report(validation, "VIOLATIONS", validation)
        draft = proposal_interactions.save_draft(proposalId, normalized_phase, artifact)
        _log("proposal_save_draft", proposalId, draftId=draft["id"])
        return _with_report(
            {"status": "ok", "draftRef": draft["id"], "draft": draft},
            normalized_phase, artifact,
        )

    @server.tool(name="proposal_confirm_draft", description="Confirm an already-validated draft and promote it to a canonical artifact (promotion only).")
    def proposal_confirm_draft(proposalId: str, draftRef: str) -> dict[str, Any]:  # noqa: N803
        draft = proposal_interactions.get_interaction(draftRef)
        if not draft:
            return {"status": "not-found", "draftRef": draftRef}
        payload = draft.get("payload") or {}
        artifact = payload.get("artifact") if isinstance(payload, dict) else None
        phase = (draft.get("phase") or "").upper()
        # 015-report-issue: 방어적 정규화 — 상위 phase 로 저장된 스테이지 초안도 승격·렌더가
        # 스테이지 기준으로 동작하도록 봉투 키에서 스테이지를 복원.
        inferred_stage = report_contract_data.stage_from_envelope(artifact)
        if inferred_stage and phase not in set(DDD_STAGE_ORDER):
            phase = inferred_stage
        if isinstance(artifact, dict):
            # FR-2: 초안은 save_draft 에서 이미 검증됨 → 여기서는 승격만.
            # 방어적 전이 가드만 유지(직전 필수 스텝 미완료 시 승격 거부).
            node = proposal_state_service.get_node(proposalId) or {}
            stage_hint = phase if phase in set(DDD_STAGE_ORDER) else node.get("currentStage")
            if lifecycle_steps.prior_requirement_unmet(node, _phase_of(phase), stage_hint):
                return {
                    "status": "invalid-transition",
                    "reason": "prior_requirement_unmet",
                    "message": f"Prior required steps for {phase} are incomplete; cannot promote.",
                }
            draft = proposal_interactions.confirm_draft(proposalId, draftRef)
            _promote_confirmed(proposalId, phase, artifact)
        # 확정 후 다음 phase 는 스텝 테이블에서 파생(FR-5) — _phase_after_confirm 제거.
        proposal_state_service.set_lifecycle(proposalId, lifecycle_status="ACTIVE", clear_pending_draft=True)
        proposal_state_service.refresh_current_phase(proposalId)
        _log("proposal_confirm_draft", proposalId, draftId=draftRef)
        return _with_report(
            {"status": "ok", "confirmed": draft, "proposal": _state(proposalId)},
            phase, artifact if isinstance(artifact, dict) else {},
        )

    @server.tool(name="proposal_reject_draft", description="Reject a pending draft artifact.")
    def proposal_reject_draft(proposalId: str, draftRef: str, reason: str | None = None) -> dict[str, Any]:  # noqa: N803
        rejected = proposal_interactions.reject_draft(proposalId, draftRef, reason)
        _log("proposal_reject_draft", proposalId, draftId=draftRef)
        return {"status": "ok" if rejected else "not-found", "draft": rejected}

    @server.tool(name="proposal_save_stage_artifact", description="Validate and save a confirmed DDD stage artifact.")
    def proposal_save_stage_artifact(proposalId: str, stage: str, artifact: dict) -> dict[str, Any]:  # noqa: N803
        normalized_stage = stage.upper()
        if staged_runner.prior_stage_incomplete(proposalId, normalized_stage):
            return {
                "status": "invalid-transition",
                "reason": "prior_stage_incomplete",
                "message": "Previous active stage artifact is required before saving this stage.",
            }
        validation = validate_stage_artifact(normalized_stage, artifact)
        if validation.violations:
            proposal_interactions.record_interaction(
                proposalId,
                phase=normalized_stage,
                kind="VALIDATOR_ERROR",
                status="RESOLVED",
                payload={"violations": validation.violations},
            )
            err = _validation_error("stage_artifact_invalid", validation.violations)
            return _with_report(err, "VIOLATIONS", err)
        next_stage = staged_runner.save_stage_artifact(proposalId, normalized_stage, artifact)
        _log("proposal_save_stage_artifact", proposalId, stage=normalized_stage)
        return _with_report(
            {"status": "ok", "nextStage": next_stage, "proposal": _state(proposalId)},
            normalized_stage, artifact,
        )

    @server.tool(name="proposal_save_diff", description="Validate and save strategic or tactical diff (guarded).")
    def proposal_save_diff(proposalId: str, diffType: str, payload: Any) -> dict[str, Any]:  # noqa: N803
        node = proposal_state_service.get_node(proposalId)
        if node is None:
            return {"status": "not-found", "proposalId": proposalId}
        target_phase = "TACTICAL_DIFF" if diffType.lower() == "tactical" else "STRATEGIC_DIFF"
        # FR-7: 하드 전이 가드 — 전략 Diff 없이 전술 Diff 저장 등 앞으로 건너뛰기 차단.
        if lifecycle_steps.prior_requirement_unmet(node, target_phase, None):
            return {
                "status": "invalid-transition",
                "reason": "prior_requirement_unmet",
                "message": f"Prior required steps for {target_phase} are incomplete.",
            }
        known_bc = _known_bc_ids(proposalId) if diffType.lower() == "tactical" else _live_bc_ids()
        validation = _validate_diff(diffType, payload, known_bc_ids=known_bc)
        if validation:
            proposal_interactions.record_interaction(
                proposalId,
                phase="TACTICAL_DIFF" if diffType == "tactical" else "STRATEGIC_DIFF",
                kind="VALIDATOR_ERROR",
                status="RESOLVED",
                payload=validation,
            )
            return _with_report(validation, "VIOLATIONS", validation)
        proposal_state_service.save_diff(proposalId, diffType.lower(), payload)
        _log("proposal_save_diff", proposalId, diffType=diffType)
        if diffType.lower() == "tactical":
            report_phase, report_artifact = "TACTICAL_DIFF", {"tacticalDiff": payload}
        else:
            report_phase, report_artifact = "STRATEGIC_DIFF", {"strategicDiff": payload}
        return _with_report(
            {"status": "ok", "proposal": _state(proposalId)},
            report_phase, report_artifact,
        )

    @server.tool(name="proposal_record_question", description="Store a single pending HITL question.")
    def proposal_record_question(
        proposalId: str,  # noqa: N803
        phase: str,
        question: str,
        options: list[Any] | None = None,
    ) -> dict[str, Any]:
        interaction = proposal_interactions.record_question(proposalId, phase.upper(), question, options or [])
        _log("proposal_record_question", proposalId, questionId=interaction["id"])
        return _with_report(
            {"status": "ok", "questionId": interaction["id"], "question": interaction},
            "QUESTION", {"question": question, "options": options or []},
        )

    @server.tool(name="proposal_answer_question", description="Store a user's answer and resume the Proposal.")
    def proposal_answer_question(proposalId: str, questionId: str, answer: Any) -> dict[str, Any]:  # noqa: N803
        try:
            result = proposal_interactions.answer_question(proposalId, questionId, answer)
        except ValueError as e:
            return {"status": "not-found", "message": str(e)}
        _log("proposal_answer_question", proposalId, questionId=questionId)
        return {"status": "ok", **result, "nextStep": proposal_state_service.next_step(proposalId).get("nextStep")}

    @server.tool(name="proposal_resume", description="Restore pending question/draft and recent interaction window.")
    def proposal_resume(proposalId: str) -> dict[str, Any]:  # noqa: N803
        try:
            context = proposal_interactions.resume_context(proposalId)
        except ValueError as e:
            return {"status": "not-found", "message": str(e)}
        # resume 는 확정 산출물 개요를 렌더(FR-3, S2 재열람).
        return {
            "status": "ok",
            "resumeContext": context,
            "nextStep": proposal_state_service.next_step(proposalId).get("nextStep"),
            "reportMarkdown": _overview_report(proposalId),
        }

    @server.tool(name="proposal_generate_tasks", description="Persist generated implementation tasks.")
    def proposal_generate_tasks(proposalId: str, tasks: list[dict]) -> dict[str, Any]:  # noqa: N803
        # 015-issue3: 헌장/구현계획 게이트를 우회해 태스크를 저장하지 못하도록 전이 가드(FR-7).
        node = proposal_state_service.get_node(proposalId)
        if node is None:
            return {"status": "not-found", "proposalId": proposalId}
        if lifecycle_steps.prior_requirement_unmet(node, "TASKS", None):
            return {
                "status": "invalid-transition",
                "reason": "prior_requirement_unmet",
                "message": "Prior required steps for TASKS are incomplete (Constitution node and implementation plan are required).",
            }
        proposal_state_service.save_tasks(proposalId, tasks)
        proposal_interactions.record_interaction(
            proposalId,
            phase="TASKS",
            kind="SYSTEM_NOTE",
            status="RESOLVED",
            payload={"event": "tasksSaved", "count": len(tasks or [])},
        )
        _log("proposal_generate_tasks", proposalId, count=len(tasks or []))
        return _with_report(
            {"status": "ok", "proposal": _state(proposalId)},
            "TASKS", {"tasks": tasks or []},
        )

    @server.tool(name="proposal_update_implementation_status", description="Update implementation/sandbox status.")
    def proposal_update_implementation_status(proposalId: str, status: str) -> dict[str, Any]:  # noqa: N803
        # 015: IMPLEMENT 완료 플래그를 앞 단계(태스크 확정) 없이 선점하지 못하게 가드.
        node = proposal_state_service.get_node(proposalId)
        if node is None:
            return {"status": "not-found", "proposalId": proposalId}
        if lifecycle_steps.prior_requirement_unmet(node, "IMPLEMENT", None):
            return {
                "status": "invalid-transition",
                "reason": "prior_requirement_unmet",
                "message": "Prior required steps for IMPLEMENT are incomplete (approved tasks are required).",
            }
        proposal = proposal_state_service.update_implementation_status(proposalId, status.upper())
        _log("proposal_update_implementation_status", proposalId, status=status.upper())
        return {"status": "ok", "proposal": _state_from_node(proposal)}

    @server.tool(name="proposal_save_test_result", description="Validate and save TestRunResult.")
    def proposal_save_test_result(proposalId: str, testRunResult: dict) -> dict[str, Any]:  # noqa: N803
        # 015: TEST 결과를 구현 완료(IMPLEMENT) 전에 선점 저장하지 못하게 가드.
        node = proposal_state_service.get_node(proposalId)
        if node is None:
            return {"status": "not-found", "proposalId": proposalId}
        if lifecycle_steps.prior_requirement_unmet(node, "TEST", None):
            return {
                "status": "invalid-transition",
                "reason": "prior_requirement_unmet",
                "message": "Prior required steps for TEST are incomplete (implementation must be finished first).",
            }
        try:
            result = TestRunResult(**{**testRunResult, "proposalId": proposalId}).model_dump(mode="json")
        except ValidationError as e:
            err = {"status": "invalid", "violations": e.errors()}
            return _with_report(err, "VIOLATIONS", err)
        proposal_state_service.save_test_result(proposalId, result)
        _log("proposal_save_test_result", proposalId)
        return _with_report(
            {"status": "ok", "proposal": _state(proposalId)},
            "TEST", result,
        )

    @server.tool(name="proposal_submit", description="Transition Proposal to submitted Plan state.")
    def proposal_submit(proposalId: str) -> dict[str, Any]:  # noqa: N803
        node = proposal_state_service.get_node(proposalId)
        if not node:
            return {"status": "not-found", "proposalId": proposalId}
        if node.get("status") != "DRAFT":
            return {"status": "invalid-transition", "message": f"current status is {node.get('status')}"}
        history = append_status_history(node.get("statusHistory") or "[]", "DRAFT", "SUBMITTED", "mcp")
        with get_session() as session:
            session.run(
                """
                MATCH (p:Proposal {id:$id})
                SET p.status='SUBMITTED',
                    p.statusHistory=$history,
                    p.lifecycleStatus='ACTIVE'
                """,
                id=proposalId,
                history=history,
            )
        # submit 후 다음 phase(SIMPLIFIED=TACTICAL_DIFF, DETAILED=다음 전술 스테이지)는 테이블 파생.
        proposal_state_service.refresh_current_phase(proposalId)
        _log("proposal_submit", proposalId)
        return {"status": "ok", "proposal": _state(proposalId)}

    @server.tool(
        name="proposal_prepare_sandbox",
        description=(
            "Create the Proposal git worktree inside the target project "
            "(<projectRoot>/.sandbox/proposal/<PRO-NNN>, branch proposal/<PRO-NNN>) and return its path. "
            "Call this at the start of the IMPLEMENT phase — never ask the user where to put the worktree."
        ),
    )
    def proposal_prepare_sandbox(proposalId: str, projectRoot: str) -> dict[str, Any]:  # noqa: N803
        """015-issue4: 워크트리 위치는 서버가 정한다(질문 금지). 구현은 이 경로 안에서만."""
        node = proposal_state_service.get_node(proposalId)
        if node is None:
            return {"status": "not-found", "proposalId": proposalId}
        if lifecycle_steps.prior_requirement_unmet(node, "IMPLEMENT", None):
            return {
                "status": "invalid-transition",
                "reason": "prior_requirement_unmet",
                "message": "Approved tasks are required before implementation can start.",
            }
        from api.features.proposal_lifecycle.services.sandbox_manager import SandboxManager

        manager = SandboxManager()
        try:
            root = manager.resolve_root(projectRoot)
            worktree = manager.create_worktree(proposalId, str(root), allow_init=True)
        except Exception as e:
            return {"status": "error", "reason": "sandbox_failed", "message": str(e)}

        with get_session() as session:
            session.run(
                """
                MATCH (p:Proposal {id:$id})
                SET p.projectRoot=$root, p.worktreePath=$worktree, p.sandboxBranch=$branch
                """,
                id=proposalId, root=str(root), worktree=str(worktree),
                branch=manager.branch_name(proposalId),
            )
        proposal_state_service.update_implementation_status(proposalId, "IN_PROGRESS")
        _log("proposal_prepare_sandbox", proposalId, worktree=str(worktree))
        return {
            "status": "ok",
            "projectRoot": str(root),
            "worktreePath": str(worktree),
            "branch": manager.branch_name(proposalId),
            "proposal": _state(proposalId),
        }

    @server.tool(
        name="proposal_accept",
        description=(
            "Finalize the Proposal: merge the worktree branch and apply the strategic + tactical Diff "
            "to the live Neo4j graph (Aggregate/Command/Event/ValueObject/Enumeration/... nodes), then ACCEPTED."
        ),
    )
    def proposal_accept(proposalId: str) -> dict[str, Any]:  # noqa: N803
        """015-issue6: Accept 는 '상태만 바꾸기'가 아니라 **라이브 그래프 반영**이다."""
        node = proposal_state_service.get_node(proposalId)
        if node is None:
            return {"status": "not-found", "proposalId": proposalId}
        if lifecycle_steps.prior_requirement_unmet(node, "ACCEPT", None):
            return {
                "status": "invalid-transition",
                "reason": "prior_requirement_unmet",
                "message": "Implementation and test results are required before accepting.",
            }
        from api.features.proposal_lifecycle.services import dual_merge

        try:
            applied = dual_merge.execute_dual_merge_sync(proposalId, "mcp", "accepted via proposal MCP")
        except dual_merge.DualMergeFailed as e:
            SmartLogger.log(
                "ERROR",
                f"proposal accept failed at {e.step}: {proposalId}",
                category="proposal_lifecycle.mcp.accept_failed",
                params={"proposalId": proposalId, "step": e.step, "detail": e.detail},
            )
            return {
                "status": "failed",
                "reason": f"dual_merge_{e.step}",
                "message": e.detail,
                "proposal": _state(proposalId),
            }
        _log("proposal_accept", proposalId, **{k: v for k, v in applied.items() if k != "liveCounts"})
        return {
            "status": "ok",
            "applied": applied,
            "liveGraph": applied.get("liveCounts", {}),
            "proposal": _state(proposalId),
        }

    @server.tool(
        name="proposal_get_constitution",
        description="Return the target project's root Constitution node (exists / fields / raw).",
    )
    def proposal_get_constitution() -> dict[str, Any]:
        from api.features.constitution.services import constitution_store as store

        constitution = store.get_project_constitution()
        return {"status": "ok", "exists": bool(constitution), "constitution": constitution}

    @server.tool(name="proposal_rollback", description="User-explicit rollback to an earlier completed step; invalidates downstream artifacts (FR-7b).")
    def proposal_rollback(proposalId: str, targetPhase: str, targetStage: str | None = None) -> dict[str, Any]:  # noqa: N803
        result = proposal_state_service.rollback(proposalId, targetPhase, targetStage)
        _log("proposal_rollback", proposalId, target=targetPhase, status=result.get("status"))
        if result.get("status") != "ok":
            return result
        return {"status": "ok", "rollback": result, "proposal": _state(proposalId)}

    SmartLogger.log(
        "INFO",
        "Proposal MCP server constructed.",
        category="proposal_lifecycle.mcp.constructed",
        params={"tools": [
            "proposal_create", "proposal_get", "proposal_list", "proposal_next_step",
            "proposal_save_stage_plan", "proposal_skip_stage", "proposal_save_draft",
            "proposal_confirm_draft", "proposal_reject_draft", "proposal_save_stage_artifact",
            "proposal_save_diff", "proposal_record_question", "proposal_answer_question",
            "proposal_resume", "proposal_generate_tasks", "proposal_update_implementation_status",
            "proposal_save_test_result", "proposal_submit", "proposal_prepare_sandbox",
            "proposal_accept", "proposal_get_constitution", "proposal_rollback",
        ]},
    )
    return server


def _normalize_mode(mode: str) -> str:
    normalized = (mode or "SIMPLIFIED").strip().upper()
    if normalized == "DETAILED":
        normalized = "DETAILED_DDD"
    try:
        return DecompositionMode(normalized).value
    except Exception:
        return DecompositionMode.SIMPLIFIED.value


def _state(proposal_id: str) -> dict[str, Any]:
    node = proposal_state_service.get_node(proposal_id)
    if node is None:
        return {"status": "not-found", "proposalId": proposal_id}
    return _state_from_node(node)


def _state_from_node(node: dict, *, include_interactions: bool = True) -> dict[str, Any]:
    hydrated = proposal_state_service.hydrate_for_response(node) if include_interactions else dict(node)
    try:
        return ProposalResponse.from_neo4j(hydrated, []).model_dump(mode="json")
    except Exception:
        return _json_safe(hydrated)


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: _json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_json_safe(v) for v in value]
    try:
        json.dumps(value)
        return value
    except TypeError:
        return str(value)


def _live_bc_ids() -> set[str]:
    try:
        return proposal_state_service.live_bounded_context_ids()
    except Exception:  # 그래프 조회 실패 시 검증을 막지 않고 관대 모드로.
        return set()


def _known_bc_ids(proposal_id: str) -> set[str]:
    """015-issue6: tacticalDiff 의 boundedContextId 가 해소 가능한 BC 집합.

    확정된 전략 Diff 의 Epic tempId(Epic ≡ BoundedContext) + 실재 BoundedContext.
    """
    node = proposal_state_service.get_node(proposal_id) or {}
    strategic = _parse_stored(node.get("strategicDiff")) or {}
    return declared_bc_ids(strategic) | _live_bc_ids()


def _validate_diff(diff_type: str, payload: Any, *, known_bc_ids: set[str] | None = None) -> dict | None:
    normalized = diff_type.lower()
    if normalized == "strategic":
        result = validate_strategic_output(
            {"action": "done", "strategicDiff": payload},
            allow_clarify=False,
            known_bc_ids=known_bc_ids,
        )
        if result.valid:
            return None
        return _validation_error("strategic_contract_invalid", result.violations)
    if normalized == "tactical":
        result = validate_tactical_output({"tacticalDiff": payload}, known_bc_ids=known_bc_ids)
        if result.valid:
            return None
        return _validation_error("tactical_contract_invalid", result.violations)
    return {"status": "invalid", "reason": "unknown_diff_type", "message": "diffType must be strategic or tactical"}


# --- 015-issue3: 프로젝트 헌장(Constitution 노드) 게이트 ----------------------

_CONSTITUTION_ENUMS = {
    "architectureStyle": {"MONOLITH", "MICROSERVICES"},
    "repoStrategy": {"MONOREPO", "REPO_PER_SERVICE"},
}


def _constitution_interview_done(proposal_id: str) -> bool:
    """헌장 인터뷰가 실제로 수행됐는지(응답 완료된 질문이 1건 이상) 확인."""
    try:
        interactions = proposal_interactions.list_interactions(proposal_id)
    except Exception:
        return False
    return any(
        item.get("kind") == "QUESTION"
        and (item.get("phase") or "").upper() == "PROJECT_CONSTITUTION"
        and (item.get("status") or "").upper() == "RESOLVED"
        for item in interactions
    )


def _validate_project_constitution(proposal_id: str, artifact: dict) -> dict | None:
    con = artifact.get("constitution")
    if not isinstance(con, dict):
        return {
            "status": "invalid",
            "reason": "project_constitution_invalid",
            "message": "PROJECT_CONSTITUTION draft must be {\"constitution\": {\"raw\": ..., \"fields\": {...}}}.",
        }
    violations: list[dict] = []
    raw = str(con.get("raw") or "").strip()
    if len(raw) < 40:
        violations.append({
            "path": "constitution.raw",
            "code": "required",
            "message": "constitution.raw must be the Constitution document body (markdown, non-trivial).",
        })
    fields = con.get("fields") if isinstance(con.get("fields"), dict) else {}
    for key in ("designPrinciples", "techStack"):
        if not str(fields.get(key) or "").strip():
            violations.append({"path": f"constitution.fields.{key}", "code": "required",
                               "message": f"{key} is required (decide it in the interview)."})
    for key, allowed in _CONSTITUTION_ENUMS.items():
        value = str(fields.get(key) or "").strip().upper()
        if value not in allowed:
            violations.append({"path": f"constitution.fields.{key}", "code": "invalid",
                               "message": f"{key} must be one of {sorted(allowed)}."})
    if not _constitution_interview_done(proposal_id):
        violations.append({
            "path": "constitution.interview",
            "code": "interview_required",
            "message": (
                "Interview the architect first: ask the Constitution questions with "
                "proposal_record_question(phase='PROJECT_CONSTITUTION') and record the answers with "
                "proposal_answer_question before saving the Constitution."
            ),
        })
    if violations:
        return _validation_error("project_constitution_invalid", violations)
    return None


def _validate_artifact_for_phase(proposal_id: str, phase: str, artifact: dict) -> dict | None:
    if phase in set(DDD_STAGE_ORDER):
        if staged_runner.prior_stage_incomplete(proposal_id, phase):
            return {
                "status": "invalid-transition",
                "reason": "prior_stage_incomplete",
                "message": "Previous active stage artifact is required before confirming this draft.",
            }
        result = validate_stage_artifact(phase, artifact)
        if result.violations:
            return _validation_error("stage_artifact_invalid", result.violations)
        return None
    if phase == "STRATEGIC_DIFF":
        return _validate_diff("strategic", artifact.get("strategicDiff", artifact),
                              known_bc_ids=_live_bc_ids())
    if phase == "TACTICAL_DIFF":
        return _validate_diff("tactical", artifact.get("tacticalDiff", artifact),
                              known_bc_ids=_known_bc_ids(proposal_id))
    if phase == "PROJECT_CONSTITUTION":
        return _validate_project_constitution(proposal_id, artifact)
    if phase == "CONSTITUTION":
        plan = artifact.get("implementationPlan")
        if not isinstance(plan, dict):
            return {"status": "invalid", "reason": "plan_draft_invalid", "message": "CONSTITUTION draft must include implementationPlan."}
        violations = validate_implementation_plan(plan)
        if violations:
            return _validation_error("implementation_plan_invalid", violations)
        if artifact.get("tacticalDiff") is not None:
            tactical_validation = _validate_diff("tactical", artifact.get("tacticalDiff"),
                                                 known_bc_ids=_known_bc_ids(proposal_id))
            if tactical_validation:
                return tactical_validation
        return None
    if phase == "TASKS" and not isinstance(artifact.get("tasks"), list):
        return {"status": "invalid", "reason": "tasks_invalid", "message": "TASKS draft must include tasks list."}
    return None


def _validation_error(reason: str, violations: list[dict]) -> dict:
    return {
        "status": "invalid",
        "reason": reason,
        "violationSummary": violation_summary(violations),
        "violations": violations[:8],
    }


def _promote_confirmed(proposal_id: str, phase: str, artifact: dict) -> None:
    if phase in set(DDD_STAGE_ORDER):
        staged_runner.save_stage_artifact(proposal_id, phase, artifact)
    elif phase == "PROJECT_CONSTITUTION":
        # 015-issue3: 승인된 헌장을 **프로젝트 루트 :Constitution 노드**로 그래프에 생성한다.
        from api.features.constitution.services import constitution_store as store
        con = artifact.get("constitution") or {}
        fields = con.get("fields") if isinstance(con.get("fields"), dict) else {}
        chash = store.upsert_project_constitution(str(con.get("raw") or ""), fields)
        with get_session() as session:
            session.run(
                "MATCH (p:Proposal {id:$id}) SET p.constitutionConfirmed = true, p.constitutionHash = $h",
                id=proposal_id, h=chash,
            )
        SmartLogger.log(
            "INFO",
            f"project constitution node created from proposal: {proposal_id}",
            category="proposal_lifecycle.mcp.constitution_created",
            params={"proposalId": proposal_id, "hash": (chash or "")[:8],
                    "architectureStyle": fields.get("architectureStyle"),
                    "repoStrategy": fields.get("repoStrategy")},
        )
    elif phase == "STRATEGIC_DIFF":
        proposal_state_service.save_diff(proposal_id, "strategic", artifact.get("strategicDiff", artifact))
    elif phase in ("TACTICAL_DIFF", "CONSTITUTION"):
        if artifact.get("implementationPlan"):
            from api.features.proposal_lifecycle.services import plan_runner
            plan_runner.confirm_plan(
                proposal_id,
                artifact.get("implementationPlan") or {},
                artifact.get("tacticalDiff"),
                artifact.get("impactMap"),
            )
        elif artifact.get("tacticalDiff") is not None:
            proposal_state_service.save_diff(proposal_id, "tactical", artifact["tacticalDiff"])
    elif phase == "TASKS":
        proposal_state_service.save_tasks(proposal_id, artifact.get("tasks") or [])


def _phase_of(phase: str) -> str:
    """DDD 스테이지명을 스텝 테이블의 phase(STRATEGIC_DDD/TACTICAL_DDD)로 매핑."""
    normalized = (phase or "").upper()
    if normalized in set(DDD_STAGE_ORDER[:3]):
        return "STRATEGIC_DDD"
    if normalized in set(DDD_STAGE_ORDER[3:]):
        return "TACTICAL_DDD"
    return normalized


# --- 013-report-mcda: reportMarkdown 주입 헬퍼(FR-2/3) ----------------------


def _with_report(result: dict, phase: str, artifact: Any) -> dict:
    """대상 도구 응답에 서버 렌더 reportMarkdown 주입(기존 필드 불변, 추가만)."""
    try:
        result["reportMarkdown"] = report_render.render_report(phase, artifact)
    except Exception as e:  # 렌더 실패는 흐름을 막지 않음(표시 계층 전용).
        SmartLogger.log(
            "WARN",
            "reportMarkdown render failed; response returned without it.",
            category="proposal_lifecycle.mcp.report_render_failed",
            params={"phase": phase, "error": str(e)},
        )
    return result


def _overview_report(proposal_id: str) -> str:
    """proposal_get/resume 용 — Neo4j 저장 canonical artifact 를 합성 렌더."""
    node = proposal_state_service.get_node(proposal_id)
    if not node:
        return ""
    parts: list[str] = []
    strategic = _parse_stored(node.get("strategicDiff"))
    if strategic:
        parts.append(report_render.render_report("STRATEGIC_DIFF", {"strategicDiff": strategic}))
    tactical = _parse_stored(node.get("tacticalDiff"))
    plan = _parse_stored(node.get("implementationPlan"))
    if tactical or plan:
        payload: dict[str, Any] = {}
        if tactical:
            payload["tacticalDiff"] = tactical
        if plan:
            payload["implementationPlan"] = plan
        parts.append(report_render.render_report("TACTICAL_DIFF", payload))
    stages = _parse_stored(node.get("stageArtifacts"))
    if isinstance(stages, dict):
        for stage, art in stages.items():
            parts.append(report_render.render_report(stage, art))
    tasks = _parse_stored(node.get("tasksJson"))
    if tasks:
        parts.append(report_render.render_report("TASKS", {"tasks": tasks}))
    test = _parse_stored(node.get("testResults"))
    if test:
        parts.append(report_render.render_report("TEST", test))
    if not parts:
        return f"## 📄 제안 개요\n\n_아직 확정된 산출물이 없습니다 (현재 단계: {node.get('currentPhase')})_"
    return "\n\n---\n\n".join(parts)


def _parse_stored(raw: Any) -> Any:
    if raw is None:
        return None
    if isinstance(raw, (dict, list)):
        return raw
    try:
        return json.loads(raw)
    except Exception:
        return None


def _log(tool: str, proposal_id: str, **params: Any) -> None:
    SmartLogger.log(
        "INFO",
        f"Proposal MCP tool called: {tool}",
        category=f"proposal_lifecycle.mcp.{tool}",
        params={"proposalId": proposal_id, **params},
    )
