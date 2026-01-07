from __future__ import annotations

from typing import Any, Dict, Optional

from langgraph.graph import END, StateGraph

from .user_story_planning_contracts import PlanningScope, UserStoryPlanningState
from .user_story_planning_nodes import analyze_story_node, find_matching_bc_node, generate_objects_node


def create_user_story_planning_graph():
    graph = StateGraph(UserStoryPlanningState)
    graph.add_node("analyze_story", analyze_story_node)
    graph.add_node("find_matching_bc", find_matching_bc_node)
    graph.add_node("generate_objects", generate_objects_node)

    graph.set_entry_point("analyze_story")
    graph.add_edge("analyze_story", "find_matching_bc")
    graph.add_edge("find_matching_bc", "generate_objects")
    graph.add_edge("generate_objects", END)

    return graph.compile()


def run_user_story_planning(
    role: str,
    action: str,
    benefit: str,
    target_bc_id: Optional[str] = None,
    auto_generate: bool = True,
) -> Dict[str, Any]:
    graph = create_user_story_planning_graph()
    initial_state = UserStoryPlanningState(
        role=role,
        action=action,
        benefit=benefit,
        target_bc_id=target_bc_id,
        auto_generate=auto_generate,
    )

    result = graph.invoke(initial_state)

    if hasattr(result, "scope"):
        scope_val = result.scope.value
        scope_reasoning = result.scope_reasoning
        keywords = result.domain_keywords
        related = result.related_objects
        changes = [obj.dict() for obj in result.proposed_objects]
        summary = result.plan_summary
    else:
        scope_val = (result.get("scope") or PlanningScope.EXISTING_BC).value
        scope_reasoning = result.get("scope_reasoning", "")
        keywords = result.get("domain_keywords", [])
        related = result.get("related_objects", [])
        changes = result.get("proposed_objects", [])
        summary = result.get("plan_summary", "")

    return {
        "scope": scope_val,
        "scopeReasoning": scope_reasoning,
        "keywords": keywords,
        "relatedObjects": related,
        "changes": changes,
        "summary": summary,
    }


