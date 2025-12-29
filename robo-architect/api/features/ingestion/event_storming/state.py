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
    SAVE_TO_GRAPH = "save_to_graph"
    COMPLETE = "complete"


# =============================================================================
# Pydantic Models for LLM Structured Output
# =============================================================================


class BoundedContextCandidate(BaseModel):
    """A candidate Bounded Context identified from User Stories."""

    id: str = Field(..., description="Unique ID like BC-ORDER")
    name: str = Field(..., description="Short name like 'Order'")
    description: str = Field(..., description="What this BC is responsible for")
    rationale: str = Field(..., description="Why this should be a separate BC")
    user_story_ids: List[str] = Field(
        default_factory=list, description="User Story IDs that belong to this BC"
    )


class AggregateCandidate(BaseModel):
    """A candidate Aggregate within a Bounded Context."""

    id: str = Field(..., description="Unique ID like AGG-ORDER-CART")
    name: str = Field(..., description="Aggregate name like 'Cart'")
    root_entity: str = Field(..., description="Root entity name")
    invariants: List[str] = Field(
        default_factory=list, description="Business invariants this aggregate enforces"
    )
    description: str = Field(..., description="What this aggregate manages")
    user_story_ids: List[str] = Field(
        default_factory=list, description="User Story IDs that this aggregate implements"
    )


class CommandCandidate(BaseModel):
    """A candidate Command within an Aggregate."""

    id: str = Field(..., description="Unique ID like CMD-ORDER-PLACE")
    name: str = Field(..., description="Command name in PascalCase like 'PlaceOrder'")
    actor: str = Field(default="user", description="Who triggers this command")
    description: str = Field(..., description="What this command does")
    user_story_ids: List[str] = Field(
        default_factory=list, description="User Story IDs that this command implements"
    )


class EventCandidate(BaseModel):
    """A candidate Event emitted by a Command."""

    id: str = Field(..., description="Unique ID like EVT-ORDER-PLACED")
    name: str = Field(..., description="Event name in past tense like 'OrderPlaced'")
    description: str = Field(..., description="What happened")
    user_story_ids: List[str] = Field(
        default_factory=list, description="User Story IDs related to this event"
    )


class PolicyCandidate(BaseModel):
    """A candidate Policy for cross-BC communication."""

    id: str = Field(..., description="Unique ID like POL-REFUND-ON-CANCEL")
    name: str = Field(..., description="Policy name like 'RefundOnOrderCancelled'")
    trigger_event: str = Field(..., description="Event that triggers this policy")
    target_bc: str = Field(..., description="BC where this policy lives")
    invoke_command: str = Field(..., description="Command this policy invokes")
    description: str = Field(..., description="When [event] then [command] description")


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

