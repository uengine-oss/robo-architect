"""
Change Planning: Plan Revision

Business capability: revise a proposed change plan based on human feedback.
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

from .change_planning_contracts import ChangePlanningPhase, ChangePlanningState, ProposedChange
from .change_planning_runtime import get_llm


def revise_plan_node(state: ChangePlanningState) -> Dict[str, Any]:
    """
    Revise the plan based on human feedback.
    """
    if not state.human_feedback:
        return {"phase": ChangePlanningPhase.AWAIT_APPROVAL}

    llm = get_llm()

    current_plan = [
        {
            "action": c.action,
            "targetType": c.targetType,
            "targetId": c.targetId,
            "targetName": c.targetName,
            "description": c.description,
            "reason": c.reason,
        }
        for c in state.proposed_changes
    ]

    prompt = f"""Revise this change plan based on user feedback.

## Current Plan
{json.dumps(current_plan, indent=2)}

## User Feedback
{state.human_feedback}

## Context
- User Story ID: {state.user_story_id}
- Original Action: {state.original_user_story.get('action', '')}
- New Action: {state.edited_user_story.get('action', '')}

## Related Objects Available
{chr(10).join([f"- {obj.type}: {obj.name} (BC: {obj.bcName})" for obj in state.related_objects])}

Provide the revised plan in the same JSON format:
{{
    "summary": "Brief summary of revised plan",
    "changes": [...]
}}"""

    provider, model = get_llm_provider_model()
    system_msg = "You are revising a change plan based on user feedback."

    if AI_AUDIT_LOG_ENABLED:
        SmartLogger.log(
            "INFO",
            "Plan revision: LLM invoke starting.",
            category="agent.change_graph.plan_revision.llm.start",
            params={
                "user_story_id": state.user_story_id,
                "revision_count": state.revision_count,
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
            "Plan revision: LLM invoke completed.",
            category="agent.change_graph.plan_revision.llm.done",
            params={
                "user_story_id": state.user_story_id,
                "revision_count": state.revision_count,
                "llm": {"provider": provider, "model": model},
                "llm_ms": llm_ms,
                "response_len": len(resp_text),
                "response_sha256": sha256_text(resp_text),
                "response": resp_text if AI_AUDIT_LOG_FULL_OUTPUT else summarize_for_log(resp_text),
            }
        )

    try:
        content = response.content
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0]
        elif "```" in content:
            content = content.split("```")[1].split("```")[0]

        result = json.loads(content.strip())

        proposed_changes = []
        for change in result.get("changes", []):
            proposed_changes.append(
                ProposedChange(
                    action=change.get("action", "update"),
                    targetType=change.get("targetType", "Unknown"),
                    targetId=change.get("targetId", ""),
                    targetName=change.get("targetName", ""),
                    targetBcId=change.get("targetBcId"),
                    targetBcName=change.get("targetBcName"),
                    description=change.get("description", ""),
                    reason=change.get("reason", ""),
                    connectionType=change.get("connectionType"),
                    sourceId=change.get("sourceId"),
                )
            )

        return {
            "phase": ChangePlanningPhase.AWAIT_APPROVAL,
            "proposed_changes": proposed_changes,
            "plan_summary": result.get("summary", ""),
            "awaiting_approval": True,
            "human_feedback": None,
            "revision_count": state.revision_count + 1,
        }

    except Exception as e:
        return {
            "phase": ChangePlanningPhase.AWAIT_APPROVAL,
            "error": str(e),
        }


