"""
Event Storming Nodes: bounded context identification + approval
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
from .prompts import IDENTIFY_BC_FROM_STORIES_PROMPT, SYSTEM_PROMPT
from .state import EventStormingState, WorkflowPhase
from .structured_outputs import BoundedContextList


def identify_bc_node(state: EventStormingState) -> Dict[str, Any]:
    """Identify Bounded Context candidates from user stories."""
    llm = get_llm()

    # Format user stories for the prompt
    stories_text = "\n".join(
        [
            f"[{us['id']}] As a {us.get('role', 'user')}, I want to {us.get('action', '?')}"
            + (f", so that {us.get('benefit', '')}" if us.get("benefit") else "")
            for us in state.user_stories
        ]
    )

    prompt = IDENTIFY_BC_FROM_STORIES_PROMPT.format(user_stories=stories_text)

    # Use structured output for BC candidates
    structured_llm = llm.with_structured_output(BoundedContextList)

    provider, model = get_llm_provider_model()
    if AI_AUDIT_LOG_ENABLED:
        SmartLogger.log(
            "INFO",
            "EventStorming: identify BCs - LLM invoke starting.",
            category="agent.nodes.identify_bc.llm.start",
            params={
                "llm": {"provider": provider, "model": model},
                "user_stories_count": len(state.user_stories or []),
                "prompt_len": len(prompt),
                "prompt_sha256": sha256_text(prompt),
                "prompt": prompt if AI_AUDIT_LOG_FULL_PROMPT else summarize_for_log(prompt),
                "system_len": len(SYSTEM_PROMPT),
                "system_sha256": sha256_text(SYSTEM_PROMPT),
            }
        )

    t_llm0 = time.perf_counter()
    response = structured_llm.invoke([SystemMessage(content=SYSTEM_PROMPT), HumanMessage(content=prompt)])
    llm_ms = int((time.perf_counter() - t_llm0) * 1000)

    if AI_AUDIT_LOG_ENABLED:
        bcs = getattr(response, "bounded_contexts", []) or []
        SmartLogger.log(
            "INFO",
            "EventStorming: identify BCs - LLM invoke completed.",
            category="agent.nodes.identify_bc.llm.done",
            params={
                "llm": {"provider": provider, "model": model},
                "llm_ms": llm_ms,
                "result": {
                    "bounded_contexts_count": len(bcs),
                    "bounded_contexts": summarize_for_log(
                        [{"id": getattr(bc, "id", None), "name": getattr(bc, "name", None)} for bc in bcs]
                    ),
                    "response": dump_model(response) if AI_AUDIT_LOG_FULL_OUTPUT else summarize_for_log(dump_model(response)),
                },
            }
        )

    # Parse response into BC candidates
    bc_candidates = response.bounded_contexts

    # Format for display
    bc_text = "\n".join(
        [
            f"- {bc.id}: {bc.name}\n  Description: {bc.description}\n  User Stories: {', '.join(bc.user_story_ids)}"
            for bc in bc_candidates
        ]
    )

    return {
        "bc_candidates": bc_candidates,
        "phase": WorkflowPhase.APPROVE_BC,
        "awaiting_human_approval": True,
        "messages": [
            AIMessage(
                content=f"I've identified {len(bc_candidates)} Bounded Context candidates:\n\n{bc_text}\n\nPlease review and approve, or provide feedback for changes."
            )
        ],
    }


def approve_bc_node(state: EventStormingState) -> Dict[str, Any]:
    """Process human approval for Bounded Contexts."""
    feedback = state.human_feedback

    if feedback and feedback.upper() == "APPROVED":
        return {
            "approved_bcs": state.bc_candidates,
            "awaiting_human_approval": False,
            "human_feedback": None,
            "phase": WorkflowPhase.BREAKDOWN_USER_STORY,
            "current_bc_index": 0,
            "messages": [
                HumanMessage(content="APPROVED"),
                AIMessage(content="Bounded Contexts approved! Moving to user story breakdown..."),
            ],
        }
    elif feedback:
        # User requested changes - go back to identification with feedback
        return {
            "awaiting_human_approval": False,
            "human_feedback": None,
            "phase": WorkflowPhase.IDENTIFY_BC,
            "messages": [
                HumanMessage(content=feedback),
                AIMessage(content=f"I'll revise the Bounded Contexts based on your feedback: {feedback}"),
            ],
        }
    else:
        # Still waiting for approval
        return {"awaiting_human_approval": True}


