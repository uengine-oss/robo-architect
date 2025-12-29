"""
Change Planning API Helpers

Business capability: provide a simple function entry point for the /api/change/plan endpoint.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from .change_planning_contracts import ChangePlanningPhase, ChangePlanningState, ProposedChange
from .change_planning_graph import ChangePlanningRunner
from .plan_revision import revise_plan_node


def run_change_planning(
    user_story_id: str,
    original_user_story: Dict[str, Any],
    edited_user_story: Dict[str, Any],
    connected_objects: List[Dict[str, Any]],
    feedback: Optional[str] = None,
    previous_plan: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """
    Run the change planning workflow and return the plan.

    This is the main entry point for the API.
    """
    import uuid

    thread_id = str(uuid.uuid4())
    runner = ChangePlanningRunner(thread_id)

    if feedback and previous_plan:
        # This is a revision request
        # Reconstruct state and run revision
        state = ChangePlanningState(
            user_story_id=user_story_id,
            original_user_story=original_user_story,
            edited_user_story=edited_user_story,
            connected_objects=connected_objects,
            proposed_changes=[ProposedChange(**c) for c in previous_plan],
            human_feedback=feedback,
            phase=ChangePlanningPhase.REVISE_PLAN,
        )

        # Run just the revision node
        result = revise_plan_node(state)
        return {
            "scope": state.change_scope.value if state.change_scope else "local",
            "scopeReasoning": state.scope_reasoning,
            "relatedObjects": [obj.dict() for obj in state.related_objects],
            "changes": [c.dict() for c in result.get("proposed_changes", [])],
            "summary": result.get("plan_summary", ""),
            "propagation": {
                "enabled": state.propagation_enabled,
                "rounds": state.propagation_rounds,
                "stopReason": state.propagation_stop_reason,
                "confirmed": [c.model_dump() for c in (state.propagation_confirmed or [])],
                "review": [c.model_dump() for c in (state.propagation_review or [])],
            },
        }

    # Start fresh planning
    final_state = runner.start(
        user_story_id=user_story_id,
        original_user_story=original_user_story,
        edited_user_story=edited_user_story,
        connected_objects=connected_objects,
    )

    return {
        "scope": final_state.change_scope.value if final_state.change_scope else "local",
        "scopeReasoning": final_state.scope_reasoning,
        "keywords": final_state.keywords_to_search,
        "relatedObjects": [obj.dict() for obj in final_state.related_objects],
        "changes": [c.dict() for c in final_state.proposed_changes],
        "summary": final_state.plan_summary,
        "propagation": {
            "enabled": final_state.propagation_enabled,
            "rounds": final_state.propagation_rounds,
            "stopReason": final_state.propagation_stop_reason,
            "confirmed": [c.model_dump() for c in (final_state.propagation_confirmed or [])],
            "review": [c.model_dump() for c in (final_state.propagation_review or [])],
            "debug": final_state.propagation_debug,
        },
    }


