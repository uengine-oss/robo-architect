"""
Event Storming Nodes: event extraction (from commands)
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
from api.platform.observability.request_logging import summarize_for_log
from api.platform.observability.smart_logger import SmartLogger

from api.platform.keys import slugify

from .node_runtime import dump_model, get_llm
from .prompts import EXTRACT_EVENTS_PROMPT, SYSTEM_PROMPT
from .state import EventStormingState, WorkflowPhase
from .structured_outputs import EventList


def extract_events_node(state: EventStormingState) -> Dict[str, Any]:
    """Extract Events for each Command."""
    llm = get_llm()
    event_candidates = dict(state.event_candidates)

    for agg_id, commands in state.command_candidates.items():
        # Include user story IDs in command context
        commands_text = "\n".join([f"- {cmd.name} (implements: {cmd.user_story_ids}): {cmd.description}" for cmd in commands])

        # Find aggregate name and BC
        agg_name = agg_id
        bc_name = ""
        bc_short = ""
        for bc_id, aggregates in state.approved_aggregates.items():
            for agg in aggregates:
                if agg.id == agg_id:
                    agg_name = agg.name
                    bc = next((b for b in state.approved_bcs if b.id == bc_id), None)
                    if bc:
                        bc_name = bc.name
                        bc_short = slugify(bc.name).upper()
                    break

        prompt = EXTRACT_EVENTS_PROMPT.format(
            aggregate_name=agg_name,
            bc_name=bc_name,
            bc_short=bc_short,
            commands=commands_text,
        )

        structured_llm = llm.with_structured_output(EventList)

        provider, model = get_llm_provider_model()
        if AI_AUDIT_LOG_ENABLED:
            SmartLogger.log(
                "INFO",
                "EventStorming: extract events - LLM invoke starting.",
                category="agent.nodes.extract_events.llm.start",
                params={
                    "llm": {"provider": provider, "model": model},
                    "aggregate": {"id": agg_id, "name": agg_name},
                    "bc": {"name": bc_name, "short": bc_short},
                    "prompt": prompt if AI_AUDIT_LOG_FULL_PROMPT else summarize_for_log(prompt),
                    "system_prompt": SYSTEM_PROMPT,
                }
            )

        t_llm0 = time.perf_counter()
        response = structured_llm.invoke([SystemMessage(content=SYSTEM_PROMPT), HumanMessage(content=prompt)])
        llm_ms = int((time.perf_counter() - t_llm0) * 1000)

        if AI_AUDIT_LOG_ENABLED:
            evts = getattr(response, "events", []) or []
            SmartLogger.log(
                "INFO",
                "EventStorming: extract events - LLM invoke completed.",
                category="agent.nodes.extract_events.llm.done",
                params={
                    "llm": {"provider": provider, "model": model},
                    "aggregate": {"id": agg_id, "name": agg_name},
                    "bc": {"name": bc_name, "short": bc_short},
                    "llm_ms": llm_ms,
                    "result": {
                        "events": summarize_for_log(
                            [{"id": getattr(e, "id", None), "name": getattr(e, "name", None)} for e in evts]
                        ),
                        "response": dump_model(response) if AI_AUDIT_LOG_FULL_OUTPUT else summarize_for_log(dump_model(response)),
                    },
                }
            )
        evts = response.events or []
        # Fill missing ids/keys deterministically (in-memory only).
        # Best-effort: derive command key from aggregate+command names if needed.
        cmd_key_prefix = f"{slugify(bc_name)}.{slugify(agg_name)}"
        for e in evts:
            if not getattr(e, "key", None):
                try:
                    e.key = f"{cmd_key_prefix}.{slugify(e.name)}@1.0.0"
                except Exception:
                    pass
            if not getattr(e, "id", None):
                try:
                    e.id = getattr(e, "key", None) or f"{cmd_key_prefix}.{slugify(e.name)}@1.0.0"
                except Exception:
                    pass
        event_candidates[agg_id] = evts

    return {
        "event_candidates": event_candidates,
        "phase": WorkflowPhase.IDENTIFY_POLICIES,
        "messages": [AIMessage(content="Extracted events for all commands. Identifying cross-BC policies...")],
    }


