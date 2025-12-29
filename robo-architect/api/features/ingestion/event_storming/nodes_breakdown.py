"""
Event Storming Nodes: user story breakdown (within a bounded context)
"""

from __future__ import annotations

import time
from typing import Any, Dict

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from api.platform.env import (
    AI_AUDIT_LOG_ENABLED,
    AI_AUDIT_LOG_FULL_OUTPUT,
    AI_AUDIT_LOG_FULL_PROMPT,
    get_llm_provider_model,
)
from api.platform.observability.request_logging import sha256_text, summarize_for_log
from api.platform.observability.smart_logger import SmartLogger

from .node_runtime import dump_model, get_llm
from .prompts import BREAKDOWN_USER_STORY_PROMPT, SYSTEM_PROMPT
from .state import EventStormingState, UserStoryBreakdown, WorkflowPhase, format_user_story


def breakdown_user_story_node(state: EventStormingState) -> Dict[str, Any]:
    """Break down user stories within the current Bounded Context."""
    if state.current_bc_index >= len(state.approved_bcs):
        # All BCs processed, move to aggregate extraction
        return {
            "phase": WorkflowPhase.EXTRACT_AGGREGATES,
            "current_bc_index": 0,
        }

    current_bc = state.approved_bcs[state.current_bc_index]
    llm = get_llm()

    # Get user stories for this BC
    bc_stories = [us for us in state.user_stories if us["id"] in current_bc.user_story_ids]

    breakdowns = []

    for us in bc_stories:
        user_story_text = format_user_story(us)
        prompt = BREAKDOWN_USER_STORY_PROMPT.format(
            user_story=f"[{us['id']}] {user_story_text}",
            bc_name=current_bc.name,
        )

        structured_llm = llm.with_structured_output(UserStoryBreakdown)

        provider, model = get_llm_provider_model()
        if AI_AUDIT_LOG_ENABLED:
            SmartLogger.log(
                "INFO",
                "EventStorming: breakdown user story - LLM invoke starting.",
                category="agent.nodes.breakdown_user_story.llm.start",
                params={
                    "llm": {"provider": provider, "model": model},
                    "bc": {"id": current_bc.id, "name": current_bc.name},
                    "user_story_id": us.get("id"),
                    "prompt_len": len(prompt),
                    "prompt_sha256": sha256_text(prompt),
                    "prompt": prompt if AI_AUDIT_LOG_FULL_PROMPT else summarize_for_log(prompt),
                    "system_sha256": sha256_text(SYSTEM_PROMPT),
                }
            )

        t_llm0 = time.perf_counter()
        response = structured_llm.invoke([SystemMessage(content=SYSTEM_PROMPT), HumanMessage(content=prompt)])
        llm_ms = int((time.perf_counter() - t_llm0) * 1000)

        if AI_AUDIT_LOG_ENABLED:
            SmartLogger.log(
                "INFO",
                "EventStorming: breakdown user story - LLM invoke completed.",
                category="agent.nodes.breakdown_user_story.llm.done",
                params={
                    "llm": {"provider": provider, "model": model},
                    "bc": {"id": current_bc.id, "name": current_bc.name},
                    "user_story_id": us.get("id"),
                    "llm_ms": llm_ms,
                    "response": dump_model(response) if AI_AUDIT_LOG_FULL_OUTPUT else summarize_for_log(dump_model(response)),
                }
            )
        # Ensure correct ID
        response.user_story_id = us["id"]
        breakdowns.append(response)

    # Move to next BC
    return {
        "breakdowns": state.breakdowns + breakdowns,
        "current_bc_index": state.current_bc_index + 1,
        "messages": [
            AIMessage(content=f"Analyzed {len(breakdowns)} user stories in BC '{current_bc.name}'. Moving to next BC...")
        ],
    }


