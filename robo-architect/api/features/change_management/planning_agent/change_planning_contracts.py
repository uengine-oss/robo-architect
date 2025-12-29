"""
Change Planning Contracts (State + DTOs)

Business capability: represent change planning workflow state and returned plan items.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class ChangeScope(str, Enum):
    """Scope of the change impact."""

    LOCAL = "local"  # Can be resolved within existing connections
    CROSS_BC = "cross_bc"  # Requires connections to other BCs
    NEW_CAPABILITY = "new_capability"  # Requires entirely new objects


class ChangePlanningPhase(str, Enum):
    """Current phase of change planning."""

    INIT = "init"
    ANALYZE_SCOPE = "analyze_scope"
    PROPAGATE_IMPACTS = "propagate_impacts"
    SEARCH_RELATED = "search_related"
    GENERATE_PLAN = "generate_plan"
    AWAIT_APPROVAL = "await_approval"
    REVISE_PLAN = "revise_plan"
    APPLY_CHANGES = "apply_changes"
    COMPLETE = "complete"


class ProposedChange(BaseModel):
    """A single proposed change."""

    action: str  # create, update, connect, rename
    targetType: str  # Aggregate, Command, Event, Policy
    targetId: str
    targetName: str
    targetBcId: Optional[str] = None
    targetBcName: Optional[str] = None
    description: str
    reason: str
    from_value: Optional[str] = None
    to_value: Optional[str] = None
    connectionType: Optional[str] = None  # TRIGGERS, INVOKES, etc.
    sourceId: Optional[str] = None  # For connections


class RelatedObject(BaseModel):
    """An object found via vector search."""

    id: str
    name: str
    type: str  # Aggregate, Command, Event, Policy
    bcId: Optional[str] = None
    bcName: Optional[str] = None
    similarity: float
    description: Optional[str] = None


class PropagationCandidate(BaseModel):
    """
    A candidate node identified by propagation as potentially impacted by the change.
    """

    id: str
    type: str
    name: str
    bcId: Optional[str] = None
    bcName: Optional[str] = None
    confidence: float = 0.0
    reason: str = ""
    evidence_paths: List[str] = Field(default_factory=list)
    suggested_change_type: str = "unknown"  # rename/update/create/connect/delete/unknown
    round: int = 0  # Which round this candidate was identified in (0 = seed)


class ChangePlanningState(BaseModel):
    """State for the change planning workflow."""

    # Input
    user_story_id: str = ""
    original_user_story: Dict[str, Any] = Field(default_factory=dict)
    edited_user_story: Dict[str, Any] = Field(default_factory=dict)
    change_description: str = ""  # What changed

    # Connected objects (from existing relationships)
    connected_objects: List[Dict[str, Any]] = Field(default_factory=list)

    # Propagation (iterative impact expansion)
    propagation_enabled: bool = True
    propagation_confirmed: List[PropagationCandidate] = Field(default_factory=list)
    propagation_review: List[PropagationCandidate] = Field(default_factory=list)
    propagation_rounds: int = 0
    propagation_stop_reason: str = ""
    propagation_debug: Dict[str, Any] = Field(default_factory=dict)

    # Analysis results
    phase: ChangePlanningPhase = ChangePlanningPhase.INIT
    change_scope: Optional[ChangeScope] = None
    scope_reasoning: str = ""
    keywords_to_search: List[str] = Field(default_factory=list)

    # Vector search results
    related_objects: List[RelatedObject] = Field(default_factory=list)

    # Generated plan
    proposed_changes: List[ProposedChange] = Field(default_factory=list)
    plan_summary: str = ""

    # Human-in-the-loop
    awaiting_approval: bool = False
    human_feedback: Optional[str] = None
    revision_count: int = 0

    # Results
    applied_changes: List[Dict[str, Any]] = Field(default_factory=list)
    error: Optional[str] = None

    class Config:
        arbitrary_types_allowed = True


