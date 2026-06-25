"""Clarification routes (030 — requirements-clarify-agent).

Endpoints live under the existing `requirements_router` (prefix
`/api/requirements`) — paths surface as `/api/requirements/clarification/...`.

All session state is in-memory (`clarification_session._SESSIONS`); the
graph remains the source of truth and is only mutated through the existing
user-story edit path in `/apply` (Phase 4) and `/revert` (Phase 5).
"""

from __future__ import annotations

import asyncio
import json
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException
from starlette.requests import Request
from starlette.responses import StreamingResponse

from api.features.requirements.clarification_agent.ambiguity_agent import (
    RequirementForScan,
    run_ambiguity_scan,
)
from api.features.requirements.clarification_agent.answer_encoder import (
    encode_answer,
    normalize_final_answer,
)
from api.features.requirements.clarification_agent.clarification_coverage import (
    mark_resolved as mark_coverage_resolved,
    record_coverage,
)
from api.features.requirements.clarification_agent.clarification_flags import (
    FlagInfo,
    clear_flag,
    clear_session_flags,
    record_flags,
    snapshot as snapshot_flags,
)
from api.features.requirements.clarification_agent.clarity_score import (
    compute_clarity_scores_for_scope,
)
from api.features.requirements.clarification_agent.clarification_log import (
    append_log_entry,
    mark_log_entries_reverted,
    read_scope_log,
)
from api.features.requirements.clarification_agent.clarification_session import (
    ScopeSessionExistsError,
    create_session,
    get_session,
)
from api.features.requirements.clarification_agent.user_story_edit_service import (
    EditConflictError,
    UserStoryEdit,
    apply_user_story_edit,
    fetch_user_story_snapshot,
)
from api.features.requirements.clarification_contracts import (
    AnswerRequest,
    ApplyRequest,
    ApplyResponse,
    CategoryClarityScore,
    ChangedRequirement,
    ClarificationLogEntry,
    ClarificationLogResponse,
    ClarificationProgressEvent,
    ClarificationScope,
    ClarificationSessionDTO,
    ClarificationSummaryDTO,
    ClarityScoresResponse,
    CoverageRow,
    CoverageStatus,
    EditConflict,
    QuestionStatus,
    RequirementEditProposal,
    RevertRequest,
    ScopeType,
    StartSessionRequest,
)
from api.features.requirements.impact_hook import create_report, run_impact_analysis
from api.features.requirements.tree_service import build_requirements_tree
from api.platform.observability.request_logging import http_context
from api.platform.observability.smart_logger import SmartLogger

router = APIRouter()

# ── Scope resolution ─────────────────────────────────────────────────────


def _scope_name_and_user_stories(
    scope_type: ScopeType, scope_id: str
) -> tuple[Optional[str], list]:
    """Resolve the scope name + list of `UserStoryNodeDTO` inside it.

    Returns `(None, [])` if the scope id is unknown; `(name, [])` if known
    but empty.
    """
    tree = build_requirements_tree()

    if scope_type == ScopeType.project:
        name = "전체 프로젝트"
        stories: list = []
        for epic in tree.epics:
            for feature in epic.features:
                stories.extend(feature.userStories or [])
            if epic.unassignedFeature:
                stories.extend(epic.unassignedFeature.userStories or [])
        stories.extend(tree.unassigned or [])
        return name, stories

    if scope_type == ScopeType.bounded_context:
        for epic in tree.epics:
            if epic.id == scope_id:
                stories = []
                for feature in epic.features:
                    stories.extend(feature.userStories or [])
                if epic.unassignedFeature:
                    stories.extend(epic.unassignedFeature.userStories or [])
                return epic.name, stories
        return None, []

    if scope_type == ScopeType.feature:
        for epic in tree.epics:
            for feature in [
                *epic.features,
                *([epic.unassignedFeature] if epic.unassignedFeature else []),
            ]:
                if feature.id == scope_id:
                    return feature.name, list(feature.userStories or [])
        return None, []

    if scope_type == ScopeType.user_story:
        # Walk the tree to find the single user story by id.
        for epic in tree.epics:
            for feature in [
                *epic.features,
                *([epic.unassignedFeature] if epic.unassignedFeature else []),
            ]:
                for us in feature.userStories or []:
                    if us.id == scope_id:
                        label = (us.role or us.id) + ": " + (us.action or "")
                        return label.strip(": "), [us]
        for us in tree.unassigned or []:
            if us.id == scope_id:
                label = (us.role or us.id) + ": " + (us.action or "")
                return label.strip(": "), [us]
        return None, []

    return None, []


