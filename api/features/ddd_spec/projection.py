"""Internal read-side projection types populated by ``repository.py`` and
consumed by ``renderers/*``. None of these shapes are persisted.

Mirrors ``specs/022-spec-generation-from-event-storming/data-model.md`` §1.
"""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field


class StrategicClassification(BaseModel):
    domain_type: Optional[Literal["Core", "Supporting", "Generic"]] = None
    business_model: Optional[str] = None
    evolution: Optional[str] = None


class AggregateAttribute(BaseModel):
    name: str
    type: str
    mutability: str
    description: Optional[str] = None


class MemberEntity(BaseModel):
    name: str
    kind: Literal["entity", "value_object", "enum", "identifier"]
    note: Optional[str] = None


class GwtCriterion(BaseModel):
    id: str
    given: list[str] = Field(default_factory=list)
    when: str = ""
    then: list[str] = Field(default_factory=list)


class CommandProjection(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    preconditions: list[str] = Field(default_factory=list)
    postconditions: list[str] = Field(default_factory=list)
    events_emitted: list[str] = Field(default_factory=list)
    gwt: list[GwtCriterion] = Field(default_factory=list)
    user_story_ids: list[str] = Field(default_factory=list)


class EventProjection(BaseModel):
    id: str
    name: str
    description: Optional[str] = None


class PolicyProjection(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    effect: Optional[str] = None


class ReadModelProjection(BaseModel):
    id: str
    name: str
    description: Optional[str] = None


class WireframeProjection(BaseModel):
    ui_id: str
    name: str
    slug: str
    scene_graph_json: Optional[str] = None
    template: Optional[str] = None
    attached_to_type: Optional[Literal["Command", "ReadModel"]] = None
    attached_to_name: Optional[str] = None
    actor: Optional[str] = None


class UserStoryProjection(BaseModel):
    id: str
    title: str
    narrative: str = ""
    priority: Optional[Literal["P1", "P2", "P3", "P4", "P5"]] = None
    aggregate_id: Optional[str] = None
    acceptance_criteria: list[GwtCriterion] = Field(default_factory=list)
    wireframes: list[WireframeProjection] = Field(default_factory=list)


class AggregateProjection(BaseModel):
    id: str
    name: str
    slug: str
    description: Optional[str] = None
    root_entity: str
    member_entities: list[MemberEntity] = Field(default_factory=list)
    attributes: list[AggregateAttribute] = Field(default_factory=list)
    invariants: list[str] = Field(default_factory=list)
    commands: list[CommandProjection] = Field(default_factory=list)
    events: list[EventProjection] = Field(default_factory=list)
    policies: list[PolicyProjection] = Field(default_factory=list)
    read_models: list[ReadModelProjection] = Field(default_factory=list)
    identity_type: str = ""


class ExternalIntegrationProjection(BaseModel):
    id: str
    external_system_name: str
    slug: str
    direction: Literal["inbound", "outbound", "bidirectional"]
    our_concepts: list[str] = Field(default_factory=list)
    external_concepts: list[str] = Field(default_factory=list)
    # Tuple-as-list of (external_field, our_field, translation).
    inbound_field_map: list[tuple[str, str, str]] = Field(default_factory=list)
    outbound_call_map: list[tuple[str, str, str]] = Field(default_factory=list)
    error_map: list[tuple[str, str]] = Field(default_factory=list)
    forbidden_concepts: list[str] = Field(default_factory=list)


class CrossBcFlow(BaseModel):
    from_bc_id: str
    from_bc_name: str
    to_bc_id: str
    to_bc_name: str
    channel: str = "Event bus"
    message: str = ""
    recorded_pattern: Optional[str] = None


class BoundedContextProjection(BaseModel):
    id: str
    name: str
    slug: str
    description: Optional[str] = None
    purpose: Optional[str] = None
    strategic: Optional[StrategicClassification] = None
    aggregates: list[AggregateProjection] = Field(default_factory=list)
    user_stories: list[UserStoryProjection] = Field(default_factory=list)
    external_integrations: list[ExternalIntegrationProjection] = Field(default_factory=list)
    inbound_flows: list[CrossBcFlow] = Field(default_factory=list)
    outbound_flows: list[CrossBcFlow] = Field(default_factory=list)
    key_terms: list[str] = Field(default_factory=list)


# --- Frontend perspective (US5, data-model.md §6.1) -----------------------


class FrameworkConventions(BaseModel):
    """Convention bundle for one frontend framework. Drives ``framework.md``
    rendering. Looked up by framework value verbatim in the catalog; absence
    of an entry triggers the ``frontend_framework_unsupported`` warning.
    """

    framework: str
    component_file_shape: str
    state_default: str
    routing_default: str
    styling_default: str


class TriggerOrigin(BaseModel):
    """How the user arrived at a UI screen in the causal flow."""

    kind: Literal["event", "story_internal", "entry_point"]
    event_name: Optional[str] = None
    from_bounded_context_id: Optional[str] = None
    from_user_story_id: Optional[str] = None


class UIFlowEntry(BaseModel):
    """One screen in ``specs/frontend/ui-flow.md``."""

    position: int
    bounded_context_id: str
    bounded_context_slug: str
    user_story_id: str
    user_story_title: str
    wireframe_ui_id: str
    wireframe_slug: str
    triggered_by: Optional[TriggerOrigin] = None
    is_unreferenced: bool = False


class MenuEntry(BaseModel):
    """One bound UI surfaced as a **hint** for the frontend-engineer agent
    in ``specs/frontend/menu-structure.md``.

    The menu IA is NOT decided here — this is a flat inventory the agent
    reads alongside ``ui-flow.md`` so it can design routes/groupings
    that follow the user's workflow (the event-modeling flow), not BC
    boundaries. BC fields below are for traceability only.

    Entry-point markers (``is_entry_point``) tell the agent which UIs
    start a flow; unreferenced markers (``is_unreferenced``) tell it
    which UIs need user confirmation before placement.
    """

    bc_id: str
    bc_slug: str
    bc_name: str
    user_story_id: str
    user_story_title: str
    wireframe_slug: str
    wireframe_name: str
    actor: Optional[str] = None
    attached_to_type: Optional[Literal["Command", "ReadModel"]] = None
    attached_to_name: Optional[str] = None
    is_entry_point: bool = False
    is_unreferenced: bool = False


class FrontendCompositionProjection(BaseModel):
    """Top-level projection passed to the frontend renderer."""

    framework: str
    framework_conventions: Optional[FrameworkConventions] = None
    bounded_contexts: list[BoundedContextProjection] = Field(default_factory=list)
    menu: list[MenuEntry] = Field(default_factory=list)
    ui_flow: list[UIFlowEntry] = Field(default_factory=list)
    unreferenced_uis: list[UIFlowEntry] = Field(default_factory=list)
    # Pairs of ``(from_node_key, to_node_key)`` removed to break cycles.
    cycle_broken_edges: list[tuple[str, str]] = Field(default_factory=list)


