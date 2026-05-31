"""Requirements Tab Contracts (DTOs) — 026 requirements-tab.

Pydantic request/response models for the `/api/requirements` API.
See specs/026-requirements-tab/data-model.md §2 and contracts/rest-api.md.
"""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field

# ── GenerationWarning codes — natural-language requirement decomposition ──
# String constants (not an enum) so they survive JSON serialization as-is.
REQUIREMENT_WARNING_CODES: tuple[str, ...] = (
    "requirement_unclear",   # NL input too vague to decompose into a user story
    "bc_unresolved",         # BC auto-classification failed → unassigned
    "feature_unresolved",    # Feature auto-classification failed → unassigned
)


class GenerationWarning(BaseModel):
    """A non-fatal warning surfaced during requirement decomposition."""

    code: str
    message: str


# ── Tree DTOs (GET /api/requirements/tree) ───────────────────────────────


class AcceptanceCriterionDTO(BaseModel):
    kind: Literal["given", "when", "then"]
    name: str
    description: Optional[str] = None


class UserStoryNodeDTO(BaseModel):
    id: str
    role: str = ""
    action: str = ""
    benefit: str = ""
    priority: str = "medium"
    status: str = "draft"
    commandId: Optional[str] = None
    commandName: Optional[str] = None
    acceptanceCriteria: list[AcceptanceCriterionDTO] = Field(default_factory=list)