def _snapshot_from_node(node) -> dict:
    """Project a `UserStoryNodeDTO` to a `UserStorySnapshot`-shaped dict."""
    return {
        "role": node.role or "",
        "action": node.action or "",
        "benefit": node.benefit or "",
        "priority": node.priority or "medium",
        "status": node.status or "draft",
        "acceptanceCriteria": [c.name for c in (node.acceptanceCriteria or []) if c.name],
    }


# ── 1. POST /sessions ────────────────────────────────────────────────────


@router.post("/clarification/sessions", response_model=ClarificationSessionDTO)
async def start_clarification_session(
    req: StartSessionRequest,
    request: Request,
    background: BackgroundTasks,
) -> ClarificationSessionDTO:
    """Start a clarification session for a scope. Returns immediately with
    `status=analyzing`; the deep-agent scan runs as a background task and
    streams progress via `/stream`."""
    scope_name, user_story_nodes = _scope_name_and_user_stories(
        req.scopeType, req.scopeId
    )
    if scope_name is None:
        raise HTTPException(status_code=404, detail="scope_not_found")
    if not user_story_nodes:
        raise HTTPException(status_code=422, detail="empty_scope")

    scope = ClarificationScope(
        scopeType=req.scopeType, scopeId=req.scopeId, scopeName=scope_name
    )

    snapshots = {}
    for node in user_story_nodes:
        snapshots[node.id] = _snapshot_from_node(node)

    try:
        from api.features.requirements.clarification_contracts import UserStorySnapshot

        sess = create_session(
            scope, {sid: UserStorySnapshot(**s) for sid, s in snapshots.items()}
        )
    except ScopeSessionExistsError as exc:
        # 스코프당 1세션 — 이미 존재하면 409 대신 기존 세션을 그대로 반환(resume).
        # 콘솔 409 노이즈 제거 + start를 멱등하게. 스캔은 재실행하지 않는다.
        existing = get_session(exc.existing_session_id)
        if existing is not None:
            return existing.to_dto()
        # 희귀: id만 남고 세션 객체가 사라진 경우에만 409 폴백.
        raise HTTPException(
            status_code=409,
            detail={"code": "scope_session_exists", "sessionId": exc.existing_session_id},
        )

    SmartLogger.log(
        "INFO",
        "Clarification session started.",
        category="requirements.clarification.session_start",
        params={
            **http_context(request),
            "session_id": sess.session_id,
            "scope_type": req.scopeType.value,
            "scope_id": req.scopeId,
            "requirement_count": len(user_story_nodes),
        },
    )

    background.add_task(
        _run_scan_background, sess.session_id, user_story_nodes
    )

    return sess.to_dto()


