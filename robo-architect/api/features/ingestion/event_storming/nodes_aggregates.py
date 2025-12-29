"""
Event Storming Nodes: aggregate extraction + approval
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
from .prompts import EXTRACT_AGGREGATES_PROMPT, SYSTEM_PROMPT
from .state import EventStormingState, WorkflowPhase
from .structured_outputs import AggregateList


def extract_aggregates_node(state: EventStormingState) -> Dict[str, Any]:
    """Extract Aggregates for each Bounded Context."""
    if state.current_bc_index >= len(state.approved_bcs):
        return {
            "phase": WorkflowPhase.APPROVE_AGGREGATES,
            "awaiting_human_approval": True,
            "current_bc_index": 0,
        }

    current_bc = state.approved_bcs[state.current_bc_index]
    llm = get_llm()

    # Get breakdowns for this BC
    bc_breakdowns = [bd for bd in state.breakdowns if bd.user_story_id in current_bc.user_story_ids]

    breakdowns_text = "\n".join(
        [
            f"User Story: {bd.user_story_id}\n"
            f"  Sub-tasks: {', '.join(bd.sub_tasks)}\n"
            f"  Domain Concepts: {', '.join(bd.domain_concepts)}\n"
            f"  Potential Aggregates: {', '.join(bd.potential_aggregates)}"
            for bd in bc_breakdowns
        ]
    )

    # Extract short BC ID for aggregate naming (e.g., BC-ORDER -> ORDER)
    bc_id_short = current_bc.id.replace("BC-", "")

    prompt = EXTRACT_AGGREGATES_PROMPT.format(
        bc_name=current_bc.name,
        bc_id=current_bc.id,
        bc_id_short=bc_id_short,
        bc_description=current_bc.description,
        breakdowns=breakdowns_text,
    )

    structured_llm = llm.with_structured_output(AggregateList)

    provider, model = get_llm_provider_model()
    if AI_AUDIT_LOG_ENABLED:
        SmartLogger.log(
            "INFO",
            "EventStorming: extract aggregates - LLM invoke starting.",
            category="agent.nodes.extract_aggregates.llm.start",
            params={
                "llm": {"provider": provider, "model": model},
                "bc": {"id": current_bc.id, "name": current_bc.name},
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
        aggs = getattr(response, "aggregates", []) or []
        SmartLogger.log(
            "INFO",
            "EventStorming: extract aggregates - LLM invoke completed.",
            category="agent.nodes.extract_aggregates.llm.done",
            params={
                "llm": {"provider": provider, "model": model},
                "bc": {"id": current_bc.id, "name": current_bc.name},
                "llm_ms": llm_ms,
                "result": {
                    "aggregates_count": len(aggs),
                    "aggregates": summarize_for_log(
                        [{"id": getattr(a, "id", None), "name": getattr(a, "name", None)} for a in aggs]
                    ),
                    "response": dump_model(response) if AI_AUDIT_LOG_FULL_OUTPUT else summarize_for_log(dump_model(response)),
                },
            }
        )
    aggregates = response.aggregates

    # Store aggregates for this BC
    aggregate_candidates = dict(state.aggregate_candidates)
    aggregate_candidates[current_bc.id] = aggregates

    return {
        "aggregate_candidates": aggregate_candidates,
        "current_bc_index": state.current_bc_index + 1,
        "messages": [AIMessage(content=f"Identified {len(aggregates)} aggregates for BC '{current_bc.name}'.")],
    }


def approve_aggregates_node(state: EventStormingState) -> Dict[str, Any]:
    """Process human approval for Aggregates."""
    feedback = state.human_feedback

    if feedback and feedback.upper() == "APPROVED":
        return {
            "approved_aggregates": state.aggregate_candidates,
            "awaiting_human_approval": False,
            "human_feedback": None,
            "phase": WorkflowPhase.EXTRACT_COMMANDS,
            "messages": [
                HumanMessage(content="APPROVED"),
                AIMessage(content="Aggregates approved! Extracting commands..."),
            ],
        }
    elif feedback:
        return {
            "awaiting_human_approval": False,
            "human_feedback": None,
            "phase": WorkflowPhase.EXTRACT_AGGREGATES,
            "current_bc_index": 0,
            "messages": [
                HumanMessage(content=feedback),
                AIMessage(content=f"I'll revise the Aggregates based on your feedback: {feedback}"),
            ],
        }
    else:
        # Display aggregates for review
        agg_text = ""
        for bc_id, aggregates in state.aggregate_candidates.items():
            bc = next((bc for bc in state.approved_bcs if bc.id == bc_id), None)
            bc_name = bc.name if bc else bc_id
            agg_text += f"\n{bc_name}:\n"
            for agg in aggregates:
                agg_text += f"  - {agg.name}: {agg.description}\n"
                agg_text += f"    Invariants: {', '.join(agg.invariants)}\n"

        return {
            "awaiting_human_approval": True,
            "messages": [
                AIMessage(content=f"Please review the proposed Aggregates:\n{agg_text}\n\nType 'APPROVED' or provide feedback.")
            ],
        }


