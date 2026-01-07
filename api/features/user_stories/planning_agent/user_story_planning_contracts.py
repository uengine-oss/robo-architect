from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class PlanningScope(str, Enum):
    EXISTING_BC = "existing_bc"
    NEW_BC = "new_bc"
    CROSS_BC = "cross_bc"


class ProposedObject(BaseModel):
    action: str = "create"  # create, update, connect
    targetType: str
    targetId: str
    targetName: str
    targetBcId: Optional[str] = None
    targetBcName: Optional[str] = None
    description: str = ""
    reason: str = ""
    connectionType: Optional[str] = None
    sourceId: Optional[str] = None
    actor: Optional[str] = None
    aggregateId: Optional[str] = None
    commandId: Optional[str] = None


class UserStoryPlanningState(BaseModel):
    # Input
    role: str = ""
    action: str = ""
    benefit: str = ""
    target_bc_id: Optional[str] = None
    auto_generate: bool = True

    # Analysis results
    story_intent: str = ""
    domain_keywords: List[str] = Field(default_factory=list)
    action_verbs: List[str] = Field(default_factory=list)

    # BC matching
    scope: PlanningScope = PlanningScope.EXISTING_BC
    scope_reasoning: str = ""
    matched_bc_id: Optional[str] = None
    matched_bc_name: Optional[str] = None

    # Related objects found
    related_objects: List[Dict[str, Any]] = Field(default_factory=list)

    # Generated plan
    proposed_objects: List[ProposedObject] = Field(default_factory=list)
    plan_summary: str = ""

    # Error
    error: Optional[str] = None

    class Config:
        arbitrary_types_allowed = True


