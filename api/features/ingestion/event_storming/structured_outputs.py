"""
Event Storming Structured Outputs

Business capability: wrapper DTOs for LLM structured outputs used by Event Storming nodes.
"""

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field

from .state import (
    AggregateCandidate,
    BoundedContextCandidate,
    CommandCandidate,
    EventCandidate,
    PolicyCandidate,
    ReadModelCandidate,
)


class BoundedContextList(BaseModel):
    """List of Bounded Context candidates."""

    bounded_contexts: List[BoundedContextCandidate] = Field(description="List of identified bounded contexts")


class AggregateList(BaseModel):
    """List of Aggregate candidates."""

    aggregates: List[AggregateCandidate] = Field(description="List of identified aggregates")


class CommandList(BaseModel):
    """List of Command candidates."""

    commands: List[CommandCandidate] = Field(description="List of identified commands")


class EventList(BaseModel):
    """List of Event candidates."""

    events: List[EventCandidate] = Field(description="List of identified events")


class PolicyList(BaseModel):
    """List of Policy candidates."""

    policies: List[PolicyCandidate] = Field(description="List of identified policies")


class ReadModelList(BaseModel):
    """List of ReadModel candidates."""

    readmodels: List[ReadModelCandidate] = Field(description="List of identified read models")


# =============================================================================
# Property generation (Phase 1)
# =============================================================================


class PropertyCandidate(BaseModel):
    """
    A Property (field) owned by exactly one parent node (Aggregate|Command|Event|ReadModel).

    NOTE:
    - `name` will be server-normalized to camelCase.
    - `fkTargetHint` is optional, but recommended when isForeignKey=true.
    - `displayName` is the UI label in the chosen language (e.g. '주문 번호' or 'Order ID').
    """

    name: str = Field(..., description="Property name in camelCase. Identifiers MUST be `id` or `xxxId`.")
    displayName: Optional[str] = Field(default=None, description="UI label in chosen language (e.g. '주문 번호' or 'Order ID').")
    type: str = Field(..., description="Java type string (e.g., String, UUID, int, BigDecimal, LocalDateTime, List<String>).")
    description: str = Field(default="", description="Short, domain-oriented description. Empty string allowed.")
    isKey: bool = Field(default=False, description="True if this is a key/identifier field for the parent object.")
    isForeignKey: bool = Field(default=False, description="True if this identifier references another entity by id.")
    isRequired: bool = Field(default=False, description="True if the field must be provided / non-null.")
    fkTargetHint: Optional[str] = Field(
        default=None,
        description="Optional FK hint for Phase 2 REFERENCES creation. Format: `<TargetType>:<TargetKey>:<TargetPropertyName>`.",
    )


class ParentProperties(BaseModel):
    """
    Properties for a single parent (identified by parentType + parentKey).
    """

    parentType: str = Field(..., description="One of: Aggregate|Command|Event|ReadModel")
    parentKey: str = Field(..., description="Natural key of the parent node (Neo4j `key`).")
    properties: List[PropertyCandidate] = Field(default_factory=list, description="List of properties for the parent.")


class PropertyBatch(BaseModel):
    """Batch output: properties grouped by parent."""

    parents: List[ParentProperties] = Field(default_factory=list, description="Parent -> properties mapping.")


