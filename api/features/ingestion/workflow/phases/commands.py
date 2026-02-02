from __future__ import annotations

import asyncio
import time
from typing import Any, AsyncGenerator

from langchain_core.messages import HumanMessage, SystemMessage

from api.platform.env import (
    AI_AUDIT_LOG_ENABLED,
    AI_AUDIT_LOG_FULL_OUTPUT,
    AI_AUDIT_LOG_FULL_PROMPT,
)
from api.features.ingestion.ingestion_contracts import IngestionPhase, ProgressEvent
from api.features.ingestion.event_storming.nodes import CommandList
from api.features.ingestion.event_storming.prompts import EXTRACT_COMMANDS_PROMPT, SYSTEM_PROMPT
from api.features.ingestion.workflow.ingestion_workflow_context import IngestionWorkflowContext
from api.platform.env import get_llm_provider_model
from api.platform.observability.request_logging import summarize_for_log
from api.platform.observability.smart_logger import SmartLogger


async def extract_commands_phase(ctx: IngestionWorkflowContext) -> AsyncGenerator[ProgressEvent, None]:
    """
    Phase 5: extract commands per aggregate and persist them.
    """
    yield ProgressEvent(phase=IngestionPhase.EXTRACTING_COMMANDS, message="Command 추출 중...", progress=60)

    all_commands: dict[str, Any] = {}

    for bc in ctx.bounded_contexts:
        # Legacy field used only for prompt text; keep stable without prefix-based ids.
        bc_id_short = (getattr(bc, "name", "") or "").strip()
        bc_aggregates = ctx.aggregates_by_bc.get(bc.id, [])

        for agg in bc_aggregates:
            stories_context = "\n".join(
                [f"[{us.id}] As a {us.role}, I want to {us.action}" for us in ctx.user_stories if us.id in bc.user_story_ids]
            )

            prompt = EXTRACT_COMMANDS_PROMPT.format(
                aggregate_name=agg.name,
                aggregate_id=agg.id,
                bc_name=bc.name,
                bc_short=bc_id_short,
                user_story_context=stories_context[:2000],
            )

            structured_llm = ctx.llm.with_structured_output(CommandList)

            try:
                provider, model = get_llm_provider_model()
                if AI_AUDIT_LOG_ENABLED:
                    SmartLogger.log(
                        "INFO",
                        "Ingestion: extract commands - LLM invoke starting.",
                        category="ingestion.llm.extract_commands.start",
                        params={
                            "session_id": ctx.session.id,
                            "llm": {"provider": provider, "model": model},
                            "bc": {"id": bc.id, "name": bc.name},
                            "aggregate": {"id": agg.id, "name": agg.name},
                            "prompt": prompt if AI_AUDIT_LOG_FULL_PROMPT else summarize_for_log(prompt),
                            "system_prompt": SYSTEM_PROMPT,
                        }
                    )

                t_llm0 = time.perf_counter()
                cmd_response = structured_llm.invoke([SystemMessage(content=SYSTEM_PROMPT), HumanMessage(content=prompt)])
                llm_ms = int((time.perf_counter() - t_llm0) * 1000)
                commands = cmd_response.commands

                if AI_AUDIT_LOG_ENABLED:
                    try:
                        resp_dump = cmd_response.model_dump() if hasattr(cmd_response, "model_dump") else cmd_response.dict()
                    except Exception:
                        resp_dump = {"__type__": type(cmd_response).__name__, "__repr__": repr(cmd_response)[:1000]}
                    SmartLogger.log(
                        "INFO",
                        "Ingestion: extract commands - LLM invoke completed.",
                        category="ingestion.llm.extract_commands.done",
                        params={
                            "session_id": ctx.session.id,
                            "llm": {"provider": provider, "model": model},
                            "bc": {"id": bc.id, "name": bc.name},
                            "aggregate": {"id": agg.id, "name": agg.name},
                            "llm_ms": llm_ms,
                            "result": {
                                "command_ids": summarize_for_log([getattr(c, "id", None) for c in commands]),
                                "response": resp_dump
                                if AI_AUDIT_LOG_FULL_OUTPUT
                                else summarize_for_log(resp_dump, max_list=5000, max_dict_items=5000),
                            },
                        }
                    )
            except Exception as e:
                SmartLogger.log(
                    "WARNING",
                    "Command extraction failed (LLM)",
                    category="ingestion.workflow.commands",
                    params={"session_id": ctx.session.id, "bc_id": bc.id, "agg_id": agg.id, "error": str(e)},
                )
                commands = []

            all_commands[agg.id] = commands
            if commands:
                SmartLogger.log(
                    "INFO",
                    "Commands extracted",
                    category="ingestion.workflow.commands",
                    params={
                        "session_id": ctx.session.id,
                        "agg_id": agg.id,
                        "commands": summarize_for_log(
                            commands, max_list=5000, max_dict_items=5000
                        ),
                    },
                )

            for cmd in commands:
                category = getattr(cmd, "category", None)
                input_schema = getattr(cmd, "inputSchema", None)
                created_cmd = ctx.client.create_command(
                    name=cmd.name,
                    aggregate_id=agg.id,
                    actor=cmd.actor,
                    category=category,
                    input_schema=input_schema,
                )
                # Overwrite LLM-proposed id with UUID from DB (canonical)
                try:
                    cmd.id = created_cmd.get("id")
                except Exception:
                    pass
                # Preserve natural key (needed by downstream property generation prompts)
                try:
                    cmd.key = created_cmd.get("key")
                except Exception:
                    pass

                # Traceability: UserStory -> Command
                for us_id in getattr(cmd, "user_story_ids", []) or []:
                    try:
                        ctx.client.link_user_story_to_command(us_id, created_cmd.get("id"))
                    except Exception:
                        pass

                yield ProgressEvent(
                    phase=IngestionPhase.EXTRACTING_COMMANDS,
                    message=f"Command 생성: {cmd.name}",
                    progress=65,
                    data={
                        "type": "Command",
                        "object": {"id": created_cmd.get("id"), "name": cmd.name, "type": "Command", "parentId": agg.id},
                    },
                )
                await asyncio.sleep(0.1)

    ctx.commands_by_agg = all_commands


