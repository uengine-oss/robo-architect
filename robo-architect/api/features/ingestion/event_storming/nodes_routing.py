"""
Event Storming Nodes: routing helpers
"""

from __future__ import annotations

from .state import EventStormingState, WorkflowPhase


def route_after_approval(state: EventStormingState) -> str:
    """Route based on whether we're waiting for human approval."""
    if state.awaiting_human_approval:
        return "wait_for_human"
    return "continue"


def route_by_phase(state: EventStormingState) -> str:
    """Route to the appropriate node based on current phase."""
    phase_routes = {
        WorkflowPhase.INIT: "init",
        WorkflowPhase.LOAD_USER_STORIES: "load_user_stories",
        WorkflowPhase.SELECT_USER_STORY: "select_user_story",
        WorkflowPhase.IDENTIFY_BC: "identify_bc",
        WorkflowPhase.APPROVE_BC: "approve_bc",
        WorkflowPhase.BREAKDOWN_USER_STORY: "breakdown_user_story",
        WorkflowPhase.EXTRACT_AGGREGATES: "extract_aggregates",
        WorkflowPhase.APPROVE_AGGREGATES: "approve_aggregates",
        WorkflowPhase.EXTRACT_COMMANDS: "extract_commands",
        WorkflowPhase.EXTRACT_EVENTS: "extract_events",
        WorkflowPhase.IDENTIFY_POLICIES: "identify_policies",
        WorkflowPhase.APPROVE_POLICIES: "approve_policies",
        WorkflowPhase.SAVE_TO_GRAPH: "save_to_graph",
        WorkflowPhase.COMPLETE: "complete",
    }
    return phase_routes.get(state.phase, "complete")


