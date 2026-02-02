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
from api.platform.observability.request_logging import summarize_for_log
from api.platform.observability.smart_logger import SmartLogger

from api.platform.keys import slugify

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
    # Ensure we have a stable in-memory identifier even if LLM omitted `id`.
    if not getattr(current_bc, "id", None):
        fallback = getattr(current_bc, "key", None) or slugify(current_bc.name)
        try:
            current_bc.id = fallback
        except Exception:
            pass
        if not getattr(current_bc, "key", None):
            try:
                current_bc.key = fallback
            except Exception:
                pass
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

    # Collect existing aggregates from other BCs (already extracted) for reference validation
    existing_aggregates_text = ""
    all_existing_aggregate_names = set()
    for other_bc_id, other_aggregates in state.aggregate_candidates.items():
        if other_bc_id != current_bc.id and other_aggregates:
            other_bc = next((bc for bc in state.approved_bcs if bc.id == other_bc_id), None)
            bc_name = other_bc.name if other_bc else other_bc_id
            agg_names = [getattr(agg, "name", "") for agg in other_aggregates if getattr(agg, "name", None)]
            if agg_names:
                existing_aggregates_text += f"  - {bc_name}: {', '.join(agg_names)}\n"
                all_existing_aggregate_names.update(agg_names)
    
    if not existing_aggregates_text:
        existing_aggregates_text = "  (No aggregates have been extracted from other Bounded Contexts yet.)"
    else:
        existing_aggregates_text = "The following Aggregates already exist in other Bounded Contexts and can be referenced:\n" + existing_aggregates_text

    # Legacy prompt helper (no longer derived from prefixed ids)
    bc_id_short = slugify(current_bc.name).upper()

    prompt = EXTRACT_AGGREGATES_PROMPT.format(
        bc_name=current_bc.name,
        bc_id=current_bc.id,
        bc_id_short=bc_id_short,
        bc_description=current_bc.description,
        breakdowns=breakdowns_text,
        existing_aggregates=existing_aggregates_text,
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
                "prompt": prompt if AI_AUDIT_LOG_FULL_PROMPT else summarize_for_log(prompt),
                "system_prompt": SYSTEM_PROMPT,
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
                    "aggregates": summarize_for_log(
                        [{"id": getattr(a, "id", None), "name": getattr(a, "name", None)} for a in aggs]
                    ),
                    "response": dump_model(response) if AI_AUDIT_LOG_FULL_OUTPUT else summarize_for_log(dump_model(response)),
                },
            }
        )
    aggregates = response.aggregates
    # Fill missing ids/keys with deterministic natural-key-like strings (in-memory only).
    bc_key_value = getattr(current_bc, "key", None) or slugify(current_bc.name)
    for a in aggregates or []:
        if not getattr(a, "key", None):
            try:
                a.key = f"{bc_key_value}.{slugify(a.name)}"
            except Exception:
                pass
        if not getattr(a, "id", None):
            try:
                a.id = getattr(a, "key", None) or f"{bc_key_value}.{slugify(a.name)}"
            except Exception:
                pass

    # Validate and fix Value Object references
    # Collect all existing aggregate names (from other BCs and current BC)
    all_existing_aggregate_names = set()
    for other_bc_id, other_aggregates in state.aggregate_candidates.items():
        if other_aggregates:
            for agg in other_aggregates:
                agg_name = getattr(agg, "name", None)
                if agg_name:
                    all_existing_aggregate_names.add(agg_name)
    # Also include aggregates being extracted now
    for agg in aggregates or []:
        agg_name = getattr(agg, "name", None)
        if agg_name:
            all_existing_aggregate_names.add(agg_name)
    
    # Validate and remove invalid references
    validation_warnings = []
    for agg in aggregates or []:
        if hasattr(agg, "value_objects") and agg.value_objects:
            for vo in agg.value_objects:
                ref_name = getattr(vo, "referenced_aggregate_name", None)
                if ref_name and ref_name not in all_existing_aggregate_names:
                    # Remove invalid reference
                    validation_warnings.append(
                        f"Removed invalid reference: {agg.name}.{getattr(vo, 'name', 'unknown')} → {ref_name} (Aggregate does not exist)"
                    )
                    try:
                        vo.referenced_aggregate_name = None
                    except Exception:
                        pass
                    SmartLogger.log(
                        "WARNING",
                        f"Removed invalid Aggregate reference in {current_bc.name}.{agg.name}",
                        category="event_storming.aggregates.reference_validation.auto_fix",
                        params={
                            "bc_id": current_bc.id,
                            "bc_name": current_bc.name,
                            "aggregate_name": getattr(agg, "name", None),
                            "vo_name": getattr(vo, "name", None),
                            "referenced_aggregate_name": ref_name,
                        },
                    )
    
    if validation_warnings:
        SmartLogger.log(
            "INFO",
            f"Auto-fixed {len(validation_warnings)} invalid Aggregate references",
            category="event_storming.aggregates.reference_validation.auto_fix_summary",
            params={
                "bc_id": current_bc.id,
                "bc_name": current_bc.name,
                "warnings": validation_warnings,
            },
        )

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
        # Collect all aggregate names across all BCs for reference validation
        all_aggregate_names = set()
        for aggregates in state.aggregate_candidates.values():
            for agg in aggregates:
                if hasattr(agg, "name") and agg.name:
                    all_aggregate_names.add(agg.name)
        
        # Validate Value Object references
        reference_warnings = []
        for bc_id, aggregates in state.aggregate_candidates.items():
            bc = next((bc for bc in state.approved_bcs if bc.id == bc_id), None)
            bc_name = bc.name if bc else bc_id
            for agg in aggregates:
                if hasattr(agg, "value_objects") and agg.value_objects:
                    for vo in agg.value_objects:
                        ref_name = getattr(vo, "referenced_aggregate_name", None)
                        if ref_name:
                            if ref_name not in all_aggregate_names:
                                reference_warnings.append(
                                    f"⚠️ {bc_name}.{agg.name}: Value Object '{getattr(vo, 'name', 'unknown')}' references non-existent Aggregate '{ref_name}'"
                                )
        
        # Display aggregates for review
        agg_text = ""
        for bc_id, aggregates in state.aggregate_candidates.items():
            bc = next((bc for bc in state.approved_bcs if bc.id == bc_id), None)
            bc_name = bc.name if bc else bc_id
            agg_text += f"\n{bc_name}:\n"
            for agg in aggregates:
                agg_text += f"  - {agg.name}: {agg.description}\n"
                agg_text += f"    Root Entity: {agg.root_entity}\n"
                agg_text += f"    Invariants: {', '.join(agg.invariants) if agg.invariants else 'None'}\n"
                if agg.enumerations:
                    enum_names = [e.name for e in agg.enumerations]
                    agg_text += f"    Enumerations: {', '.join(enum_names)}\n"
                if agg.value_objects:
                    vo_info = []
                    for vo in agg.value_objects:
                        vo_name = getattr(vo, "name", "unknown")
                        ref_name = getattr(vo, "referenced_aggregate_name", None)
                        if ref_name:
                            vo_info.append(f"{vo_name} (→ {ref_name})")
                        else:
                            vo_info.append(vo_name)
                    agg_text += f"    Value Objects: {', '.join(vo_info)}\n"
                if agg.user_story_ids:
                    agg_text += f"    User Stories: {', '.join(agg.user_story_ids)}\n"
        
        # Add reference validation warnings
        review_message = f"Please review the proposed Aggregates:\n{agg_text}\n"
        if reference_warnings:
            review_message += "\n⚠️ Reference Validation Warnings:\n"
        for warning in reference_warnings:
            review_message += f"{warning}\n"
            SmartLogger.log(
                "WARNING",
                warning,
                category="event_storming.aggregates.reference_validation",
                params={
                    "bc_id": bc_id if "bc_id" in locals() else None,
                    "aggregate_candidates": {
                        bc_id: len(aggs) for bc_id, aggs in state.aggregate_candidates.items()
                    },
                },
            )
        review_message += "\nType 'APPROVED' or provide feedback."

        return {
            "awaiting_human_approval": True,
            "messages": [
                AIMessage(content=review_message)
            ],
        }


