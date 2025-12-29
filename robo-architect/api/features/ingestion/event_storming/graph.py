"""
LangGraph Workflow for Event Storming

This module defines the main workflow graph that orchestrates the
Event Storming process from User Stories to a complete domain model.

Workflow Steps:
1. init → Load user stories from Neo4j
2. identify_bc → Identify Bounded Context candidates
3. approve_bc → Human-in-the-loop approval
4. breakdown → Break down user stories
5. extract_aggregates → Extract aggregates per BC
6. approve_aggregates → Human-in-the-loop approval
7. extract_commands → Extract commands per aggregate
8. extract_events → Extract events per command
9. identify_policies → Identify cross-BC policies
10. approve_policies → Human-in-the-loop approval
11. save_to_graph → Persist everything to Neo4j

The graph uses checkpointing for human-in-the-loop interactions,
allowing the workflow to pause and resume when human input is needed.
"""

from __future__ import annotations

from typing import Literal
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph

from .nodes import (
    approve_aggregates_node,
    approve_bc_node,
    approve_policies_node,
    breakdown_user_story_node,
    extract_aggregates_node,
    extract_commands_node,
    extract_events_node,
    identify_bc_node,
    identify_policies_node,
    init_node,
    load_user_stories_node,
    save_to_graph_node,
)
from .state import EventStormingState, WorkflowPhase

from api.platform.observability.smart_logger import SmartLogger


def should_continue_or_wait(
    state: EventStormingState,
) -> Literal["wait_for_human", "continue"]:
    """Determine if we should wait for human input or continue."""
    if state.awaiting_human_approval:
        return "wait_for_human"
    return "continue"


def route_after_bc_approval(
    state: EventStormingState,
) -> Literal["breakdown_user_story", "identify_bc"]:
    """Route after BC approval - continue or revise."""
    if state.approved_bcs:
        return "breakdown_user_story"
    return "identify_bc"


def route_after_aggregate_approval(
    state: EventStormingState,
) -> Literal["extract_commands", "extract_aggregates"]:
    """Route after aggregate approval."""
    if state.approved_aggregates:
        return "extract_commands"
    return "extract_aggregates"


def route_after_policy_approval(
    state: EventStormingState,
) -> Literal["save_to_graph", "identify_policies"]:
    """Route after policy approval."""
    # Check if we're in SAVE_TO_GRAPH phase (means approval happened)
    if state.phase == WorkflowPhase.SAVE_TO_GRAPH:
        return "save_to_graph"
    # Check if not awaiting approval and we've processed policies
    if not state.awaiting_human_approval and state.phase != WorkflowPhase.IDENTIFY_POLICIES:
        return "save_to_graph"
    return "identify_policies"


def route_breakdown(
    state: EventStormingState,
) -> Literal["breakdown_user_story", "extract_aggregates"]:
    """Route during breakdown - continue or move to aggregates."""
    if state.current_bc_index < len(state.approved_bcs):
        return "breakdown_user_story"
    return "extract_aggregates"


def route_aggregate_extraction(
    state: EventStormingState,
) -> Literal["extract_aggregates", "approve_aggregates"]:
    """Route during aggregate extraction."""
    if state.current_bc_index < len(state.approved_bcs):
        return "extract_aggregates"
    return "approve_aggregates"