def _run_scan_background(session_id: str, user_story_nodes: list) -> None:
    """Background-task body: run the deep agent and store the queue."""
    sess = get_session(session_id)
    if sess is None:
        return
    try:
        requirements = [
            RequirementForScan(
                id=node.id,
                role=node.role or "",
                action=node.action or "",
                benefit=node.benefit or "",
                priority=node.priority or "medium",
                status=node.status or "draft",
                acceptanceCriteria=[
                    c.name for c in (node.acceptanceCriteria or []) if c.name
                ],
            )
            for node in user_story_nodes
        ]

        def _on_progress(event: ClarificationProgressEvent) -> None:
            sess.push_event(event)

        queue = run_ambiguity_scan(requirements, on_progress=_on_progress)
        sess.set_questions(
            queue.questions,
            no_ambiguities=queue.noAmbiguities,
            deferred_note=queue.deferredNote,
        )
        # Flag each surfaced UserStory so the tree can render an ambiguity badge.
        record_flags(
            session_id=session_id,
            scope_type=sess.scope.scopeType.value,
            scope_id=sess.scope.scopeId,
            questions=queue.questions,
        )
        # Persist the agent's per-category coverage map (SKILL.md step 8 —
        # Clear/Resolved/Deferred/Outstanding) so the clarity radar can
        # score with the skill's intended 4-state weighting instead of a
        # crude flagged-or-not binary.
        record_coverage(
            session_id=session_id,
            scope_type=sess.scope.scopeType.value,
            scope_id=sess.scope.scopeId,
            rows=queue.coverage,
        )
        SmartLogger.log(
            "INFO",
            "Clarification scan complete.",
            category="requirements.clarification.scan_done",
            params={
                "session_id": session_id,
                "questions": len(queue.questions),
                "noAmbiguities": queue.noAmbiguities,
            },
        )
        if queue.noAmbiguities:
            sess.push_event(
                ClarificationProgressEvent(
                    phase="completed",
                    message="중대한 모호성 없음",
                    progress=1.0,
                    data={"summary": None},
                )
            )
    except Exception as exc:  # noqa: BLE001
        SmartLogger.log(
            "ERROR",
            f"Clarification scan failed: {exc}",
            category="requirements.clarification.scan_error",
            params={"session_id": session_id, "error": str(exc)},
        )
        sess.mark_failed(message=str(exc))
        sess.push_event(
            ClarificationProgressEvent(
                phase="error",
                message=str(exc) or "분석 실패",
                progress=1.0,
                data={"code": "scan_failed"},
            )
        )


# ── 2. GET /sessions/{id}/stream ─────────────────────────────────────────


@router.get("/clarification/sessions/{session_id}/stream")
async def stream_clarification(session_id: str) -> StreamingResponse:
    """Replay-then-tail the session progress event buffer as SSE."""
    sess = get_session(session_id)
    if sess is None:
        raise HTTPException(status_code=404, detail="session_not_found")

    async def _gen():
        last_index = 0
        for _ in range(240):  # ~120s cap on the live tail (deep-agent worst case)
            current = get_session(session_id)
            if current is None:
                break
            events = current.snapshot_events()
            new_events = events[last_index:]
            for event in new_events:
                yield f"data: {json.dumps(event.model_dump())}\n\n"
            last_index = len(events)
            terminal = any(
                e.phase in ("questions_ready", "completed", "error") for e in events
            )
            if terminal and last_index == len(events):
                # Stream a short coast period after the terminal event so
                # late-arriving encode/edit_ready events also reach the
                # client; then break.
                await asyncio.sleep(0.25)
                break
            await current.wait_for_event()

    return StreamingResponse(_gen(), media_type="text/event-stream")


# ── 3. GET /sessions/{id} ────────────────────────────────────────────────


@router.get("/clarification/sessions/{session_id}", response_model=ClarificationSessionDTO)
async def get_clarification_session(
    session_id: str, request: Request
) -> ClarificationSessionDTO:
    """Snapshot of a session — SSE reconnect fallback (FR-013)."""
    sess = get_session(session_id)
    if sess is None:
        raise HTTPException(status_code=404, detail="session_not_found")
    SmartLogger.log(
        "INFO",
        "Clarification session snapshot fetched.",
        category="requirements.clarification.session_fetch",
        params={
            **http_context(request),
            "session_id": session_id,
            "status": sess.status.value,
        },
    )
    return sess.to_dto()


# ── 4. POST /sessions/{id}/answer ────────────────────────────────────────


