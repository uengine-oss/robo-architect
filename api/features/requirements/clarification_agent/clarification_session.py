"""In-memory clarification session store + state machine (030).

Process-local store keyed by `sessionId`. Same lifecycle pattern as the
impact-report `_REPORTS` dict and the ingestion session — the graph remains
the source of truth; this holds only the volatile session state (queue,
current index, replayable SSE buffer).

State machine (data-model §5):
    analyzing → awaiting_answers → encoding → completed
              ↘ failed
                                              ↘ discarded
"""

from __future__ import annotations

import asyncio
import threading
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from api.features.requirements.clarification_contracts import (
    ClarificationProgressEvent,
    ClarificationQuestionDTO,
    ClarificationScope,
    ClarificationSessionDTO,
    QuestionStatus,
    SessionProgress,
    SessionStatus,
    UserStorySnapshot,
)


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


class ClarificationSession:
    """One in-flight clarification run."""

    def __init__(self, scope: ClarificationScope, snapshots: dict[str, UserStorySnapshot]):
        self.session_id: str = str(uuid.uuid4())
        self.scope: ClarificationScope = scope
        self.status: SessionStatus = SessionStatus.analyzing
        self.questions: list[ClarificationQuestionDTO] = []
        self.no_ambiguities: bool = False
        self.deferred_note: Optional[str] = None
        self.progress: SessionProgress = SessionProgress(
            phase="loading_scope", message="범위 로드 중..."
        )
        self.created_at: str = _utcnow()
        self.ended_at: Optional[str] = None

        # Pre-session snapshots — used by /revert (FR-010) and the summary
        # before/after rendering.
        self.pre_session_snapshots: dict[str, UserStorySnapshot] = dict(snapshots)
        # Per-question encoded proposals (proposals returned from /answer).
        self.proposals: dict[str, Any] = {}
        # Per-question final answer text (after normalization).
        self.final_answers: dict[str, str] = {}
        # Per-question post-apply snapshot (for the summary).
        self.applied_snapshots: dict[str, UserStorySnapshot] = {}
        # Per-question requirement ids it touched on apply.
        self.applied_requirement_ids: dict[str, list[str]] = {}

        # SSE replay buffer + pubsub.
        self.events: list[ClarificationProgressEvent] = []
        self._waiters: list[asyncio.Event] = []
        self._lock = threading.Lock()

    # ── progress / events ────────────────────────────────────────────

    def push_event(self, event: ClarificationProgressEvent) -> None:
        with self._lock:
            self.events.append(event)
            # Snap progress meta to the latest event.
            self.progress = SessionProgress(
                phase=event.phase,
                message=event.message,
                questionsTotal=self.progress.questionsTotal,
                questionsAnswered=self.progress.questionsAnswered,
                currentQuestionIndex=self.progress.currentQuestionIndex,
            )
            for w in list(self._waiters):
                try:
                    w.set()
                except Exception:  # noqa: BLE001
                    pass
            self._waiters.clear()

    async def wait_for_event(self) -> None:
        waiter = asyncio.Event()
        with self._lock:
            self._waiters.append(waiter)
        try:
            await asyncio.wait_for(waiter.wait(), timeout=15.0)
        except asyncio.TimeoutError:
            pass

    def snapshot_events(self) -> list[ClarificationProgressEvent]:
        with self._lock:
            return list(self.events)

    # ── queue mutations ──────────────────────────────────────────────

    def set_questions(
        self,
        questions: list[ClarificationQuestionDTO],
        *,
        no_ambiguities: bool,
        deferred_note: Optional[str],
    ) -> None:
        # Number the queue 1..N and ensure pending.
        self.questions = []
        for i, q in enumerate(questions, start=1):
            q.order = i
            q.status = QuestionStatus.pending
            self.questions.append(q)
        self.no_ambiguities = no_ambiguities
        self.deferred_note = deferred_note
        self.progress = SessionProgress(
            phase="questions_ready" if questions else "completed",
            message="질문 큐 준비됨" if questions else "중대한 모호성 없음",
            questionsTotal=len(questions),
            questionsAnswered=0,
            currentQuestionIndex=0 if questions else 0,
        )
        if no_ambiguities and not questions:
            self.status = SessionStatus.completed
            self.ended_at = _utcnow()
        else:
            self.status = SessionStatus.awaiting_answers

    def mark_failed(self, message: str = "") -> None:
        self.status = SessionStatus.failed
        self.ended_at = _utcnow()
        self.progress = SessionProgress(
            phase="error",
            message=message or "분석 실패",
            questionsTotal=self.progress.questionsTotal,
            questionsAnswered=self.progress.questionsAnswered,
            currentQuestionIndex=self.progress.currentQuestionIndex,
        )

    def end(self) -> None:
        if self.status not in (SessionStatus.failed, SessionStatus.discarded):
            self.status = SessionStatus.completed
        self.ended_at = self.ended_at or _utcnow()

    def discard(self) -> None:
        self.status = SessionStatus.discarded
        self.ended_at = _utcnow()

    # ── question lookup ──────────────────────────────────────────────

    def find_question(self, question_id: str) -> Optional[ClarificationQuestionDTO]:
        for q in self.questions:
            if q.questionId == question_id:
                return q
        return None

    def current_question(self) -> Optional[ClarificationQuestionDTO]:
        for q in self.questions:
            if q.status == QuestionStatus.pending:
                return q
        return None

    def advance(self) -> None:
        """Update progress meta after a question is answered/skipped/applied."""
        total = len(self.questions)
        answered = sum(
            1
            for q in self.questions
            if q.status in (QuestionStatus.applied, QuestionStatus.skipped)
        )
        current = next(
            (i for i, q in enumerate(self.questions) if q.status == QuestionStatus.pending),
            total,
        )
        self.progress = SessionProgress(
            phase=self.progress.phase,
            message=self.progress.message,
            questionsTotal=total,
            questionsAnswered=answered,
            currentQuestionIndex=current,
        )

    # ── DTO ──────────────────────────────────────────────────────────

    def to_dto(self) -> ClarificationSessionDTO:
        return ClarificationSessionDTO(
            sessionId=self.session_id,
            scope=self.scope,
            status=self.status,
            progress=self.progress,
            questions=list(self.questions),
            noAmbiguities=self.no_ambiguities,
            deferredNote=self.deferred_note,
            createdAt=self.created_at,
            endedAt=self.ended_at,
        )


