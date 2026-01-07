from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field


class UserStoryEdit(BaseModel):
    """Edited user story data."""

    role: str
    action: str
    benefit: Optional[str] = None
    changes: List[dict] = Field(default_factory=list)


class ChangePlanRequest(BaseModel):
    """Request for generating or revising a change plan."""

    userStoryId: str
    originalUserStory: Optional[dict] = None
    editedUserStory: dict
    impactedNodes: List[dict]
    feedback: Optional[str] = None
    previousPlan: Optional[List[dict]] = None


class ChangeItem(BaseModel):
    """A single change in the plan."""

    action: str  # rename, update, create, delete
    targetType: str  # Aggregate, Command, Event, Policy
    targetId: str
    targetName: str
    from_value: Optional[str] = Field(None, alias="from")
    to_value: Optional[str] = Field(None, alias="to")
    description: str
    reason: str


class ChangePlanResponse(BaseModel):
    """Response containing the generated change plan."""

    changes: List[dict]
    summary: str


class VectorSearchRequest(BaseModel):
    """Request for keyword-based related object search."""

    query: str
    nodeTypes: List[str] = Field(default_factory=lambda: ["Command", "Event", "Policy", "Aggregate"])
    excludeIds: List[str] = Field(default_factory=list)
    limit: int = 10


class VectorSearchResult(BaseModel):
    """A single result from keyword-based related object search."""

    id: str
    name: str
    type: str
    bcId: Optional[str] = None
    bcName: Optional[str] = None
    similarity: float
    description: Optional[str] = None


class ApplyChangesRequest(BaseModel):
    """Request to apply approved changes."""

    userStoryId: str
    editedUserStory: dict
    changePlan: List[dict]


class ApplyChangesResponse(BaseModel):
    """Response after applying changes."""

    success: bool
    appliedChanges: List[dict]
    errors: List[str] = Field(default_factory=list)


