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


class FeatureDeleteResponse(BaseModel):
    deleted: bool
    affectedUserStoryIds: list[str] = Field(default_factory=list)
    impactReportId: Optional[str] = None


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


class DesignReflectRequest(BaseModel):
    userStoryIds: list[str] = Field(default_factory=list)


class ReflectedDesign(BaseModel):
    userStoryId: str
    boundedContextId: Optional[str] = None
    aggregateName: Optional[str] = None
    commandName: Optional[str] = None
    eventName: Optional[str] = None
    reusedAggregate: bool = False
    ok: bool = True
    message: Optional[str] = None


class DesignReflectResponse(BaseModel):
    reflected: list[ReflectedDesign] = Field(default_factory=list)


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


class UserStoryDeleteResponse(BaseModel):
    deleted: bool
    impactReportId: Optional[str] = None


# ── Design trace ─────────────────────────────────────────────────────────


class DesignTraceResponse(BaseModel):
    rootCommandId: Optional[str] = None
    nodes: list[dict] = Field(default_factory=list)
    relationships: list[dict] = Field(default_factory=list)
    empty: bool = False


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
