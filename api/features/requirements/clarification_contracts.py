"""Clarification Agent Contracts (DTOs) — 030 requirements-clarify-agent.

Pydantic request/response models for the `/api/requirements/clarification/*`
API and the in-memory session state machine. See
specs/030-requirements-clarify-agent/data-model.md and contracts/rest-and-agent.md.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field

# ── Enumerations (data-model §2) ─────────────────────────────────────────


class AmbiguityCategory(str, Enum):
    functional_scope = "functional_scope"
    domain_data_model = "domain_data_model"
    interaction_flow = "interaction_flow"
    non_functional = "non_functional"
    integration_dependencies = "integration_dependencies"
    edge_cases = "edge_cases"
    terminology = "terminology"
    completion_signals = "completion_signals"


class ScopeType(str, Enum):
    project = "project"
    bounded_context = "bounded_context"
    feature = "feature"


class SessionStatus(str, Enum):
    analyzing = "analyzing"
    awaiting_answers = "awaiting_answers"
    encoding = "encoding"
    completed = "completed"
    discarded = "discarded"
    failed = "failed"


class QuestionStatus(str, Enum):
    pending = "pending"
    answered = "answered"
    applied = "applied"
    skipped = "skipped"


class QuestionType(str, Enum):
    closed = "closed"
    short_answer = "short_answer"


class CoverageStatus(str, Enum):
    resolved = "resolved"
    deferred = "deferred"
    clear = "clear"
    outstanding = "outstanding"


# ── Scope ────────────────────────────────────────────────────────────────


class ClarificationScope(BaseModel):
    scopeType: ScopeType
    scopeId: str
    scopeName: str = ""


# ── Question ─────────────────────────────────────────────────────────────


class QuestionOption(BaseModel):
    key: str
    label: str


class ClarificationQuestionDTO(BaseModel):
    questionId: str
    order: int = 1
    category: AmbiguityCategory
    priority: int = 1
    questionType: QuestionType
    questionText: str
    referencedRequirementIds: list[str] = Field(default_factory=list)
    recommendedAnswer: str = ""
    options: list[QuestionOption] = Field(default_factory=list)
    status: QuestionStatus = QuestionStatus.pending


# ── Session ──────────────────────────────────────────────────────────────


class SessionProgress(BaseModel):
    phase: str = "loading_scope"
    message: str = ""
    questionsTotal: int = 0
    questionsAnswered: int = 0
    currentQuestionIndex: int = 0


class ClarificationSessionDTO(BaseModel):
    sessionId: str
    scope: ClarificationScope
    status: SessionStatus
    progress: SessionProgress = Field(default_factory=SessionProgress)
    questions: list[ClarificationQuestionDTO] = Field(default_factory=list)
    noAmbiguities: bool = False
    deferredNote: Optional[str] = None
    createdAt: Optional[str] = None
    endedAt: Optional[str] = None


class StartSessionRequest(BaseModel):
    scopeType: ScopeType
    scopeId: str


# ── Answer / Proposal / Apply ────────────────────────────────────────────


class AnswerRequest(BaseModel):
    questionId: str
    mode: Literal["option", "recommended", "free_text", "skip"]
    optionKey: Optional[str] = None
    text: Optional[str] = None


class UserStorySnapshot(BaseModel):
    role: str = ""
    action: str = ""
    benefit: str = ""
    priority: str = "medium"
    status: str = "draft"
    acceptanceCriteria: list[str] = Field(default_factory=list)


class RequirementEdit(BaseModel):
    requirementId: str
    baseUpdatedAt: Optional[str] = None
    before: UserStorySnapshot
    after: UserStorySnapshot
    fieldsSummary: str = ""


class RequirementEditProposal(BaseModel):
    questionId: str
    finalAnswer: str = ""
    edits: list[RequirementEdit] = Field(default_factory=list)
    needsDisambiguation: bool = False
    disambiguationPrompt: Optional[str] = None


class ApplyRequest(BaseModel):
    questionId: str


class EditConflict(BaseModel):
    requirementId: str
    latestUpdatedAt: Optional[str] = None
    message: str = ""


class ApplyResponse(BaseModel):
    appliedRequirementIds: list[str] = Field(default_factory=list)
    impactReportIds: list[str] = Field(default_factory=list)
    conflict: Optional[EditConflict] = None
    noOp: bool = False


# ── Summary / Coverage / Revert ──────────────────────────────────────────


class ChangedRequirement(BaseModel):
    requirementId: str
    requirementLabel: str = ""
    questionId: str
    before: UserStorySnapshot
    after: UserStorySnapshot


class CoverageRow(BaseModel):
    category: AmbiguityCategory
    status: CoverageStatus


class ClarificationSummaryDTO(BaseModel):
    sessionId: str
    changedRequirements: list[ChangedRequirement] = Field(default_factory=list)
    coverage: list[CoverageRow] = Field(default_factory=list)
    questionsAsked: int = 0
    questionsApplied: int = 0
    questionsSkipped: int = 0


class RevertRequest(BaseModel):
    requirementId: str


# ── SSE event ────────────────────────────────────────────────────────────


class ClarificationProgressEvent(BaseModel):
    phase: Literal[
        "loading_scope",
        "scanning",
        "drafting_questions",
        "questions_ready",
        "encoding",
        "edit_ready",
        "completed",
        "error",
    ]
    message: str = ""
    progress: float = 0.0
    data: Optional[dict[str, Any]] = None


# ── Persistent clarification log (UserStory.clarifications JSON entry) ──


class ClarificationLogEntry(BaseModel):
    sessionId: str
    questionId: str
    question: str
    answer: str
    category: AmbiguityCategory
    before: UserStorySnapshot
    after: UserStorySnapshot
    at: str
    reverted: bool = False
    revertedAt: Optional[str] = None


class ClarificationLogResponse(BaseModel):
    scope: ClarificationScope
    entries: list[ClarificationLogEntry] = Field(default_factory=list)
