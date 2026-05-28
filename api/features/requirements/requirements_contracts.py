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
    userStories: list[UserStoryNodeDTO] = Field(default_factory=list)


class EpicNodeDTO(BaseModel):
    id: str  # = BoundedContext id
    name: str
    displayName: Optional[str] = None
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