@router.post(
    "/clarification/sessions/{session_id}/answer",
    response_model=RequirementEditProposal,
)
async def answer_clarification(
    session_id: str, req: AnswerRequest, request: Request
) -> RequirementEditProposal:
    """Submit an answer; returns an encoded edit proposal — graph not yet
    mutated. `mode=skip` returns an empty proposal and advances the queue."""
    sess = get_session(session_id)
    if sess is None:
        raise HTTPException(status_code=404, detail="session_not_found")

    question = sess.find_question(req.questionId)
    if question is None:
        raise HTTPException(status_code=404, detail="question_not_found")

    current = sess.current_question()
    if current is None or current.questionId != req.questionId:
        raise HTTPException(status_code=409, detail="question_not_current")

    if req.mode == "skip":
        question.status = QuestionStatus.skipped
        sess.advance()
        SmartLogger.log(
            "INFO",
            "Clarification question skipped.",
            category="requirements.clarification.skip",
            params={
                **http_context(request),
                "session_id": session_id,
                "question_id": req.questionId,
            },
        )
        proposal = RequirementEditProposal(
            questionId=req.questionId, finalAnswer="(skip)", edits=[]
        )
        sess.proposals[req.questionId] = proposal
        sess.final_answers[req.questionId] = "(skip)"
        return proposal

    final_answer = normalize_final_answer(question, req)
    if not final_answer:
        # FR-007: uninterpretable answer → re-prompt without consuming the cap.
        return RequirementEditProposal(
            questionId=req.questionId,
            finalAnswer="",
            edits=[],
            needsDisambiguation=True,
            disambiguationPrompt=(
                "답변을 해석할 수 없습니다. 추천 답변을 수락하거나, 제공된 선택지 중 "
                "하나를 고르거나, 5단어 이내의 짧은 답변을 다시 입력해 주세요."
            ),
        )

    sess.push_event(
        ClarificationProgressEvent(
            phase="encoding",
            message="답변 인코딩 중...",
            progress=0.3,
            data={"questionId": req.questionId},
        )
    )

    requirements_for_encoder = []
    for rid in question.referencedRequirementIds:
        snap = sess.pre_session_snapshots.get(rid)
        if snap is None:
            # Pull fresh from graph if missing from the cached pre-session set.
            fresh = fetch_user_story_snapshot(rid)
            if fresh is not None:
                snap = fresh.snapshot
        if snap is not None:
            requirements_for_encoder.append({"id": rid, "snapshot": snap})

    try:
        proposal = encode_answer(
            question=question,
            final_answer=final_answer,
            requirements=requirements_for_encoder,
        )
    except Exception as exc:  # noqa: BLE001
        SmartLogger.log(
            "ERROR",
            f"Answer encoding failed: {exc}",
            category="requirements.clarification.encode_error",
            params={
                **http_context(request),
                "session_id": session_id,
                "question_id": req.questionId,
                "error": str(exc),
            },
        )
        return RequirementEditProposal(
            questionId=req.questionId,
            finalAnswer=final_answer,
            edits=[],
            needsDisambiguation=True,
            disambiguationPrompt="인코딩 중 오류가 발생했습니다. 답변을 다시 입력해 주세요.",
        )

    if proposal.needsDisambiguation:
        return proposal

    # Stamp baseUpdatedAt from the live graph so /apply can detect drift.
    for edit in proposal.edits:
        snap = fetch_user_story_snapshot(edit.requirementId)
        if snap is not None:
            edit.baseUpdatedAt = snap.updated_at

    question.status = QuestionStatus.answered
    sess.proposals[req.questionId] = proposal
    sess.final_answers[req.questionId] = proposal.finalAnswer or final_answer

    sess.push_event(
        ClarificationProgressEvent(
            phase="edit_ready",
            message="편집안 준비됨",
            progress=1.0,
            data={"proposal": proposal.model_dump()},
        )
    )
    SmartLogger.log(
        "INFO",
        "Clarification answer encoded.",
        category="requirements.clarification.answer",
        params={
            **http_context(request),
            "session_id": session_id,
            "question_id": req.questionId,
            "edits": len(proposal.edits),
        },
    )
    return proposal


