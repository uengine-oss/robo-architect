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
from api.platform.observability.request_logging import summarize_for_log
from api.platform.observability.smart_logger import SmartLogger

from api.platform.keys import slugify

from .node_runtime import dump_model, get_llm
from .prompts import IDENTIFY_POLICIES_PROMPT, SYSTEM_PROMPT
from .state import EventStormingState, WorkflowPhase
from .structured_outputs import PolicyList


def identify_policies_node(state: EventStormingState) -> Dict[str, Any]:
    """Identify Policies for cross-BC communication."""
    llm = get_llm()

    user_stories_text = "\n".join(
        [f"[{us.get('id')}] As a {us.get('role', 'user')}, I want to {us.get('action', '?')}" for us in (state.user_stories or [])]
    )

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

    # Collect commands by BC (deterministic)
    commands_by_bc: dict[str, str] = {}
    for bc in state.approved_bcs or []:
        bc_commands: list[str] = []
        for agg in state.approved_aggregates.get(bc.id, []) or []:
            for cmd in state.command_candidates.get(agg.id, []) or []:
                bc_commands.append(f"- {cmd.name}: {cmd.description}")
        commands_by_bc[bc.name] = "\n".join(bc_commands) if bc_commands else "No commands"

    commands_text = "\n".join([f"{bc_name}:\n{cmds}" for bc_name, cmds in commands_by_bc.items()])

    bc_text = "\n".join([f"- {bc.name}: {bc.description}" for bc in state.approved_bcs])

    prompt = IDENTIFY_POLICIES_PROMPT.format(
        user_stories=user_stories_text,
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
                "bounded_contexts": summarize_for_log(state.approved_bcs or []),
                "events": summarize_for_log(all_events),
                "prompt": prompt if AI_AUDIT_LOG_FULL_PROMPT else summarize_for_log(prompt),
                "system_prompt": SYSTEM_PROMPT,
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
                    "policies": summarize_for_log(
                        [{"name": getattr(p, "name", None), "target_bc": getattr(p, "target_bc", None)} for p in policies]
                    ),
                    "response": dump_model(response) if AI_AUDIT_LOG_FULL_OUTPUT else summarize_for_log(dump_model(response)),
                },
            }
        )
    policies = response.policies
    # Fill missing ids/keys deterministically (in-memory only).
    for p in policies or []:
        target = getattr(p, "target_bc", "") or "target"
        if not getattr(p, "key", None):
            try:
                p.key = f"{slugify(target)}.{slugify(p.name)}"
            except Exception:
                pass
        if not getattr(p, "id", None):
            try:
                p.id = getattr(p, "key", None) or f"{slugify(target)}.{slugify(p.name)}"
            except Exception:
                pass

        # GWT will be generated in generate_gwt_node after all commands/events/policies are created

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
            "phase": WorkflowPhase.GENERATE_GWT,
            "messages": [
                HumanMessage(content="APPROVED"),
                AIMessage(content="Policies approved! Generating GWT structures..."),
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


