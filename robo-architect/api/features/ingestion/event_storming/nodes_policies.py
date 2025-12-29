"""
Event Storming Nodes: policy identification + approval
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
from .prompts import IDENTIFY_POLICIES_PROMPT, SYSTEM_PROMPT
from .state import EventStormingState, WorkflowPhase
from .structured_outputs import PolicyList


def identify_policies_node(state: EventStormingState) -> Dict[str, Any]:
    """Identify Policies for cross-BC communication."""
    llm = get_llm()

    # Collect all events
    all_events = []
    for agg_id, events in state.event_candidates.items():
        # Find which BC this aggregate belongs to
        bc_name = "Unknown"
        for bc_id, aggregates in state.approved_aggregates.items():
            for agg in aggregates:
                if agg.id == agg_id:
                    bc = next((b for b in state.approved_bcs if b.id == bc_id), None)
                    bc_name = bc.name if bc else bc_id
                    break

        for evt in events:
            all_events.append(f"- {evt.name} (from {bc_name}): {evt.description}")

    events_text = "\n".join(all_events)

    # Collect commands by BC
    commands_by_bc = {}
    for bc in state.approved_bcs:
        bc_commands = []
        for agg_id, aggregates in state.approved_aggregates.items():
            if agg_id == bc.id or any(a.id.startswith(bc.id.replace("BC-", "AGG-")) for a in aggregates):
                continue
        # Get commands for aggregates in this BC
        for agg_id, commands in state.command_candidates.items():
            for aggregates in state.approved_aggregates.get(bc.id, []):
                if agg_id == aggregates.id:
                    bc_commands.extend([f"- {cmd.name}: {cmd.description}" for cmd in commands])
        if not bc_commands:
            # Fallback: collect all commands for this BC's aggregates
            for agg in state.approved_aggregates.get(bc.id, []):
                for cmd in state.command_candidates.get(agg.id, []):
                    bc_commands.append(f"- {cmd.name}: {cmd.description}")
        commands_by_bc[bc.name] = "\n".join(bc_commands) if bc_commands else "No commands"

    commands_text = "\n".join([f"{bc_name}:\n{cmds}" for bc_name, cmds in commands_by_bc.items()])

    bc_text = "\n".join([f"- {bc.name}: {bc.description}" for bc in state.approved_bcs])

    prompt = IDENTIFY_POLICIES_PROMPT.format(
        events=events_text,
        commands_by_bc=commands_text,
        bounded_contexts=bc_text,
    )

    structured_llm = llm.with_structured_output(PolicyList)

    provider, model = get_llm_provider_model()
    if AI_AUDIT_LOG_ENABLED:
        SmartLogger.log(
            "INFO",
            "EventStorming: identify policies - LLM invoke starting.",
            category="agent.nodes.identify_policies.llm.start",
            params={
                "llm": {"provider": provider, "model": model},
                "bounded_contexts_count": len(state.approved_bcs or []),
                "events_count": len(all_events),
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
        policies = getattr(response, "policies", []) or []
        SmartLogger.log(
            "INFO",
            "EventStorming: identify policies - LLM invoke completed.",
            category="agent.nodes.identify_policies.llm.done",
            params={
                "llm": {"provider": provider, "model": model},
                "llm_ms": llm_ms,
                "result": {
                    "policies_count": len(policies),
                    "policies": summarize_for_log(
                        [{"name": getattr(p, "name", None), "target_bc": getattr(p, "target_bc", None)} for p in policies]
                    ),
                    "response": dump_model(response) if AI_AUDIT_LOG_FULL_OUTPUT else summarize_for_log(dump_model(response)),
                },
            }
        )
    policies = response.policies

    return {
        "policy_candidates": policies,
        "phase": WorkflowPhase.APPROVE_POLICIES,
        "awaiting_human_approval": True,
        "messages": [AIMessage(content=f"Identified {len(policies)} cross-BC policies. Please review...")],
    }


def approve_policies_node(state: EventStormingState) -> Dict[str, Any]:
    """Process human approval for Policies."""
    feedback = state.human_feedback

    if feedback and feedback.upper() == "APPROVED":
        return {
            "approved_policies": state.policy_candidates,
            "awaiting_human_approval": False,
            "human_feedback": None,
            "phase": WorkflowPhase.SAVE_TO_GRAPH,
            "messages": [
                HumanMessage(content="APPROVED"),
                AIMessage(content="Policies approved! Saving everything to Neo4j..."),
            ],
        }
    elif feedback:
        return {
            "awaiting_human_approval": False,
            "human_feedback": None,
            "phase": WorkflowPhase.IDENTIFY_POLICIES,
            "messages": [
                HumanMessage(content=feedback),
                AIMessage(content=f"I'll revise the Policies based on your feedback: {feedback}"),
            ],
        }
    else:
        # Display policies for review
        pol_text = "\n".join(
            [
                f"- {pol.name}\n  When: {pol.trigger_event} → Then: {pol.invoke_command} (in {pol.target_bc})"
                for pol in state.policy_candidates
            ]
        )

        return {
            "awaiting_human_approval": True,
            "messages": [
                AIMessage(content=f"Please review the proposed Policies:\n\n{pol_text}\n\nType 'APPROVED' or provide feedback.")
            ],
        }