# ── Module-level store ──────────────────────────────────────────────────

_SESSIONS: dict[str, ClarificationSession] = {}
_STORE_LOCK = threading.Lock()


def _scope_key(scope: ClarificationScope) -> str:
    return f"{scope.scopeType.value}:{scope.scopeId}"


def active_session_for_scope(scope: ClarificationScope) -> Optional[ClarificationSession]:
    """Return the currently in-flight session for a scope, if any (FR-016)."""
    key = _scope_key(scope)
    with _STORE_LOCK:
        for sess in _SESSIONS.values():
            if _scope_key(sess.scope) == key and sess.status in (
                SessionStatus.analyzing,
                SessionStatus.awaiting_answers,
                SessionStatus.encoding,
            ):
                return sess
    return None


def create_session(
    scope: ClarificationScope,
    snapshots: dict[str, UserStorySnapshot],
) -> ClarificationSession:
    """Register a fresh `analyzing` session. Raises ValueError if one already
    exists for this scope."""
    existing = active_session_for_scope(scope)
    if existing is not None:
        raise ScopeSessionExistsError(existing.session_id)
    sess = ClarificationSession(scope, snapshots)
    with _STORE_LOCK:
        _SESSIONS[sess.session_id] = sess
    return sess


def get_session(session_id: str) -> Optional[ClarificationSession]:
    with _STORE_LOCK:
        return _SESSIONS.get(session_id)


def all_sessions() -> list[ClarificationSession]:
    with _STORE_LOCK:
        return list(_SESSIONS.values())


class ScopeSessionExistsError(Exception):
    """Raised by `create_session` when the scope already has an active session."""

    def __init__(self, existing_session_id: str):
        super().__init__(f"scope already has active session: {existing_session_id}")
        self.existing_session_id = existing_session_id
