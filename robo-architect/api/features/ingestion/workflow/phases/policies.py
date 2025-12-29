from __future__ import annotations

import time
from typing import Any, AsyncGenerator

from langchain_core.messages import HumanMessage, SystemMessage

from api.platform.env import (
    AI_AUDIT_LOG_ENABLED,
    AI_AUDIT_LOG_FULL_OUTPUT,
    AI_AUDIT_LOG_FULL_PROMPT,
)
from api.features.ingestion.ingestion_contracts import IngestionPhase, ProgressEvent
from api.features.ingestion.event_storming.nodes import PolicyList
from api.features.ingestion.event_storming.prompts import IDENTIFY_POLICIES_PROMPT, SYSTEM_PROMPT
from api.features.ingestion.workflow.ingestion_workflow_context import IngestionWorkflowContext
from api.platform.env import get_llm_provider_model
from api.platform.observability.request_logging import sha256_text, summarize_for_log
from api.platform.observability.smart_logger import SmartLogger


async def identify_policies_phase(ctx: IngestionWorkflowContext) -> AsyncGenerator[ProgressEvent, None]:
    """
    Phase 7: identify policies using LLM and create them with TRIGGERS/INVOKES relationships.
    """
    yield ProgressEvent(phase=IngestionPhase.IDENTIFYING_POLICIES, message="Policy 식별 중...", progress=90)

    all_events_list: list[str] = []
    for events in ctx.events_by_agg.values():
        for evt in events:
            all_events_list.append(f"- {evt.name}")
    events_text = "\n".join(all_events_list)

    commands_by_bc: dict[str, str] = {}
    for bc in ctx.bounded_contexts:
        bc_cmds: list[str] = []
        for agg in ctx.aggregates_by_bc.get(bc.id, []):
            for cmd in ctx.commands_by_agg.get(agg.id, []):
                bc_cmds.append(f"- {cmd.name}")
        commands_by_bc[bc.name] = "\n".join(bc_cmds) if bc_cmds else "No commands"

    commands_text = "\n".join([f"{bc_name}:\n{cmds}" for bc_name, cmds in commands_by_bc.items()])
    bc_text = "\n".join([f"- {bc.name}: {bc.description}" for bc in ctx.bounded_contexts])

    prompt = IDENTIFY_POLICIES_PROMPT.format(events=events_text, commands_by_bc=commands_text, bounded_contexts=bc_text)
    structured_llm = ctx.llm.with_structured_output(PolicyList)

    try:
        provider, model = get_llm_provider_model()
        if AI_AUDIT_LOG_ENABLED:
            SmartLogger.log(
                "INFO",
                "Ingestion: identify policies - LLM invoke starting.",
                category="ingestion.llm.identify_policies.start",
                params={
                    "session_id": ctx.session.id,
                    "llm": {"provider": provider, "model": model},
                    "bounded_contexts_count": len(ctx.bounded_contexts),
                    "events_count": len(all_events_list),
                    "prompt_len": len(prompt),
                    "prompt_sha256": sha256_text(prompt),
                    "prompt": prompt if AI_AUDIT_LOG_FULL_PROMPT else summarize_for_log(prompt),
                    "system_sha256": sha256_text(SYSTEM_PROMPT),
                }
            )

        t_llm0 = time.perf_counter()
        pol_response = structured_llm.invoke([SystemMessage(content=SYSTEM_PROMPT), HumanMessage(content=prompt)])
        llm_ms = int((time.perf_counter() - t_llm0) * 1000)
        policies = pol_response.policies

        if AI_AUDIT_LOG_ENABLED:
            try:
                resp_dump = pol_response.model_dump() if hasattr(pol_response, "model_dump") else pol_response.dict()
            except Exception:
                resp_dump = {"__type__": type(pol_response).__name__, "__repr__": repr(pol_response)[:1000]}
            SmartLogger.log(
                "INFO",
                "Ingestion: identify policies - LLM invoke completed.",
                category="ingestion.llm.identify_policies.done",
                params={
                    "session_id": ctx.session.id,
                    "llm": {"provider": provider, "model": model},
                    "llm_ms": llm_ms,
                    "result": {
                        "policies_count": len(policies),
                        "policy_ids": summarize_for_log([getattr(p, "id", None) for p in policies]),
                        "response": resp_dump if AI_AUDIT_LOG_FULL_OUTPUT else summarize_for_log(resp_dump),
                    },
                }
            )
    except Exception as e:
        SmartLogger.log(
            "WARNING",
            "Policy identification failed (LLM)",
            category="ingestion.workflow.policies",
            params={"session_id": ctx.session.id, "error": str(e)},
        )
        policies = []

    ctx.policies = policies

    for pol in policies:
        trigger_event_id = None
        invoke_command_id = None
        target_bc_id = None

        for events in ctx.events_by_agg.values():
            for evt in events:
                if evt.name == pol.trigger_event:
                    trigger_event_id = evt.id
                    break

        for bc in ctx.bounded_contexts:
            if bc.name == pol.target_bc or bc.id == pol.target_bc:
                target_bc_id = bc.id
                for agg in ctx.aggregates_by_bc.get(bc.id, []):
                    for cmd in ctx.commands_by_agg.get(agg.id, []):
                        if cmd.name == pol.invoke_command:
                            invoke_command_id = cmd.id
                            break

        if trigger_event_id and invoke_command_id and target_bc_id:
            try:
                ctx.client.create_policy(
                    id=pol.id,
                    name=pol.name,
                    bc_id=target_bc_id,
                    trigger_event_id=trigger_event_id,
                    invoke_command_id=invoke_command_id,
                    description=pol.description,
                )

                yield ProgressEvent(
                    phase=IngestionPhase.IDENTIFYING_POLICIES,
                    message=f"Policy 생성: {pol.name}",
                    progress=95,
                    data={"type": "Policy", "object": {"id": pol.id, "name": pol.name, "type": "Policy", "parentId": target_bc_id}},
                )
            except Exception as e:
                SmartLogger.log(
                    "WARNING",
                    "Policy create skipped",
                    category="ingestion.neo4j.policy",
                    params={"session_id": ctx.session.id, "policy_id": pol.id, "error": str(e)},
                )