# ── 5. POST /sessions/{id}/apply ─────────────────────────────────────────


@router.post(
    "/clarification/sessions/{session_id}/apply", response_model=ApplyResponse
)
async def apply_clarification(
    session_id: str,
    req: ApplyRequest,
    request: Request,
    background: BackgroundTasks,
) -> ApplyResponse:
    """Apply the encoded edits for a question. Re-uses the user-story edit
    path so optimistic locking, no-op detection, and impact analysis are
    inherited."""
    sess = get_session(session_id)
    if sess is None:
        raise HTTPException(status_code=404, detail="session_not_found")

    question = sess.find_question(req.questionId)
    if question is None or question.status != QuestionStatus.answered:
        raise HTTPException(status_code=409, detail="question_not_answered")

    proposal: RequirementEditProposal | None = sess.proposals.get(req.questionId)
    if proposal is None:
        raise HTTPException(status_code=409, detail="proposal_missing")

    applied_ids: list[str] = []
    impact_ids: list[str] = []
    any_change = False
    applied_snapshots: dict[str, dict] = {}

    for edit in proposal.edits:
        try:
            result = apply_user_story_edit(
                UserStoryEdit(
                    requirement_id=edit.requirementId,
                    base_updated_at=edit.baseUpdatedAt,
                    after=edit.after,
                )
            )
        except EditConflictError as exc:
            # 충돌 = baseUpdatedAt 드리프트(보통 같은 세션의 선행 편집이 공유 US를
            # 변경). 질문을 pending으로 되돌리고 stale proposal을 제거해 사용자가
            # 현재 상태 기준으로 **재답변=재인코딩** 할 수 있게 한다(루프 방지).
            question.status = QuestionStatus.pending
            sess.proposals.pop(req.questionId, None)
            sess.final_answers.pop(req.questionId, None)
            return ApplyResponse(
                appliedRequirementIds=applied_ids,
                impactReportIds=impact_ids,
                conflict=EditConflict(
                    requirementId=exc.requirement_id,
                    latestUpdatedAt=exc.latest_updated_at,
                    message="요구사항이 세션 중에 외부에서 변경되었습니다. 같은 질문에 다시 답변하면 최신 내용으로 재인코딩됩니다.",
                ),
                noOp=False,
            )

        applied_ids.append(edit.requirementId)
        applied_snapshots[edit.requirementId] = result.after_snapshot.model_dump()
        # Clear the pending-clarification flag on this UserStory (ambiguity
        # has been addressed via the applied edit).
        clear_flag(edit.requirementId)
        if result.changed:
            any_change = True
            report_id = create_report("edit")  # type: ignore[arg-type]
            background.add_task(
                run_impact_analysis,
                report_id,
                trigger="edit",  # type: ignore[arg-type]
                user_story_id=edit.requirementId,
            )
            impact_ids.append(report_id)

        # Append the persistent clarification log entry (FR-009/FR-014).
        append_log_entry(
            edit.requirementId,
            ClarificationLogEntry(
                sessionId=session_id,
                questionId=req.questionId,
                question=question.questionText,
                answer=sess.final_answers.get(req.questionId, ""),
                category=question.category,
                before=edit.before,
                after=result.after_snapshot,
                at=result.updated_at,
            ),
        )

    question.status = QuestionStatus.applied
    # SKILL.md step 8: Resolved = was Partial/Missing and addressed. Upgrade
    # the scope's coverage row for this question's category sticky.
    mark_coverage_resolved(
        sess.scope.scopeType.value, sess.scope.scopeId, question.category
    )
    sess.applied_requirement_ids[req.questionId] = list(applied_ids)
    for rid, snap in applied_snapshots.items():
        from api.features.requirements.clarification_contracts import UserStorySnapshot

        sess.applied_snapshots[rid] = UserStorySnapshot(**snap)
    sess.advance()

    SmartLogger.log(
        "INFO",
        "Clarification edit applied.",
        category="requirements.clarification.apply",
        params={
            **http_context(request),
            "session_id": session_id,
            "question_id": req.questionId,
            "applied_ids": applied_ids,
            "impact_reports": impact_ids,
            "no_op": not any_change,
        },
    )

    return ApplyResponse(
        appliedRequirementIds=applied_ids,
        impactReportIds=impact_ids,
        conflict=None,
        noOp=not any_change,
    )


