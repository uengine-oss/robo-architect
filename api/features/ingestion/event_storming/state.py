"""
LangGraph State Definitions for Event Storming Workflow

The workflow processes User Stories one by one, building out:
1. Bounded Context candidates
2. Aggregates within each BC
3. Commands within each Aggregate
4. Events emitted by Commands
5. Policies for cross-BC communication

State is designed to work within LLM context limits by processing
user stories incrementally rather than all at once.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Annotated, Any, Optional, List, Dict

from langgraph.graph.message import add_messages
from pydantic import BaseModel, Field


class WorkflowPhase(str, Enum):
    """Current phase of the Event Storming workflow."""

    INIT = "init"
    LOAD_USER_STORIES = "load_user_stories"
    SELECT_USER_STORY = "select_user_story"
    IDENTIFY_BC = "identify_bc"
    APPROVE_BC = "approve_bc"  # Human-in-the-loop
    BREAKDOWN_USER_STORY = "breakdown_user_story"
    EXTRACT_AGGREGATES = "extract_aggregates"
    APPROVE_AGGREGATES = "approve_aggregates"  # Human-in-the-loop
    EXTRACT_COMMANDS = "extract_commands"
    EXTRACT_EVENTS = "extract_events"
    IDENTIFY_POLICIES = "identify_policies"
    APPROVE_POLICIES = "approve_policies"  # Human-in-the-loop
    GENERATE_GWT = "generate_gwt"
    SAVE_TO_GRAPH = "save_to_graph"
    COMPLETE = "complete"


# =============================================================================
# Pydantic Models for LLM Structured Output
# =============================================================================


class BoundedContextCandidate(BaseModel):
    """A candidate Bounded Context identified from User Stories."""

    # NOTE: UUID + natural key are generated/normalized on the server side.
    # LLM may omit both; ingestion will compute key from name and persist with UUID id.
    id: Optional[str] = Field(default=None, description="Optional UUID (server-generated).")
    key: Optional[str] = Field(default=None, description="Optional natural key (slug).")
    name: str = Field(..., description="Short name like 'Order'")
    displayName: Optional[str] = Field(default=None, description="UI label in chosen language (e.g. '주문 관리' or 'Order Management').")
    description: str = Field(..., description="What this BC is responsible for")
    rationale: str = Field(..., description="Why this should be a separate BC")
    user_story_ids: List[str] = Field(
        ...,
        min_length=1,
        description="REQUIRED: List of User Story IDs that belong to this BC. This field is MANDATORY - every BC MUST have at least one user_story_id. Every user story from the input MUST be assigned to exactly one BC's user_story_ids list."
    )
    domain_type: Optional[str] = Field(
        default=None,
        description="Domain classification: MUST be one of 'Core Domain', 'Supporting Domain', or 'Generic Domain'. This field is required for proper domain modeling."
    )


class EnumerationCandidate(BaseModel):
    """An Enumeration within an Aggregate."""

    name: str = Field(..., description="Enumeration name in PascalCase")
    displayName: Optional[str] = Field(default=None, description="UI label in chosen language (e.g. '주문 상태' or 'Order Status').")
    alias: Optional[str] = Field(default=None, description="Optional alias for display")
    items: List[str] = Field(
        default_factory=list, description="List of enumeration item values (e.g., ['PENDING', 'PROCESSING', 'COMPLETED'])"
    )


class ValueObjectField(BaseModel):
    """A field within a Value Object."""

    name: str = Field(..., description="Field name (e.g., 'street', 'city')")
    type: str = Field(..., description="Field type (e.g., 'String', 'int', 'BigDecimal')")


class ValueObjectCandidate(BaseModel):
    """A Value Object within an Aggregate."""

    name: str = Field(..., description="Value Object name in PascalCase")
    displayName: Optional[str] = Field(default=None, description="UI label in chosen language (e.g. '배송 주소' or 'Shipping Address').")
    alias: Optional[str] = Field(default=None, description="Optional alias for display")
    referenced_aggregate_name: Optional[str] = Field(
        default=None, description="Name of the referenced Aggregate (if this is a reference Value Object)"
    )
    referenced_aggregate_field: Optional[str] = Field(
        default=None, description="Name of the field in the referenced Aggregate that this VO references (if this is a reference Value Object)"
    )
    fields: List[ValueObjectField] = Field(
        default_factory=list, description="List of fields in this value object. Each field has 'name' and 'type' (e.g., [{'name': 'street', 'type': 'String'}, {'name': 'city', 'type': 'String'}])"
    )


class AggregateCandidate(BaseModel):
    """A candidate Aggregate within a Bounded Context."""

    id: Optional[str] = Field(default=None, description="Optional UUID (server-generated).")
    key: Optional[str] = Field(default=None, description="Optional natural key (derived from BC + name).")
    name: str = Field(..., description="Aggregate name like 'Cart'")
    displayName: Optional[str] = Field(default=None, description="UI label in chosen language (e.g. '장바구니' or 'Cart').")
    root_entity: str = Field(..., description="Root entity name")
    invariants: List[str] = Field(
        default_factory=list, description="Business invariants this aggregate enforces"
    )
    description: str = Field(..., description="What this aggregate manages")
    user_story_ids: List[str] = Field(
        default_factory=list, description="User Story IDs that this aggregate implements"
    )
    enumerations: List[EnumerationCandidate] = Field(
        default_factory=list, description="Enumerations associated with this aggregate"
    )
    value_objects: List[ValueObjectCandidate] = Field(
        default_factory=list, description="Value Objects within this aggregate"
    )


class GivenCandidate(BaseModel):
    """A candidate Given (GWT - Given/When/Then) for Command or Policy."""

    id: Optional[str] = Field(default=None, description="Optional UUID (server-generated).")
    key: Optional[str] = Field(default=None, description="Optional natural key.")
    name: str = Field(..., description="Given description (e.g., 'Command: CancelOrder' or 'Event: OrderCancelled')")
    description: Optional[str] = Field(default=None, description="Detailed description of the Given")
    referencedNodeId: Optional[str] = Field(default=None, description="ID of the referenced node (Command or Event)")
    referencedNodeType: Optional[str] = Field(default=None, description="Type of referenced node: 'Command' or 'Event'")
    fieldValues: Dict[str, str] = Field(
        default_factory=dict,
        description="Field values mapped from referenced node's properties. Key is property name, value is the test value for that field."
    )


class WhenCandidate(BaseModel):
    """A candidate When (GWT - Given/When/Then) for Command or Policy."""

    id: Optional[str] = Field(default=None, description="Optional UUID (server-generated).")
    key: Optional[str] = Field(default=None, description="Optional natural key.")
    name: str = Field(..., description="When description (e.g., 'Aggregate: Order')")
    description: Optional[str] = Field(default=None, description="Detailed description of the When")
    referencedNodeId: Optional[str] = Field(default=None, description="ID of the referenced Aggregate")
    referencedNodeType: Optional[str] = Field(default="Aggregate", description="Type of referenced node (always 'Aggregate')")
    fieldValues: Dict[str, str] = Field(
        default_factory=dict,
        description="Field values mapped from referenced Aggregate's properties. Key is property name, value is the test value for that field."
    )


class ThenCandidate(BaseModel):
    """A candidate Then (GWT - Given/When/Then) for Command or Policy."""

    id: Optional[str] = Field(default=None, description="Optional UUID (server-generated).")
    key: Optional[str] = Field(default=None, description="Optional natural key.")
    name: str = Field(..., description="Then description (e.g., 'Event: OrderCancelled')")
    description: Optional[str] = Field(default=None, description="Detailed description of the Then")
    referencedNodeId: Optional[str] = Field(default=None, description="ID of the referenced Event")
    referencedNodeType: Optional[str] = Field(default="Event", description="Type of referenced node (always 'Event')")
    fieldValues: Dict[str, str] = Field(
        default_factory=dict,
        description="Field values mapped from referenced Event's properties. Key is property name, value is the test value for that field."
    )


class CommandCandidate(BaseModel):
    """A candidate Command within an Aggregate."""

    id: Optional[str] = Field(default=None, description="Optional UUID (server-generated).")
    key: Optional[str] = Field(default=None, description="Optional natural key (derived from Aggregate + name).")
    name: str = Field(..., description="Command name in PascalCase like 'PlaceOrder'")
    displayName: Optional[str] = Field(default=None, description="UI label in chosen language (e.g. '주문하기' or 'Place Order').")
    actor: str = Field(default="user", description="Who triggers this command (should match User Story role when applicable)")
    category: Optional[str] = Field(default=None, description="Command category: Create, Update, Delete, Process, Business Logic, or External Integration")
    inputSchema: Optional[str] = Field(default=None, description="JSON schema or description of command input parameters")
    description: str = Field(..., description="What this command does")
    user_story_ids: List[str] = Field(
        default_factory=list, description="User Story IDs that this command implements"
    )
    # Note: GWT (given/when/then) is generated in post-processing step (generate_gwt_node)
    # and stored separately in Neo4j. Not included in initial LLM structured output schema.
    # GWT fields are added dynamically at runtime using setattr().


class EventCandidate(BaseModel):
    """A candidate Event emitted by a Command."""

    id: Optional[str] = Field(default=None, description="Optional UUID (server-generated).")
    key: Optional[str] = Field(default=None, description="Optional natural key (derived from Command + name + version).")
    name: str = Field(..., description="Event name in past tense like 'OrderPlaced'")
    displayName: Optional[str] = Field(default=None, description="UI label in chosen language (e.g. '주문 접수됨' or 'Order Placed').")
    emitting_command_name: Optional[str] = Field(default=None, description="Name of the Command that emits this Event (for explicit mapping)")
    version: str = Field(default="1.0.0", description="Event version for schema evolution")
    payload: Optional[str] = Field(default=None, description="JSON schema or description of event payload/data")
    description: str = Field(..., description="What happened")
    user_story_ids: List[str] = Field(
        default_factory=list, description="User Story IDs related to this event"
    )


class ReadModelCandidate(BaseModel):
    """A candidate ReadModel (query/projection) within a Bounded Context."""

    # NOTE: For ingestion workflow, we generate a deterministic id from (BC + name).
    # Keep this optional so the LLM output stays simple and stable.
    id: Optional[str] = Field(default=None, description="Optional ID (if provided).")
    name: str = Field(
        ...,
        description="ReadModel name in PascalCase using Noun+Purpose (e.g., OrderSummary, OrderStatus).",
    )
    displayName: Optional[str] = Field(default=None, description="UI label in chosen language (e.g. '주문 요약' or 'Order Summary').")
    description: str = Field(..., description="What this ReadModel provides for queries.")
    actor: str = Field(
        default="user",
        description="Who uses this ReadModel: user, admin, or system. Should match User Story role when available.",
    )
    isMultipleResult: Optional[str] = Field(
        default=None,
        description="Result type: 'list' for ordered lists (e.g., OrderList), 'collection' for unordered collections (e.g., ProductCatalog), 'single result' for single item results (e.g., OrderDetail, UserProfile).",
    )
    user_story_ids: List[str] = Field(
        default_factory=list,
        description="User Story IDs (within the BC) that this ReadModel supports (query intent).",
    )


class PolicyCandidate(BaseModel):
    """A candidate Policy for cross-BC communication."""

    id: Optional[str] = Field(default=None, description="Optional UUID (server-generated).")
    key: Optional[str] = Field(default=None, description="Optional natural key (derived from target BC + name).")
    name: str = Field(..., description="Policy name like 'RefundOnOrderCancelled'")
    displayName: Optional[str] = Field(default=None, description="UI label in chosen language (e.g. '주문 취소 시 환불' or 'Refund on Order Cancelled').")
    trigger_event: str = Field(..., description="Event that triggers this policy")
    trigger_event_bc: str = Field(
        default="", description="BC where the trigger event originates (must be different from target_bc)"
    )
    target_bc: str = Field(..., description="BC where this policy lives")
    invoke_command: str = Field(..., description="Command this policy invokes")
    description: str = Field(..., description="When [event] then [command] description")
    user_story_ids: List[str] = Field(
        default_factory=list,
        description="User Story IDs that this policy supports (inherited from triggering event)",
    )
    # Note: GWT (given/when/then) is generated in post-processing step (generate_gwt_node)
    # and stored separately in Neo4j. Not included in initial LLM structured output schema.
    # GWT fields are added dynamically at runtime using setattr().


class UserStoryBreakdown(BaseModel):
    """Breakdown of a User Story into finer-grained tasks."""

    user_story_id: str = Field(..., description="The original user story ID")
    sub_tasks: List[str] = Field(
        ..., description="List of sub-tasks or acceptance criteria"
    )
    domain_concepts: List[str] = Field(
        ..., description="Key domain concepts identified"
    )
    potential_aggregates: List[str] = Field(
        ..., description="Potential aggregate names identified"
    )
    potential_commands: List[str] = Field(
        ..., description="Potential command names identified"
    )


# =============================================================================
# Main Workflow State
# =============================================================================


class EventStormingState(BaseModel):
    """
    Main state for the Event Storming LangGraph workflow.

    The workflow processes user stories one by one:
    1. Load all unprocessed user stories
    2. Visit each user story to identify BC candidates
    3. For each BC candidate, break down user stories
    4. Extract aggregates, commands, events
    5. Identify cross-BC policies
    6. Save everything to Neo4j

    Human-in-the-loop checkpoints allow review at key decision points.
    """

    # Current workflow phase
    phase: WorkflowPhase = Field(default=WorkflowPhase.INIT)

    # Message history for the conversation
    messages: Annotated[List[Any], add_messages] = Field(default_factory=list)

    # User Stories from Neo4j
    user_stories: List[Dict[str, Any]] = Field(default_factory=list)
    current_user_story_index: int = Field(default=0)

    # Bounded Context candidates
    bc_candidates: List[BoundedContextCandidate] = Field(default_factory=list)
    approved_bcs: List[BoundedContextCandidate] = Field(default_factory=list)
    current_bc_index: int = Field(default=0)

    # User Story breakdowns
    breakdowns: List[UserStoryBreakdown] = Field(default_factory=list)

    # Aggregate candidates per BC
    aggregate_candidates: Dict[str, List[AggregateCandidate]] = Field(default_factory=dict)
    approved_aggregates: Dict[str, List[AggregateCandidate]] = Field(default_factory=dict)

    # Command candidates per Aggregate
    command_candidates: Dict[str, List[CommandCandidate]] = Field(default_factory=dict)

    # Event candidates per Command
    event_candidates: Dict[str, List[EventCandidate]] = Field(default_factory=dict)

    # Policy candidates for cross-BC communication
    policy_candidates: List[PolicyCandidate] = Field(default_factory=list)
    approved_policies: List[PolicyCandidate] = Field(default_factory=list)

    # Human-in-the-loop state
    awaiting_human_approval: bool = Field(default=False)
    human_feedback: Optional[str] = Field(default=None)

    # Error handling
    error: Optional[str] = Field(default=None)

    # Processing stats
    processed_user_stories: int = Field(default=0)
    total_user_stories: int = Field(default=0)

    class Config:
        arbitrary_types_allowed = True


# =============================================================================
# State Update Helpers
# =============================================================================


def get_current_user_story(state: EventStormingState) -> Optional[Dict[str, Any]]:
    """Get the current user story being processed."""
    if state.current_user_story_index < len(state.user_stories):
        return state.user_stories[state.current_user_story_index]
    return None


def get_current_bc(state: EventStormingState) -> Optional[BoundedContextCandidate]:
    """Get the current bounded context being processed."""
    if state.current_bc_index < len(state.approved_bcs):
        return state.approved_bcs[state.current_bc_index]
    return None


def format_user_story(us: Dict[str, Any]) -> str:
    """Format a user story for display."""
    role = us.get("role", "user")
    action = us.get("action", "do something")
    benefit = us.get("benefit", "")
    text = f"As a {role}, I want to {action}"
    if benefit:
        text += f", so that {benefit}"
    return text

