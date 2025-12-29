"""
Change Planning: Scope Analysis

Business capability: determine whether a user story change is local, cross-bounded-context, or a new capability.
"""

from __future__ import annotations

import json
import time
from typing import Any, Dict

from langchain_core.messages import HumanMessage, SystemMessage

from api.platform.observability.request_logging import sha256_text, summarize_for_log
from api.platform.observability.smart_logger import SmartLogger
from api.platform.env import (
    AI_AUDIT_LOG_ENABLED,
    AI_AUDIT_LOG_FULL_OUTPUT,
    AI_AUDIT_LOG_FULL_PROMPT,
    get_llm_provider_model,
)

from .change_planning_contracts import ChangePlanningPhase, ChangePlanningState, ChangeScope
from .change_planning_runtime import get_llm


def analyze_scope_node(state: ChangePlanningState) -> Dict[str, Any]:
    """
    Analyze whether the change can be resolved within existing connections
    or requires cross-BC connections.
    """
    llm = get_llm()

    SmartLogger.log(
        "INFO",
        "Scope analysis started: determining whether the change is LOCAL, CROSS_BC, or NEW_CAPABILITY.",
        category="agent.change_graph.scope.start",
        params={
            "user_story_id": state.user_story_id,
            "connected_objects_count": len(state.connected_objects or []),
            "original_user_story": summarize_for_log(state.original_user_story),
            "edited_user_story": summarize_for_log(state.edited_user_story),
        }
    )

    # Build context
    original = state.original_user_story
    edited = state.edited_user_story
    connected = state.connected_objects

    connected_text = "\n".join(
        [f"- {obj.get('type', 'Unknown')}: {obj.get('name', '?')} (BC: {obj.get('bcName', 'Unknown')})" for obj in connected]
    )

    prompt = f"""Analyze this User Story change and determine its scope.

## Original User Story
Role: {original.get('role', 'user')}
Action: {original.get('action', '')}
Benefit: {original.get('benefit', '')}

## Modified User Story
Role: {edited.get('role', 'user')}
Action: {edited.get('action', '')}
Benefit: {edited.get('benefit', '')}

## Currently Connected Objects (in same BC)
{connected_text if connected_text else "No connected objects found"}

## Your Task
Determine the SCOPE of this change:

1. LOCAL - The change can be handled by modifying/adding objects within the currently connected BC
   Example: Changing "add to cart" to "add to cart with quantity validation"

2. CROSS_BC - The change requires connecting to or creating objects in a DIFFERENT Bounded Context
   Example: Adding "send notification" requires connecting to Notification BC
   
3. NEW_CAPABILITY - The change requires creating entirely new capabilities that don't exist yet
   Example: Adding AI-powered recommendations when no ML infrastructure exists

Also identify KEY TERMS that should be searched in the graph to find related objects.
For example, if the change mentions "notification", search for objects related to notification.

Respond in this exact JSON format:
{{
    "scope": "LOCAL" or "CROSS_BC" or "NEW_CAPABILITY",
    "reasoning": "Explanation of why this scope was chosen",
    "keywords": ["keyword1", "keyword2", ...],
    "change_description": "Brief description of what changed"
}}"""

    provider, model = get_llm_provider_model()
    system_msg = "You are a DDD expert analyzing change impact."

    if AI_AUDIT_LOG_ENABLED:
        SmartLogger.log(
            "INFO",
            "Scope analysis: LLM invoke starting.",
            category="agent.change_graph.scope.llm.start",
            params={
                "user_story_id": state.user_story_id,
                "llm": {"provider": provider, "model": model},
                "prompt_len": len(prompt),
                "prompt_sha256": sha256_text(prompt),
                "prompt": prompt if AI_AUDIT_LOG_FULL_PROMPT else summarize_for_log(prompt),
                "system_len": len(system_msg),
                "system_sha256": sha256_text(system_msg),
            }
        )

    t_llm0 = time.perf_counter()
    response = llm.invoke([SystemMessage(content=system_msg), HumanMessage(content=prompt)])
    llm_ms = int((time.perf_counter() - t_llm0) * 1000)

    resp_text = getattr(response, "content", "") or ""
    if AI_AUDIT_LOG_ENABLED:
        SmartLogger.log(
            "INFO",
            "Scope analysis: LLM invoke completed.",
            category="agent.change_graph.scope.llm.done",
            params={
                "user_story_id": state.user_story_id,
                "llm": {"provider": provider, "model": model},
                "llm_ms": llm_ms,
                "response_len": len(resp_text),
                "response_sha256": sha256_text(resp_text),
                "response": resp_text if AI_AUDIT_LOG_FULL_OUTPUT else summarize_for_log(resp_text),
            }
        )

    try:
        # Extract JSON from response
        content = response.content
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0]
        elif "```" in content:
            content = content.split("```")[1].split("```")[0]

        result = json.loads(content.strip())

        scope_map = {
            "LOCAL": ChangeScope.LOCAL,
            "CROSS_BC": ChangeScope.CROSS_BC,
            "NEW_CAPABILITY": ChangeScope.NEW_CAPABILITY,
        }

        payload = {
            "phase": ChangePlanningPhase.SEARCH_RELATED if result["scope"] != "LOCAL" else ChangePlanningPhase.GENERATE_PLAN,
            "change_scope": scope_map.get(result["scope"], ChangeScope.LOCAL),
            "scope_reasoning": result.get("reasoning", ""),
            "keywords_to_search": result.get("keywords", []),
            "change_description": result.get("change_description", ""),
        }

        SmartLogger.log(
            "INFO",
            "Scope analysis completed: scope determined based on user story delta and current connections.",
            category="agent.change_graph.scope.done",
            params={
                "user_story_id": state.user_story_id,
                "scope": payload["change_scope"].value if payload.get("change_scope") else None,
                "keywords_to_search": (payload.get("keywords_to_search") or [])[:20],
                "change_description": payload.get("change_description"),
                "reasoning_preview": (payload.get("scope_reasoning") or "")[:300],
            }
        )
        return payload
    except Exception as e:
        SmartLogger.log(
            "WARNING",
            "Scope analysis fallback: failed to parse LLM response, defaulting scope to LOCAL to keep workflow moving.",
            category="agent.change_graph.scope.parse_error",
            params={
                "user_story_id": state.user_story_id,
                "error": str(e),
                "llm_raw_preview": (getattr(response, "content", "") or "")[:1200],
            }
        )
        return {
            "phase": ChangePlanningPhase.GENERATE_PLAN,
            "change_scope": ChangeScope.LOCAL,
            "scope_reasoning": f"Failed to parse LLM response: {str(e)}",
            "keywords_to_search": [],
            "change_description": "",
        }