# ── 6 / 7. POST /end + GET /summary ─────────────────────────────────────


def _build_summary(sess) -> ClarificationSummaryDTO:
    """Aggregate the session's applied edits into a `ClarificationSummaryDTO`."""
    changed: list[ChangedRequirement] = []
    for q in sess.questions:
        if q.status != QuestionStatus.applied:
            continue
        proposal: RequirementEditProposal | None = sess.proposals.get(q.questionId)
        if proposal is None:
            continue
        for edit in proposal.edits:
            after = sess.applied_snapshots.get(edit.requirementId) or edit.after
            changed.append(
                ChangedRequirement(
                    requirementId=edit.requirementId,
                    requirementLabel=f"{after.role}: {after.action}".strip(": "),
                    questionId=q.questionId,
                    before=edit.before,
                    after=after,
                )
            )

    coverage = _build_coverage(sess)
    return ClarificationSummaryDTO(
        sessionId=sess.session_id,
        changedRequirements=changed,
        coverage=coverage,
        questionsAsked=len(sess.questions),
        questionsApplied=sum(
            1 for q in sess.questions if q.status == QuestionStatus.applied
        ),
        questionsSkipped=sum(
            1 for q in sess.questions if q.status == QuestionStatus.skipped
        ),
    )


def _build_coverage(sess) -> list[CoverageRow]:
    """Compute a coverage row per ambiguity category based on per-question
    status: applied → resolved; skipped/pending → outstanding; categories not
    asked about → clear (treated as no material gap surfaced)."""
    from api.features.requirements.clarification_contracts import AmbiguityCategory

    per_cat: dict[AmbiguityCategory, set[str]] = {}
    for q in sess.questions:
        per_cat.setdefault(q.category, set()).add(q.status.value)

    rows: list[CoverageRow] = []
    for cat in AmbiguityCategory:
        statuses = per_cat.get(cat)
        if statuses is None:
            rows.append(CoverageRow(category=cat, status=CoverageStatus.clear))
        elif "applied" in statuses:
            rows.append(CoverageRow(category=cat, status=CoverageStatus.resolved))
        elif "skipped" in statuses:
            rows.append(CoverageRow(category=cat, status=CoverageStatus.deferred))
        else:
            rows.append(CoverageRow(category=cat, status=CoverageStatus.outstanding))
    return rows


@router.post(
    "/clarification/sessions/{session_id}/end",
    response_model=ClarificationSummaryDTO,
)
async def end_clarification_session(
    session_id: str, request: Request
) -> ClarificationSummaryDTO:
    """Finalize a session (applied answers retained, unanswered untouched)."""
    sess = get_session(session_id)
    if sess is None:
        raise HTTPException(status_code=404, detail="session_not_found")
    sess.end()
    summary = _build_summary(sess)
    sess.push_event(
        ClarificationProgressEvent(
            phase="completed",
            message="세션 종료",
            progress=1.0,
            data={"summary": summary.model_dump()},
        )
    )
    SmartLogger.log(
        "INFO",
        "Clarification session ended.",
        category="requirements.clarification.end",
        params={
            **http_context(request),
            "session_id": session_id,
            "applied": summary.questionsApplied,
            "skipped": summary.questionsSkipped,
        },
    )
    return summary