def create_event_storming_graph(checkpointer=None):
    """
    Create the Event Storming LangGraph workflow.

    Args:
        checkpointer: Optional checkpointer for persistence.
                     If None, uses MemorySaver for in-memory checkpointing.

    Returns:
        Compiled StateGraph ready for execution.
    """

    # Create the graph
    graph = StateGraph(EventStormingState)

    # ==========================================================================
    # Add Nodes
    # ==========================================================================

    graph.add_node("init", init_node)
    graph.add_node("load_user_stories", load_user_stories_node)
    graph.add_node("identify_bc", identify_bc_node)
    graph.add_node("approve_bc", approve_bc_node)
    graph.add_node("breakdown_user_story", breakdown_user_story_node)
    graph.add_node("extract_aggregates", extract_aggregates_node)
    graph.add_node("approve_aggregates", approve_aggregates_node)
    graph.add_node("extract_commands", extract_commands_node)
    graph.add_node("extract_events", extract_events_node)
    graph.add_node("identify_policies", identify_policies_node)
    graph.add_node("approve_policies", approve_policies_node)
    graph.add_node("save_to_graph", save_to_graph_node)

    # ==========================================================================
    # Add Edges
    # ==========================================================================

    # Start -> Init -> Load User Stories
    graph.set_entry_point("init")
    graph.add_edge("init", "load_user_stories")

    # Load -> Identify BC
    graph.add_edge("load_user_stories", "identify_bc")

    # Identify BC -> Approve BC (interrupt for human-in-the-loop)
    graph.add_edge("identify_bc", "approve_bc")

    # After BC approval - conditional routing
    graph.add_conditional_edges(
        "approve_bc",
        route_after_bc_approval,
        {
            "breakdown_user_story": "breakdown_user_story",
            "identify_bc": "identify_bc",
        },
    )

    # Breakdown loop - process each BC
    graph.add_conditional_edges(
        "breakdown_user_story",
        route_breakdown,
        {
            "breakdown_user_story": "breakdown_user_story",
            "extract_aggregates": "extract_aggregates",
        },
    )

    # Aggregate extraction loop
    graph.add_conditional_edges(
        "extract_aggregates",
        route_aggregate_extraction,
        {
            "extract_aggregates": "extract_aggregates",
            "approve_aggregates": "approve_aggregates",
        },
    )

    # After aggregate approval
    graph.add_conditional_edges(
        "approve_aggregates",
        route_after_aggregate_approval,
        {
            "extract_commands": "extract_commands",
            "extract_aggregates": "extract_aggregates",
        },
    )

    # Commands -> Events -> Policies
    graph.add_edge("extract_commands", "extract_events")
    graph.add_edge("extract_events", "identify_policies")
    graph.add_edge("identify_policies", "approve_policies")

    # After policy approval
    graph.add_conditional_edges(
        "approve_policies",
        route_after_policy_approval,
        {
            "save_to_graph": "save_to_graph",
            "identify_policies": "identify_policies",
        },
    )

    # Save to graph -> End
    graph.add_edge("save_to_graph", END)

    # ==========================================================================
    # Compile with Checkpointer
    # ==========================================================================

    if checkpointer is None:
        checkpointer = MemorySaver()

    # Add interrupt points for human-in-the-loop
    compiled = graph.compile(
        checkpointer=checkpointer,
        interrupt_before=["approve_bc", "approve_aggregates", "approve_policies"],
    )

    return compiled


def get_graph_visualization():
    """Get a Mermaid diagram of the workflow graph."""
    graph = create_event_storming_graph()
    return graph.get_graph().draw_mermaid()


# =============================================================================
# Graph Runner
# =============================================================================


class EventStormingRunner:
    """
    Runner for the Event Storming workflow with human-in-the-loop support.

    Usage:
        runner = EventStormingRunner()
        runner.start()

        # At each approval point:
        runner.provide_feedback("APPROVED")  # or feedback text

        # Check completion:
        if runner.is_complete():
            SmartLogger.log("INFO", "Workflow complete", category="agent.runner", params={"result": runner.get_result()})
    """

    def __init__(self, thread_id: str = "default"):
        self.checkpointer = MemorySaver()
        self.graph = create_event_storming_graph(self.checkpointer)
        self.thread_id = thread_id
        self.config = {"configurable": {"thread_id": thread_id}}
        self._current_state: EventStormingState | None = None

    def start(self) -> EventStormingState:
        """Start the workflow from the beginning."""
        initial_state = EventStormingState()

        # Run until we hit an interrupt
        for event in self.graph.stream(initial_state, self.config, stream_mode="values"):
            self._current_state = event

        return self._current_state

    def provide_feedback(self, feedback: str) -> EventStormingState:
        """Provide human feedback and continue the workflow."""
        if self._current_state is None:
            raise ValueError("Workflow not started. Call start() first.")

        # Update state with feedback using graph.update_state
        self.graph.update_state(
            self.config,
            {"human_feedback": feedback, "awaiting_human_approval": False},
        )

        # Continue from the interrupt (pass None to resume)
        for event in self.graph.stream(None, self.config, stream_mode="values"):
            self._current_state = event

        return self._current_state

    def get_state(self) -> EventStormingState | None:
        """Get the current state of the workflow."""
        snapshot = self.graph.get_state(self.config)
        if snapshot and snapshot.values:
            return EventStormingState(**snapshot.values)
        return self._current_state

    def is_waiting_for_human(self) -> bool:
        """Check if the workflow is waiting for human input."""
        state = self.get_state()
        return state.awaiting_human_approval if state else False

    def is_complete(self) -> bool:
        """Check if the workflow is complete."""
        state = self.get_state()
        return state.phase == WorkflowPhase.COMPLETE if state else False

    def get_messages(self) -> list:
        """Get the message history."""
        state = self.get_state()
        return state.messages if state else []

    def get_last_message(self) -> str:
        """Get the last message content."""
        messages = self.get_messages()
        if messages:
            return messages[-1].content
        return ""


if __name__ == "__main__":
    # Print the graph visualization
    SmartLogger.log("INFO", "Event Storming Workflow Graph", category="agent.graph", params={"mermaid": get_graph_visualization()})

