"""
Change Planning: Graph Routing Helpers
"""

from __future__ import annotations

from api.platform.observability.smart_logger import SmartLogger

from .change_planning_contracts import ChangePlanningState, ChangeScope


def route_after_scope_analysis(state: ChangePlanningState) -> str:
    """Route based on change scope."""
    if state.change_scope in [ChangeScope.CROSS_BC, ChangeScope.NEW_CAPABILITY]:
        SmartLogger.log(
            "INFO",
            "Routing decision after propagation: scope requires cross-BC discovery, so we will search related objects before finalizing the plan.",
            category="agent.change_graph.route.after_propagation",
            params={
                "user_story_id": state.user_story_id,
                "scope": state.change_scope.value if state.change_scope else None,
                "next": "search_related",
            },
        )
        return "search_related"

    SmartLogger.log(
        "INFO",
        "Routing decision after propagation: scope is LOCAL, so we will finalize the plan without cross-BC search.",
        category="agent.change_graph.route.after_propagation",
        params={
            "user_story_id": state.user_story_id,
            "scope": state.change_scope.value if state.change_scope else None,
            "next": "generate_plan",
        },
    )
    return "generate_plan"


def route_after_approval(state: ChangePlanningState) -> str:
    """Route based on human approval."""
    if state.human_feedback:
        if state.human_feedback.upper() == "APPROVED":
            return "apply_changes"
        else:
            return "revise_plan"
    return "await_approval"


