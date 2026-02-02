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
from api.features.ingestion.event_storming.nodes import EventList
from api.features.ingestion.event_storming.prompts import EXTRACT_EVENTS_PROMPT, SYSTEM_PROMPT
from api.features.ingestion.workflow.ingestion_workflow_context import IngestionWorkflowContext
from api.platform.env import get_llm_provider_model
from api.platform.observability.request_logging import summarize_for_log
from api.platform.observability.smart_logger import SmartLogger


async def extract_events_phase(ctx: IngestionWorkflowContext) -> AsyncGenerator[ProgressEvent, None]:
    """
    Phase 6: extract events per aggregate and persist them.
    """
    yield ProgressEvent(phase=IngestionPhase.EXTRACTING_EVENTS, message="Event 추출 중...", progress=75)

    all_events: dict[str, Any] = {}

    for bc in ctx.bounded_contexts:
        # Legacy field used only for prompt text; keep stable without prefix-based ids.
        bc_id_short = (getattr(bc, "name", "") or "").strip()
        bc_aggregates = ctx.aggregates_by_bc.get(bc.id, [])

        for agg in bc_aggregates:
            commands = ctx.commands_by_agg.get(agg.id, [])
            if not commands:
                continue

            commands_text = "\n".join(
                [
                    f"- {cmd.name}: {cmd.description}" if hasattr(cmd, "description") else f"- {cmd.name}"
                    for cmd in commands
                ]
            )

            prompt = EXTRACT_EVENTS_PROMPT.format(
                aggregate_name=agg.name,
                bc_name=bc.name,
                bc_short=bc_id_short,
                commands=commands_text,
            )

            structured_llm = ctx.llm.with_structured_output(EventList)

            try:
                provider, model = get_llm_provider_model()
                if AI_AUDIT_LOG_ENABLED:
                    SmartLogger.log(
                        "INFO",
                        "Ingestion: extract events - LLM invoke starting.",
                        category="ingestion.llm.extract_events.start",
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
                evt_response = structured_llm.invoke([SystemMessage(content=SYSTEM_PROMPT), HumanMessage(content=prompt)])
                llm_ms = int((time.perf_counter() - t_llm0) * 1000)
                events = evt_response.events

                if AI_AUDIT_LOG_ENABLED:
                    try:
                        resp_dump = evt_response.model_dump() if hasattr(evt_response, "model_dump") else evt_response.dict()
                    except Exception:
                        resp_dump = {"__type__": type(evt_response).__name__, "__repr__": repr(evt_response)[:1000]}
                    SmartLogger.log(
                        "INFO",
                        "Ingestion: extract events - LLM invoke completed.",
                        category="ingestion.llm.extract_events.done",
                        params={
                            "session_id": ctx.session.id,
                            "llm": {"provider": provider, "model": model},
                            "bc": {"id": bc.id, "name": bc.name},
                            "aggregate": {"id": agg.id, "name": agg.name},
                            "llm_ms": llm_ms,
                            "result": {
                                "event_ids": summarize_for_log([getattr(e, "id", None) for e in events]),
                                "response": resp_dump
                                if AI_AUDIT_LOG_FULL_OUTPUT
                                else summarize_for_log(resp_dump, max_list=5000, max_dict_items=5000),
                            },
                        }
                    )
            except Exception as e:
                SmartLogger.log(
                    "WARNING",
                    "Event extraction failed (LLM)",
                    category="ingestion.workflow.events",
                    params={"session_id": ctx.session.id, "bc_id": bc.id, "agg_id": agg.id, "error": str(e)},
                )
                events = []

            all_events[agg.id] = events
            if events:
                SmartLogger.log(
                    "INFO",
                    "Events extracted",
                    category="ingestion.workflow.events",
                    params={
                        "session_id": ctx.session.id,
                        "agg_id": agg.id,
                        "events": summarize_for_log(events, max_list=5000, max_dict_items=5000),
                    },
                )

            for i, evt in enumerate(events):
                cmd_id = commands[i].id if i < len(commands) else commands[0].id if commands else None
                if not cmd_id:
                    continue

                version = getattr(evt, "version", "1.0.0") or "1.0.0"
                payload = getattr(evt, "payload", None)
                created_evt = ctx.client.create_event(
                    name=evt.name,
                    command_id=cmd_id,
                    version=version,
                    payload=payload,
                )
                # Overwrite LLM-proposed id with UUID from DB (canonical)
                try:
                    evt.id = created_evt.get("id")
                except Exception:
                    pass
                # Preserve natural key (needed by downstream property generation prompts)
                try:
                    evt.key = created_evt.get("key")
                except Exception:
                    pass

                # Traceability: UserStory -> Event
                for us_id in getattr(evt, "user_story_ids", []) or []:
                    try:
                        ctx.client.link_user_story_to_event(us_id, created_evt.get("id"))
                    except Exception:
                        pass
                yield ProgressEvent(
                    phase=IngestionPhase.EXTRACTING_EVENTS,
                    message=f"Event 생성: {evt.name}",
                    progress=80,
                    data={
                        "type": "Event",
                        "object": {
                            "id": created_evt.get("id"),
                            "name": evt.name,
                            "type": "Event",
                            "parentId": cmd_id,
                        },
                    },
                )
                await asyncio.sleep(0.1)

    ctx.events_by_agg = all_events