class FeatureNodeDTO(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    source: str = "llm"
    boundedContextId: Optional[str] = None
    # 034 — Feature = 하나의 speckit spec.md. 부가 spec 정보를 노드에 보관.
    edgeCases: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    userStories: list[UserStoryNodeDTO] = Field(default_factory=list)


class EpicNodeDTO(BaseModel):
    id: str  # = BoundedContext id
    name: str
    displayName: Optional[str] = None
    description: Optional[str] = None
    features: list[FeatureNodeDTO] = Field(default_factory=list)
    # User stories assigned to this BC but to no Feature.
    unassignedFeature: Optional[FeatureNodeDTO] = None


class RequirementsTreeDTO(BaseModel):
    epics: list[EpicNodeDTO] = Field(default_factory=list)
    # User stories with no BC at all.
    unassigned: list[UserStoryNodeDTO] = Field(default_factory=list)


# ── Feature CRUD ─────────────────────────────────────────────────────────


class FeatureCreateRequest(BaseModel):
    boundedContextId: str
    name: str
    description: Optional[str] = None


class FeatureCreateResponse(BaseModel):
    feature: FeatureNodeDTO


class FeatureDeleteRequest(BaseModel):
    featureId: str
    userStoryDisposition: Literal["unassign", "delete"] = "unassign"
    # 034 — when true, also remove design elements that *only* this requirement
    # implements (proposed via the existing change-plan HITL flow). Default off.
    removeDesign: bool = False


class FeatureDeleteResponse(BaseModel):
    deleted: bool
    affectedUserStoryIds: list[str] = Field(default_factory=list)
    impactReportId: Optional[str] = None
    # 034 — DeletionRecord batch id for later recovery (option B snapshot).
    restoreBatchId: Optional[str] = None


# ── Feature edit (034 — PATCH /feature) ──────────────────────────────────


class FeatureUpdateRequest(BaseModel):
    featureId: str
    # Either field may be omitted to leave it unchanged. A blank `name` is
    # rejected (422) by the route. Renames preserve the Feature's natural key
    # and its HAS_FEATURE / HAS_USER_STORY relationships.
    name: Optional[str] = None
    description: Optional[str] = None


class FeatureUpdateResponse(BaseModel):
    feature: FeatureNodeDTO


# ── Epic (BoundedContext) create / edit (034) ────────────────────────────
# "Epic" is the existing BoundedContext node (no new label). These routes
# fill the gap where BCs could previously only be created via ingestion.


class BoundedContextDTO(BaseModel):
    id: str
    key: Optional[str] = None
    name: str
    displayName: Optional[str] = None
    description: Optional[str] = None


class BoundedContextCreateRequest(BaseModel):
    name: str
    description: Optional[str] = None


class BoundedContextCreateResponse(BaseModel):
    boundedContext: BoundedContextDTO


class BoundedContextUpdateRequest(BaseModel):
    boundedContextId: str
    name: Optional[str] = None
    description: Optional[str] = None


class BoundedContextUpdateResponse(BaseModel):
    boundedContext: BoundedContextDTO


# ── 설계 미반영 User Story 식별 (034 — US7) ──────────────────────────────
# 설계(IMPLEMENTS→Command)가 없는 User Story = "설계 미반영". Event Modeling /
# Design 탭 진입 시 식별해 설계 반영 프롬프트의 대상으로 삼는다.


class PendingUS(BaseModel):
    userStoryId: str
    role: str = ""
    action: str = ""
    benefit: str = ""
    featureId: Optional[str] = None
    boundedContextId: Optional[str] = None


class PendingDesignResponse(BaseModel):
    pending: list[PendingUS] = Field(default_factory=list)



# ── 설계 커버리지 검증·복구 (034 — 인제스천 사후 검증) ────────────────────
# 인제스천이 US→Command/ReadModel IMPLEMENTS 링크를 일부 누락(특히 조회성 US는
# ReadModel 링크가 통째로 비는 문제)하므로, 사후에 누락 US를 기존 Command(액션)/
# ReadModel(조회)에 매핑해 링크하고, 남은 진짜 공백을 리포트한다.


class CoverageBC(BaseModel):
    boundedContextId: str
    name: str
    totalUS: int = 0
    orphanUS: int = 0          # 어떤 behavioral 설계객체에도 안 붙은 US 수
    orphanSample: list[str] = Field(default_factory=list)


class CoverageReport(BaseModel):
    bcs: list[CoverageBC] = Field(default_factory=list)
    totalOrphan: int = 0


class ReconcileRequest(BaseModel):
    boundedContextId: Optional[str] = None  # None이면 전체 BC
    dryRun: bool = False


class ReconcileResult(BaseModel):
    boundedContextId: str
    name: str
    orphanBefore: int = 0
    linkedToCommand: int = 0
    linkedToReadModel: int = 0
    unmapped: int = 0           # 적합한 기존 객체가 없어 못 붙인(진짜 공백)
    notes: list[str] = Field(default_factory=list)


class ReconcileResponse(BaseModel):
    results: list[ReconcileResult] = Field(default_factory=list)
    totalLinked: int = 0
    totalUnmapped: int = 0


# ── Epic / Feature AI 제안 (034 — US1) ───────────────────────────────────
# 자연어 설명 → LLM 후보 제안(미확정). 확정은 기존 create 경로 재사용.


class EpicProposal(BaseModel):
    name: str
    description: Optional[str] = None


class EpicProposeRequest(BaseModel):
    text: str


class EpicProposeResponse(BaseModel):
    proposals: list[EpicProposal] = Field(default_factory=list)


class FeatureProposal(BaseModel):
    name: str
    description: Optional[str] = None
    boundedContextId: Optional[str] = None


class FeatureProposeRequest(BaseModel):
    text: str
    boundedContextId: Optional[str] = None


class FeatureProposeResponse(BaseModel):
    proposals: list[FeatureProposal] = Field(default_factory=list)


# ── Child User Story auto-generation (034 — US5) ─────────────────────────
# Generate candidate User Stories for an Epic/Feature via the in-process LLM,
# proposed first (HITL) and persisted only on confirm. No new node types.


class GeneratedStory(BaseModel):
    role: str = ""
    action: str = ""
    benefit: str = ""
    acceptanceCriteria: list[str] = Field(default_factory=list)


# ── Epic → Feature(spec.md) 자동 생성 (034) ──────────────────────────────
# Epic 아래는 US를 바로 만들지 않고 Feature부터 만든다. 각 Feature = 하나의
# speckit spec.md(= US들 + edge cases + 핵심 가정). deepagents로 speckit-specify
# 방법론을 실행해 생성한다(clarification과 동일 패턴).


class GeneratedFeature(BaseModel):
    name: str
    description: str = ""
    edgeCases: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    conflicts: list[str] = Field(default_factory=list)
    userStories: list[GeneratedStory] = Field(default_factory=list)


class GenerateFeaturesResponse(BaseModel):
    boundedContextId: str
    features: list[GeneratedFeature] = Field(default_factory=list)


class ConfirmFeaturesRequest(BaseModel):
    boundedContextId: str
    features: list[GeneratedFeature] = Field(default_factory=list)


class ConfirmFeaturesResponse(BaseModel):
    created: list[FeatureNodeDTO] = Field(default_factory=list)


class GenerateChildStoriesResponse(BaseModel):
    scopeType: Literal["epic", "feature"]
    scopeId: str
    boundedContextId: Optional[str] = None
    featureId: Optional[str] = None
    proposals: list[GeneratedStory] = Field(default_factory=list)


class ConfirmChildStoriesRequest(BaseModel):
    boundedContextId: str
    featureId: Optional[str] = None
    stories: list[GeneratedStory] = Field(default_factory=list)


class ConfirmChildStoriesResponse(BaseModel):
    created: list[UserStoryNodeDTO] = Field(default_factory=list)


class LocalToolingStatus(BaseModel):
    """로컬 Claude IDE + speckit 설치 상태 (034 US5 — claude-ide 엔진)."""

    claudeInstalled: bool = False
    speckitInstalled: bool = False
    missing: list[str] = Field(default_factory=list)
    installHint: str = ""


# ── DDD 적합성·입도·정합성 검증 (034 — US6) ──────────────────────────────
# 추가/생성되는 요구사항이 올바른 BC에 적정 입도로 들어가는지, 기존 요구사항과
# 충돌하는지 in-process LLM이 검증하고 비차단 교정안을 제안한다.


class CorrectionProposal(BaseModel):
    # replace_bc | split | merge | differentiate | none
    action: str = "none"
    details: Optional[str] = None
    suggestedBoundedContextId: Optional[str] = None


class ValidationFinding(BaseModel):
    # wrong_bc | oversized_feature | spec_conflict
    kind: str
    severity: Literal["info", "warning"] = "warning"
    message: str
    affected: list[str] = Field(default_factory=list)
    suggestion: Optional[CorrectionProposal] = None


class ValidateRequest(BaseModel):
    targetType: Literal["epic", "feature", "userStory"]
    name: Optional[str] = None
    description: Optional[str] = None
    role: Optional[str] = None
    action: Optional[str] = None
    benefit: Optional[str] = None
    boundedContextId: Optional[str] = None
    featureId: Optional[str] = None


class ValidateResponse(BaseModel):
    ok: bool = True
    findings: list[ValidationFinding] = Field(default_factory=list)
    source: str = "in-process"


# ── User Story propose / confirm / move / delete ─────────────────────────


class UserStoryProposeRequest(BaseModel):
    text: str
    targetBoundedContextId: Optional[str] = None


class ProposedUserStory(BaseModel):
    role: str = ""
    action: str = ""
    benefit: str = ""
    suggestedBoundedContextId: Optional[str] = None
    suggestedFeatureId: Optional[str] = None
    suggestedFeatureName: Optional[str] = None
    confidence: float = 0.0
    unclear: bool = False


class UserStoryProposeResponse(BaseModel):
    proposals: list[ProposedUserStory] = Field(default_factory=list)
    warnings: list[GenerationWarning] = Field(default_factory=list)


class UserStoryConfirmRequest(BaseModel):
    role: str
    action: str
    benefit: str = ""
    priority: Optional[str] = "medium"
    boundedContextId: Optional[str] = None
    featureId: Optional[str] = None
    # When the planner accepted a proposed feature name that has no node yet.
    newFeatureName: Optional[str] = None


class UserStoryConfirmResponse(BaseModel):
    userStory: UserStoryNodeDTO
    impactReportId: Optional[str] = None


class UserStoryMoveRequest(BaseModel):
    userStoryId: str
    targetFeatureId: str


class UserStoryMoveResponse(BaseModel):
    userStory: UserStoryNodeDTO
    boundedContextChanged: bool = False
    impactReportId: Optional[str] = None


class UserStoryDeleteRequest(BaseModel):
    userStoryId: str
    removeDesign: bool = False


class UserStoryDeleteResponse(BaseModel):
    deleted: bool
    impactReportId: Optional[str] = None
    restoreBatchId: Optional[str] = None


# ── Epic (BoundedContext) delete + deletion history (034) ────────────────


class BoundedContextDeleteRequest(BaseModel):
    boundedContextId: str
    removeDesign: bool = False


class BoundedContextDeleteResponse(BaseModel):
    deleted: bool
    affectedFeatureIds: list[str] = Field(default_factory=list)
    affectedUserStoryIds: list[str] = Field(default_factory=list)
    impactReportId: Optional[str] = None
    restoreBatchId: Optional[str] = None


class DeletionRecordDTO(BaseModel):
    batchId: str
    scope: str  # "epic" | "feature" | "user_story"
    rootLabel: str
    rootName: Optional[str] = None
    actor: Optional[str] = None
    createdAt: str
    restored: bool = False
    nodeCount: int = 0
    relCount: int = 0


class DeletionRecordListResponse(BaseModel):
    records: list[DeletionRecordDTO] = Field(default_factory=list)


class RestoreResponse(BaseModel):
    restored: bool
    nodeCount: int = 0
    relinked: int = 0
    reason: Optional[str] = None


# ── Design trace ─────────────────────────────────────────────────────────


class DesignTraceResponse(BaseModel):
    rootCommandId: Optional[str] = None
    nodes: list[dict] = Field(default_factory=list)
    relationships: list[dict] = Field(default_factory=list)
    empty: bool = False


# ── User Story direct edit (033 — requirement-edit-history) ──────────────


class UserStoryPatchRequest(BaseModel):
    role: Optional[str] = None
    action: Optional[str] = None
    benefit: Optional[str] = None
    priority: Optional[str] = None
    status: Optional[str] = None
    baseUpdatedAt: Optional[str] = None


class UserStoryPatchResponse(BaseModel):
    userStory: UserStoryNodeDTO
    changed: bool
    updatedAt: str


class EditHistoryItemDTO(BaseModel):
    id: str
    timestamp: str
    userName: str
    userEmail: str
    changes: dict
    # 035 — conversational edit attribution (optional; absent on legacy entries)
    source: Optional[str] = None  # "form" | "chat" | "clarification"
    feedback: Optional[str] = None  # the NL feedback that drove a chat edit
    rationale: Optional[str] = None  # the agent's reasoning for the change


class EditHistoryResponse(BaseModel):
    items: list[EditHistoryItemDTO] = Field(default_factory=list)


# ── Conversational (chat) edit — 035 ─────────────────────────────────────
# Per-requirement-item chat: NL feedback → LLM proposes a one-shot edit
# (propose→confirm). The decision (feedback + rationale + diff + actor) is
# saved to the collaborative edit History and a per-item conversation log.


class ChatEditProposal(BaseModel):
    summary: str = ""  # one-line description of the proposed change
    rationale: str = ""  # why the agent proposes it
    fields: dict = Field(default_factory=dict)  # full proposed field values
    conflicts: list[str] = Field(default_factory=list)  # clashes w/ existing reqs


class ChatEditApplyRequest(BaseModel):
    fields: dict = Field(default_factory=dict)
    feedback: str = ""
    rationale: str = ""
    summary: str = ""
    baseUpdatedAt: Optional[str] = None


class ChatEditApplyResponse(BaseModel):
    changed: bool
    updatedAt: Optional[str] = None
    historyId: Optional[str] = None
    changes: dict = Field(default_factory=dict)


class ChatEditLogEntry(BaseModel):
    at: str
    userName: str = "unknown"
    userEmail: str = "unknown"
    feedback: str = ""
    rationale: str = ""
    summary: str = ""
    applied: bool = True
    changes: dict = Field(default_factory=dict)


class ChatEditLogResponse(BaseModel):
    entries: list[ChatEditLogEntry] = Field(default_factory=list)


# ── Impact report ────────────────────────────────────────────────────────


class ImpactFinding(BaseModel):
    kind: Literal["duplicate", "conflict", "design_impact"]
    severity: Literal["info", "warning"] = "warning"
    message: str
    relatedNodeIds: list[str] = Field(default_factory=list)


class ImpactReportDTO(BaseModel):
    id: str
    status: Literal["running", "done", "failed"] = "running"
    trigger: Literal["add", "delete", "move", "edit"] = "add"
    findings: list[ImpactFinding] = Field(default_factory=list)
    createdAt: Optional[str] = None