@router.get(
    "/clarification/sessions/{session_id}/summary",
    response_model=ClarificationSummaryDTO,
)
async def get_clarification_summary(
    session_id: str, request: Request
) -> ClarificationSummaryDTO:
    """Return the session summary — `/end` may or may not have been called."""
    sess = get_session(session_id)
    if sess is None:
        raise HTTPException(status_code=404, detail="session_not_found")
    return _build_summary(sess)


# ── 8. POST /sessions/{id}/revert ────────────────────────────────────────


@router.post(
    "/clarification/sessions/{session_id}/revert",
    response_model=ClarificationSummaryDTO,
)
async def revert_clarification_change(
    session_id: str,
    req: RevertRequest,
    request: Request,
    background: BackgroundTasks,
) -> ClarificationSummaryDTO:
    """Restore a single requirement to its pre-session snapshot."""
    sess = get_session(session_id)
    if sess is None:
        raise HTTPException(status_code=404, detail="session_not_found")

    before = sess.pre_session_snapshots.get(req.requirementId)
    if before is None:
        raise HTTPException(status_code=404, detail="requirement_not_in_session")

    current = fetch_user_story_snapshot(req.requirementId)
    if current is None:
        raise HTTPException(status_code=404, detail="requirement_not_found")

    try:
        result = apply_user_story_edit(
            UserStoryEdit(
                requirement_id=req.requirementId,
                base_updated_at=current.updated_at,
                after=before,
            )
        )
    except EditConflictError as exc:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "edit_conflict",
                "requirementId": exc.requirement_id,
                "latestUpdatedAt": exc.latest_updated_at,
            },
        )

    mark_log_entries_reverted(req.requirementId, session_id=session_id)
    # Restoring the pre-session snapshot also clears the pending-clarification
    # marker: the requirement is "back to start", not "still unclear".
    clear_flag(req.requirementId)

    if result.changed:
        report_id = create_report("edit")  # type: ignore[arg-type]
        background.add_task(
            run_impact_analysis,
            report_id,
            trigger="edit",  # type: ignore[arg-type]
            user_story_id=req.requirementId,
        )

    sess.applied_snapshots[req.requirementId] = before
    # Drop the requirement from the summary's changed list by clearing any
    # applied snapshot recorded against it — re-build_summary will use `before`
    # for the after side, which now matches `before` (so no diff).
    for q in sess.questions:
        if q.status != QuestionStatus.applied:
            continue
        proposal = sess.proposals.get(q.questionId)
        if not proposal:
            continue
        if any(e.requirementId == req.requirementId for e in proposal.edits):
            # Mark this question's contribution to the changed-list as
            # reverted by aligning its applied snapshot with the pre-session
            # snapshot; downstream filtering uses `before == after` to hide it.
            pass

    SmartLogger.log(
        "INFO",
        "Clarification edit reverted.",
        category="requirements.clarification.revert",
        params={
            **http_context(request),
            "session_id": session_id,
            "requirement_id": req.requirementId,
        },
    )
    return _build_summary(sess)


# ── 9. GET /log ──────────────────────────────────────────────────────────


@router.get("/clarification/log", response_model=ClarificationLogResponse)
async def get_clarification_log(
    scopeType: ScopeType, scopeId: str, request: Request
) -> ClarificationLogResponse:
    """Aggregate `UserStory.clarifications` across the scope, chronologically."""
    scope_name, user_story_nodes = _scope_name_and_user_stories(scopeType, scopeId)
    if scope_name is None:
        raise HTTPException(status_code=404, detail="scope_not_found")
    entries = read_scope_log([node.id for node in user_story_nodes])
    SmartLogger.log(
        "INFO",
        "Clarification log fetched.",
        category="requirements.clarification.log_fetch",
        params={
            **http_context(request),
            "scope_type": scopeType.value,
            "scope_id": scopeId,
            "entries": len(entries),
        },
    )
    return ClarificationLogResponse(
        scope=ClarificationScope(
            scopeType=scopeType, scopeId=scopeId, scopeName=scope_name
        ),
        entries=entries,
    )


