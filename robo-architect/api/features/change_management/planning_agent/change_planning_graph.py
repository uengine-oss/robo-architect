"""
Change Planning Graph (LangGraph)

Business capability: orchestrate the change planning workflow from scope analysis -> propagation -> (optional search) -> plan -> apply/revise.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph

from .change_planning_contracts import ChangePlanningPhase, ChangePlanningState
from .graph_routes import route_after_scope_analysis
from .impact_propagation import propagate_impacts_node
from .plan_apply import apply_changes_node
from .plan_finalizer import generate_plan_node
from .plan_revision import revise_plan_node
from .related_search import search_related_objects_node
from .scope_analysis import analyze_scope_node


def create_change_planning_graph(checkpointer=None):
    """Create the change planning workflow graph."""
    graph = StateGraph(ChangePlanningState)

    # Add nodes
    graph.add_node("analyze_scope", analyze_scope_node)
    graph.add_node("propagate_impacts", propagate_impacts_node)
    graph.add_node("search_related", search_related_objects_node)
    graph.add_node("generate_plan", generate_plan_node)
    graph.add_node("revise_plan", revise_plan_node)
    graph.add_node("apply_changes", apply_changes_node)

    # Set entry point
    graph.set_entry_point("analyze_scope")

    # Add edges
    graph.add_edge("analyze_scope", "propagate_impacts")
    graph.add_conditional_edges(
        "propagate_impacts",
        route_after_scope_analysis,
        {
            "search_related": "search_related",
            "generate_plan": "generate_plan",
        },
    )

    graph.add_edge("search_related", "generate_plan")
    graph.add_edge("generate_plan", END)  # Pause for approval
    graph.add_edge("revise_plan", END)  # Pause for re-approval
    graph.add_edge("apply_changes", END)

    if checkpointer is None:
        checkpointer = MemorySaver()

    return graph.compile(
        checkpointer=checkpointer,
        interrupt_before=[],  # We handle approval in API layer
    )


class ChangePlanningRunner:
    """Runner for the change planning workflow."""

    def __init__(self, thread_id: str = "default"):
        self.checkpointer = MemorySaver()
        self.graph = create_change_planning_graph(self.checkpointer)
        self.thread_id = thread_id
        self.config = {"configurable": {"thread_id": thread_id}}
        self._current_state: Optional[ChangePlanningState] = None

    def start(
        self,
        user_story_id: str,
        original_user_story: Dict[str, Any],
        edited_user_story: Dict[str, Any],
        connected_objects: List[Dict[str, Any]],
    ) -> ChangePlanningState:
        """Start the change planning workflow."""
        initial_state = ChangePlanningState(
            user_story_id=user_story_id,
            original_user_story=original_user_story,
            edited_user_story=edited_user_story,
            connected_objects=connected_objects,
            phase=ChangePlanningPhase.INIT,
        )

        # Run until we need approval
        for event in self.graph.stream(initial_state, self.config, stream_mode="values"):
            self._current_state = ChangePlanningState(**event) if isinstance(event, dict) else event

        return self._current_state

    def provide_feedback(self, feedback: str) -> ChangePlanningState:
        """Provide feedback and continue."""
        if self._current_state is None:
            raise ValueError("Workflow not started")

        # Update state
        self.graph.update_state(
            self.config,
            {"human_feedback": feedback, "awaiting_approval": False},
        )

        # Determine next action
        if feedback.upper() == "APPROVED":
            # Run apply_changes
            self.graph.update_state(self.config, {"phase": ChangePlanningPhase.APPLY_CHANGES})
            result = self.graph.invoke(None, self.config)
        else:
            # Run revision
            self.graph.update_state(self.config, {"phase": ChangePlanningPhase.REVISE_PLAN})
            result = self.graph.invoke(None, self.config)

        self._current_state = ChangePlanningState(**result) if isinstance(result, dict) else result
        return self._current_state

    def get_state(self) -> Optional[ChangePlanningState]:
        """Get current state."""
        return self._current_state


