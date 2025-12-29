"""
Change Planning: Plan Finalization

Business capability: generate an APPLY-ready change plan grounded in impacted objects + propagation results.
"""

from __future__ import annotations

import json
import time
from collections import Counter
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


def generate_plan_node(state: ChangePlanningState) -> Dict[str, Any]:
    """
    Generate a comprehensive change plan considering:
    - Changes within existing connections
    - New connections to found related objects
    - Creating new objects if needed
    """
    llm = get_llm()

    SmartLogger.log(
        "INFO",
        "Plan finalization started: generating an APPLY-ready change plan grounded in connected objects + propagation candidates.",
        category="agent.change_graph.plan_finalizer.start",
        params={
            "user_story_id": state.user_story_id,
            "scope": state.change_scope.value if state.change_scope else None,
            "connected_objects_count": len(state.connected_objects or []),
            "propagation": {
                "enabled": state.propagation_enabled,
                "confirmed": len(state.propagation_confirmed or []),
                "review": len(state.propagation_review or []),
                "rounds": state.propagation_rounds,
                "stop_reason": state.propagation_stop_reason,
            },
            "related_objects_count": len(state.related_objects or []),
        }
    )

    # Build context
    original = state.original_user_story
    edited = state.edited_user_story

    connected_text = "\n".join(
        [f"- {obj.get('type', 'Unknown')} [{obj.get('id')}]: {obj.get('name', '?')}" for obj in state.connected_objects]
    )

    related_text = (
        "\n".join(
            [f"- {obj.type} [{obj.id}]: {obj.name} (BC: {obj.bcName}, similarity: {obj.similarity:.2f})" for obj in state.related_objects]
        )
        if state.related_objects
        else "No related objects found via search"
    )

    # Propagation context (confirmed + review). Use confirmed by default for plan finalization.
    confirmed = state.propagation_confirmed or []
    review = state.propagation_review or []

    confirmed_text = (
        "\n".join(
            [
                f"- {c.type} [{c.id}]: {c.name} (BC: {c.bcName or 'Unknown'}, confidence: {c.confidence:.2f})\n"
                f"  reason: {c.reason}\n"
                f"  evidence: {', '.join(c.evidence_paths[:2]) if c.evidence_paths else 'n/a'}"
                for c in confirmed
            ]
        )
        if confirmed
        else "None"
    )

    review_text = (
        "\n".join(
            [
                f"- {c.type} [{c.id}]: {c.name} (BC: {c.bcName or 'Unknown'}, confidence: {c.confidence:.2f})\n"
                f"  reason: {c.reason}\n"
                f"  evidence: {', '.join(c.evidence_paths[:2]) if c.evidence_paths else 'n/a'}"
                for c in review[:20]
            ]
        )
        if review
        else "None"
    )

    prompt = f"""Generate an APPLY-READY change plan (finalization) for this User Story modification.

## Change Scope: {state.change_scope.value if state.change_scope else 'unknown'}
{state.scope_reasoning}

## Original User Story
Role: {original.get('role', 'user')}
Action: {original.get('action', '')}
Benefit: {original.get('benefit', '')}

## Modified User Story
Role: {edited.get('role', 'user')}
Action: {edited.get('action', '')}  
Benefit: {edited.get('benefit', '')}

## Currently Connected Objects
{connected_text if connected_text else "None"}

## Propagation (Confirmed impacted candidates)
{confirmed_text}

## Propagation (Review candidates - lower confidence, include only if necessary)
{review_text}

## Related Objects Found (from other BCs)
{related_text}

## Your Task
Finalize a detailed change plan using the objects above as your grounding context. IMPORTANT:

1. Prefer using the Propagation Confirmed candidates as the authoritative set of impacted nodes.
2. You MAY include some Review candidates only when the justification is strong and required for consistency.
3. Do NOT invent random node ids. If you propose "create", you must use a NEW id (not existing ones).
4. Keep actions within what /api/change/apply supports:
   - action: rename, update, create, connect, delete
   - create targetType: Policy, Command, Event (Aggregate create is NOT supported by apply)
   - connect connectionType: TRIGGERS, INVOKES, IMPLEMENTS
5. Cross-BC connections must use the Event-Policy-Command pattern:
   - Event (source BC) TRIGGERS Policy (target or intermediary)
   - Policy INVOKES Command (target BC)

For each change, specify:
- action: "create", "update", "connect", or "rename"
- targetType: "Aggregate", "Command", "Event", or "Policy"
- For connections: specify connectionType (TRIGGERS, INVOKES) and sourceId

Respond in this exact JSON format:
{{
    "summary": "Brief summary of the plan",
    "changes": [
        {{
            "action": "connect",
            "targetType": "Policy",
            "targetId": "POL-NEW-POLICY-ID",
            "targetName": "PolicyName",
            "targetBcId": "BC-ID",
            "targetBcName": "BC Name",
            "description": "What this change does",
            "reason": "Why this change is needed",
            "connectionType": "TRIGGERS or INVOKES",
            "sourceId": "EVT-SOURCE-ID"
        }},
        ...
    ]
}}"""

    provider, model = get_llm_provider_model()
    system_msg = """You are a DDD expert creating change plans.
When connecting BCs, always use the Event-Policy-Command pattern:
- Event (from source BC) TRIGGERS Policy
- Policy INVOKES Command (in target BC)"""

    if AI_AUDIT_LOG_ENABLED:
        SmartLogger.log(
            "INFO",
            "Plan finalization: LLM invoke starting.",
            category="agent.change_graph.plan_finalizer.llm.start",
            params={
                "user_story_id": state.user_story_id,
                "scope": state.change_scope.value if state.change_scope else None,
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
            "Plan finalization: LLM invoke completed.",
            category="agent.change_graph.plan_finalizer.llm.done",
            params={
                "user_story_id": state.user_story_id,
                "scope": state.change_scope.value if state.change_scope else None,
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
                    from_value=change.get("from"),
                    to_value=change.get("to"),
                    connectionType=change.get("connectionType"),
                    sourceId=change.get("sourceId"),
                )
            )

        # High-signal summary for log-driven verification
        action_counts = Counter([c.action for c in proposed_changes])
        connect_types = Counter([c.connectionType for c in proposed_changes if c.action == "connect" and c.connectionType])
        create_types = Counter([c.targetType for c in proposed_changes if c.action == "create" and c.targetType])

        SmartLogger.log(
            "INFO",
            "Plan finalization completed: proposed changes are ready for human approval and /apply execution.",
            category="agent.change_graph.plan_finalizer.done",
            params={
                "user_story_id": state.user_story_id,
                "scope": state.change_scope.value if state.change_scope else None,
                "summary_preview": (result.get("summary") or "")[:400],
                "changes_count": len(proposed_changes),
                "action_counts": dict(action_counts),
                "connect_types": dict(connect_types),
                "create_types": dict(create_types),
            }
        )

        return {
            "phase": ChangePlanningPhase.AWAIT_APPROVAL,
            "proposed_changes": proposed_changes,
            "plan_summary": result.get("summary", ""),
            "awaiting_approval": True,
        }

    except Exception as e:
        SmartLogger.log(
            "ERROR",
            "Plan finalization failed: LLM response could not be parsed into the expected JSON shape.",
            category="agent.change_graph.plan_finalizer.parse_error",
            params={
                "user_story_id": state.user_story_id,
                "error": str(e),
                "llm_raw_preview": (getattr(response, "content", "") or "")[:1500],
            }
        )
        return {
            "phase": ChangePlanningPhase.AWAIT_APPROVAL,
            "proposed_changes": [],
            "plan_summary": f"Error generating plan: {str(e)}",
            "awaiting_approval": True,
            "error": str(e),
        }


