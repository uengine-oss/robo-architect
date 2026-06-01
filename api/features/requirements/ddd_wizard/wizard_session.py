"""마법사 세션 in-process 저장소 + 상태머신 (035 — US1).

clarification_session.py와 동일한 패턴: 그래프가 진실의 원천이고 이 저장소는
휘발성 세션 상태(프로파일, 단계 계획, 완료 단계, 단계별 답변/제안)만 보관한다.

상태머신:
    profiling → step_running → awaiting_answers → proposing → confirmed(단계 반복)
              ↘ discarded / failed
"""

from __future__ import annotations

import threading
import uuid
from typing import Optional

from api.features.requirements.requirements_contracts import (
    ProfileAnswer,
    WizardProposal,
    WizardSessionDTO,
    WizardStepRef,
)


class WizardSession:
    def __init__(
        self,
        *,
        scope: str,
        epic_id: Optional[str],
        profile: ProfileAnswer,
        plan: list[WizardStepRef],
        engine: str,
    ):
        self.session_id: str = str(uuid.uuid4())
        self.scope: str = scope
        self.epic_id: Optional[str] = epic_id
        self.profile: ProfileAnswer = profile
        self.plan: list[WizardStepRef] = plan
        self.engine: str = engine
        self.phase: str = "profiling"
        self.completed_steps: list[str] = []
        # 단계별 사용자 답변/붙여넣은 문서/마지막 제안 보관(재개용).
        self.answers: dict[str, dict] = {}
        self.documents: dict[str, str] = {}
        self.proposals: dict[str, WizardProposal] = {}

    def record_answer(self, step_key: str, answers: dict, document: Optional[str]) -> None:
        self.answers[step_key] = answers or {}
        if document:
            self.documents[step_key] = document
        self.phase = "proposing"

    def record_proposal(self, proposal: WizardProposal) -> None:
        self.proposals[proposal.stepKey] = proposal
        self.phase = "awaiting_answers"

    def mark_confirmed(self, step_key: str) -> None:
        if step_key not in self.completed_steps:
            self.completed_steps.append(step_key)
        self.phase = "confirmed" if len(self.completed_steps) >= len(self.plan) else "step_running"

    def to_dto(self) -> WizardSessionDTO:
        return WizardSessionDTO(
            sessionId=self.session_id,
            scope=self.scope,  # type: ignore[arg-type]
            epicId=self.epic_id,
            phase=self.phase,
            plan=list(self.plan),
            completedSteps=list(self.completed_steps),
            engine=self.engine,
        )


_SESSIONS: dict[str, WizardSession] = {}
_LOCK = threading.Lock()


def create_session(**kwargs) -> WizardSession:
    sess = WizardSession(**kwargs)
    with _LOCK:
        _SESSIONS[sess.session_id] = sess
    return sess


def get_session(session_id: str) -> Optional[WizardSession]:
    with _LOCK:
        return _SESSIONS.get(session_id)


def all_sessions() -> list[WizardSession]:
    with _LOCK:
        return list(_SESSIONS.values())
