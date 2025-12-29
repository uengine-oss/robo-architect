"""
Event Storming Nodes: command extraction
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
from .prompts import EXTRACT_COMMANDS_PROMPT, SYSTEM_PROMPT
from .state import EventStormingState, WorkflowPhase
from .structured_outputs import CommandList


def extract_commands_node(state: EventStormingState) -> Dict[str, Any]:
    """Extract Commands for each Aggregate."""
    llm = get_llm()
    command_candidates = dict(state.command_candidates)

    for bc_id, aggregates in state.approved_aggregates.items():
        bc = next((bc for bc in state.approved_bcs if bc.id == bc_id), None)
        if not bc:
            continue

        bc_id_short = bc.id.replace("BC-", "")

        for agg in aggregates:
            # Get user stories that this aggregate implements
            agg_story_ids = agg.user_story_ids if agg.user_story_ids else bc.user_story_ids
            agg_stories = [us for us in state.user_stories if us["id"] in agg_story_ids]
            stories_context = "\n".join(
                [f"[{us['id']}] As a {us.get('role', 'user')}, I want to {us.get('action', '?')}" for us in agg_stories]
            )

            prompt = EXTRACT_COMMANDS_PROMPT.format(
                aggregate_name=agg.name,
                aggregate_id=agg.id,
                bc_name=bc.name,
                bc_short=bc_id_short,
                user_story_context=stories_context,
            )

            structured_llm = llm.with_structured_output(CommandList)

            provider, model = get_llm_provider_model()
            if AI_AUDIT_LOG_ENABLED:
                SmartLogger.log(
                    "INFO",
                    "EventStorming: extract commands - LLM invoke starting.",
                    category="agent.nodes.extract_commands.llm.start",
                    params={
                        "llm": {"provider": provider, "model": model},
                        "bc": {"id": bc.id, "name": bc.name},
                        "aggregate": {"id": agg.id, "name": agg.name},
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
                cmds = getattr(response, "commands", []) or []
                SmartLogger.log(
                    "INFO",
                    "EventStorming: extract commands - LLM invoke completed.",
                    category="agent.nodes.extract_commands.llm.done",
                    params={
                        "llm": {"provider": provider, "model": model},
                        "bc": {"id": bc.id, "name": bc.name},
                        "aggregate": {"id": agg.id, "name": agg.name},
                        "llm_ms": llm_ms,
                        "result": {
                            "commands_count": len(cmds),
                            "commands": summarize_for_log(
                                [{"id": getattr(c, "id", None), "name": getattr(c, "name", None)} for c in cmds]
                            ),
                            "response": dump_model(response) if AI_AUDIT_LOG_FULL_OUTPUT else summarize_for_log(dump_model(response)),
                        },
                    }
                )
            command_candidates[agg.id] = response.commands

    return {
        "command_candidates": command_candidates,
        "phase": WorkflowPhase.EXTRACT_EVENTS,
        "messages": [AIMessage(content="Extracted commands for all aggregates. Moving to event extraction...")],
    }