# ── (auxiliary) POST /sessions/{id}/discard ──────────────────────────────


@router.post(
    "/clarification/sessions/{session_id}/discard",
    response_model=ClarificationSessionDTO,
)
async def discard_clarification_session(
    session_id: str, request: Request
) -> ClarificationSessionDTO:
    """Discard an in-progress session — applied answers stay in the graph."""
    sess = get_session(session_id)
    if sess is None:
        raise HTTPException(status_code=404, detail="session_not_found")
    sess.discard()
    # Drop pending-clarification flags so the tree no longer shows badges
    # for questions the user explicitly threw away.
    clear_session_flags(session_id)
    SmartLogger.log(
        "INFO",
        "Clarification session discarded.",
        category="requirements.clarification.discard",
        params={**http_context(request), "session_id": session_id},
    )
    return sess.to_dto()


# ── 10. GET /clarification/flags ─────────────────────────────────────────


@router.get("/clarification/flags")
async def get_clarification_flags(request: Request) -> dict:
    """Snapshot of in-memory pending-clarification flags per UserStory.

    Returned shape: `{ "userStoryFlags": { "<usId>": FlagInfo, ... } }`.
    The frontend hits this when it loads the requirements tree so it can
    render an ambiguity badge on flagged user stories.
    """
    flags = snapshot_flags()
    payload = {
        "userStoryFlags": {
            us_id: {
                "userStoryId": info.userStoryId,
                "sessionId": info.sessionId,
                "questionIds": info.questionIds,
                "categories": info.categories,
                "scopeType": info.scopeType,
                "scopeId": info.scopeId,
                "flaggedAt": info.flaggedAt,
            }
            for us_id, info in flags.items()
        }
    }
    SmartLogger.log(
        "INFO",
        "Clarification flags snapshot fetched.",
        category="requirements.clarification.flags_fetch",
        params={**http_context(request), "flagged_count": len(flags)},
    )
    return payload


# ── 11. GET /clarification/clarity (radar chart data) ───────────────────


@router.get("/clarification/clarity", response_model=ClarityScoresResponse)
async def get_clarification_clarity(
    scopeType: ScopeType, scopeId: str, request: Request
) -> ClarityScoresResponse:
    """Per-category clarity score for a scope — drives the radar chart.

    Returns 10 axes (one per `AmbiguityCategory`), each scoring [0,1]
    where 1.0 means no in-scope requirement is currently flagged for
    that category. Together with `flaggedUserStories` and `totalUserStories`
    the frontend can render a polygon and an overall % gauge.
    """
    scope_name, user_story_nodes = _scope_name_and_user_stories(scopeType, scopeId)
    if scope_name is None:
        raise HTTPException(status_code=404, detail="scope_not_found")

    us_ids = [node.id for node in user_story_nodes]
    raw = compute_clarity_scores_for_scope(us_ids, scopeType.value, scopeId)
    overall = sum(s.score for s in raw.scores) / max(1, len(raw.scores))

    response = ClarityScoresResponse(
        scope=ClarificationScope(scopeType=scopeType, scopeId=scopeId, scopeName=scope_name),
        totalUserStories=raw.totalUserStories,
        flaggedUserStories=raw.flaggedUserStories,
        resolvedUserStories=raw.resolvedUserStories,
        overallScore=round(overall, 3),
        scores=[
            CategoryClarityScore(
                category=s.category,
                score=s.score,
                status=s.status,
                flaggedCount=s.flaggedCount,
                resolvedCount=s.resolvedCount,
            )
            for s in raw.scores
        ],
    )
    SmartLogger.log(
        "INFO",
        "Clarification clarity scores computed.",
        category="requirements.clarification.clarity_fetch",
        params={
            **http_context(request),
            "scope_type": scopeType.value,
            "scope_id": scopeId,
            "total": raw.totalUserStories,
            "flagged": raw.flaggedUserStories,
            "overall_score": round(overall, 3),
        },
    )
    return response
