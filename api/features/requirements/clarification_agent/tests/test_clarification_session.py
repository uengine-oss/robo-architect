"""Tests for the in-memory clarification session store + state machine
(030 — T017)."""

from __future__ import annotations

import uuid

import pytest

from api.features.requirements.clarification_agent import clarification_session as cs
from api.features.requirements.clarification_contracts import (
    AmbiguityCategory,
    ClarificationProgressEvent,
    ClarificationQuestionDTO,
    ClarificationScope,
    QuestionStatus,
    QuestionType,
    ScopeType,
    SessionStatus,
    UserStorySnapshot,
)


def _scope(scope_id: str = "bc-1") -> ClarificationScope:
    return ClarificationScope(
        scopeType=ScopeType.bounded_context, scopeId=scope_id, scopeName="BC One"
    )


def _snapshots(*ids: str) -> dict[str, UserStorySnapshot]:
    return {
        rid: UserStorySnapshot(role="user", action=f"do {rid}", benefit="")
        for rid in ids
    }


def _q(qid: str, category: AmbiguityCategory = AmbiguityCategory.functional_scope) -> ClarificationQuestionDTO:
    return ClarificationQuestionDTO(
        questionId=qid,
        category=category,
        questionType=QuestionType.closed,
        questionText="why?",
        referencedRequirementIds=["us-1"],
        recommendedAnswer="",
        options=[],
    )


@pytest.fixture(autouse=True)
def _isolate_store(monkeypatch):
    """Each test starts with an empty `_SESSIONS` dict."""
    monkeypatch.setattr(cs, "_SESSIONS", {})
    yield


# ── Lifecycle ───────────────────────────────────────────────────────────


def test_create_session_starts_in_analyzing() -> None:
    sess = cs.create_session(_scope(), _snapshots("us-1", "us-2"))
    assert sess.status == SessionStatus.analyzing
    assert sess.questions == []
    assert "us-1" in sess.pre_session_snapshots


def test_set_questions_transitions_to_awaiting_answers() -> None:
    sess = cs.create_session(_scope(), _snapshots("us-1"))
    sess.set_questions(
        [_q(str(uuid.uuid4())), _q(str(uuid.uuid4()))],
        no_ambiguities=False,
        deferred_note=None,
    )
    assert sess.status == SessionStatus.awaiting_answers
    assert sess.progress.questionsTotal == 2
    # The store also numbers the queue starting from 1.
    assert [q.order for q in sess.questions] == [1, 2]


def test_no_ambiguities_path_lands_in_completed() -> None:
    sess = cs.create_session(_scope(), _snapshots("us-1"))
    sess.set_questions(
        [], no_ambiguities=True, deferred_note=None
    )
    assert sess.status == SessionStatus.completed
    assert sess.no_ambiguities is True


def test_mark_failed_preserves_already_applied_answers() -> None:
    # FR-013: scan failure must not lose already-applied questions.
    sess = cs.create_session(_scope(), _snapshots("us-1"))
    qid = str(uuid.uuid4())
    sess.set_questions([_q(qid)], no_ambiguities=False, deferred_note=None)
    sess.questions[0].status = QuestionStatus.applied
    sess.applied_requirement_ids[qid] = ["us-1"]

    sess.mark_failed("scan blew up")

    assert sess.status == SessionStatus.failed
    assert sess.questions[0].status == QuestionStatus.applied
    assert sess.applied_requirement_ids[qid] == ["us-1"]


# ── Progress / advance ──────────────────────────────────────────────────


def test_advance_moves_current_question_pointer() -> None:
    sess = cs.create_session(_scope(), _snapshots("us-1"))
    sess.set_questions(
        [_q("q1"), _q("q2"), _q("q3")], no_ambiguities=False, deferred_note=None
    )
    assert sess.current_question().questionId == "q1"
    sess.questions[0].status = QuestionStatus.applied
    sess.advance()
    assert sess.current_question().questionId == "q2"
    assert sess.progress.questionsAnswered == 1
    assert sess.progress.currentQuestionIndex == 1


def test_event_buffer_appends_and_snapshots() -> None:
    sess = cs.create_session(_scope(), _snapshots("us-1"))
    sess.push_event(
        ClarificationProgressEvent(phase="scanning", message="halfway", progress=0.5)
    )
    sess.push_event(
        ClarificationProgressEvent(
            phase="questions_ready", message="done", progress=1.0
        )
    )
    events = sess.snapshot_events()
    assert [e.phase for e in events] == ["scanning", "questions_ready"]
    # progress meta tracks the latest event.
    assert sess.progress.phase == "questions_ready"


# ── Single-active-session-per-scope (FR-016) ─────────────────────────────


def test_duplicate_active_session_rejected() -> None:
    sess1 = cs.create_session(_scope(), _snapshots("us-1"))
    with pytest.raises(cs.ScopeSessionExistsError) as excinfo:
        cs.create_session(_scope(), _snapshots("us-1"))
    assert excinfo.value.existing_session_id == sess1.session_id


def test_after_completion_new_session_allowed_for_same_scope() -> None:
    sess1 = cs.create_session(_scope(), _snapshots("us-1"))
    sess1.end()  # status → completed
    # Now a new session for the same scope should be allowed.
    sess2 = cs.create_session(_scope(), _snapshots("us-1"))
    assert sess2.session_id != sess1.session_id


def test_different_scopes_can_run_concurrently() -> None:
    sess_a = cs.create_session(_scope("bc-a"), _snapshots("us-1"))
    sess_b = cs.create_session(_scope("bc-b"), _snapshots("us-1"))
    assert sess_a.session_id != sess_b.session_id
    assert cs.active_session_for_scope(_scope("bc-a")).session_id == sess_a.session_id
    assert cs.active_session_for_scope(_scope("bc-b")).session_id == sess_b.session_id


def test_failed_scope_can_restart() -> None:
    sess1 = cs.create_session(_scope(), _snapshots("us-1"))
    sess1.mark_failed("err")
    sess2 = cs.create_session(_scope(), _snapshots("us-1"))
    assert sess2.session_id != sess1.session_id
