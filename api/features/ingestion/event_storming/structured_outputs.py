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


# ============================================================================
# UI Flow derivation (spec 025) — LLM extracts user-journey transitions
# (NEXT_UI edges) + branching decision points (Gateway nodes) from the
# source document, binding to existing UI nodes by name.
# ============================================================================


class UIFlowGatewayItem(BaseModel):
    """LLM-emitted gateway specification before id/key resolution."""

    label: str = Field(..., min_length=1, description="Decision question shown in the diamond, e.g. '주문 승인?'.")
    kind: str = Field(default="exclusive", description="One of 'exclusive', 'parallel', 'inclusive'. v1 downgrades non-exclusive to exclusive.")
    bounded_context_name: str = Field(..., description="BC name this gateway belongs to; resolved to BC id server-side.")


class UIFlowEdgeItem(BaseModel):
    """LLM-emitted NEXT_UI edge before id/key resolution."""

    source_name: str = Field(..., description="UI displayName or Gateway label that starts this transition.")
    source_kind: str = Field(default="ui", description="'ui' or 'gateway'.")
    target_name: str = Field(..., description="UI displayName or Gateway label that the transition leads to.")
    target_kind: str = Field(default="ui", description="'ui' or 'gateway'.")
    condition: str = Field(default="", description="Branch label (required when source_kind='gateway').")
    document_excerpt: str = Field(default="", description="Snippet of source text that motivated this edge (≤500 chars; server truncates).")


class UIFlowJourney(BaseModel):
    """spec 025 v2 — one purpose-driven user journey.

    A journey is a single coherent flow with a goal (e.g. '정상 회원가입',
    '미성년자 가입', '회원 탈퇴'). Screens reused across journeys appear in
    each journey's own edge set — journeys are NOT merged by shared screens.
    """

    name: str = Field(..., min_length=1, description="Short journey name describing its purpose/goal.")
    description: str = Field(default="", description="One-line description of the journey's goal.")
    gateways: List[UIFlowGatewayItem] = Field(default_factory=list, description="Decision points within THIS journey.")
    edges: List[UIFlowEdgeItem] = Field(default_factory=list, description="Screen transitions within THIS journey, in flow order.")


class UIFlowDerivation(BaseModel):
    """Top-level LLM output for the UI-flow ingestion phase (spec 025 v2).

    Output is grouped into named journeys so a reused screen does not collapse
    distinct flows into one blob.
    """

    journeys: List[UIFlowJourney] = Field(default_factory=list)
    unresolved: List[str] = Field(
        default_factory=list,
        description="Screen names the LLM saw in the text but couldn't bind to any UI in the catalog.",
    )

