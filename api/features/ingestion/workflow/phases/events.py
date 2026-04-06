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


async def _create_event_with_links(
    evt: Any,
    evt_idx: int,
    cmd_id: str,
    ctx: IngestionWorkflowContext,
) -> tuple[dict[str, Any] | None, str]:
    """
    Create a single event with user story links.
    Returns (created_event_dict, error_message)
    """
    if not cmd_id:
        return None, "Command ID not found"
    
    # Handle both dict and object formats
    name = (evt.get("name") if isinstance(evt, dict) else getattr(evt, "name", "") or "").strip()
    if not name:
        return None, "Event name is empty"
    evt_display_name = evt.get("displayName") if isinstance(evt, dict) else getattr(evt, "displayName", None)
    if not evt_display_name:
        evt_display_name = name
    version = evt.get("version", "1.0.0") if isinstance(evt, dict) else (getattr(evt, "version", "1.0.0") or "1.0.0")
    payload = evt.get("payload") if isinstance(evt, dict) else getattr(evt, "payload", None)
    
    try:
        created_evt = await asyncio.wait_for(
            asyncio.to_thread(
                ctx.client.create_event,
                name=name,
                command_id=cmd_id,
                version=version,
                payload=payload,
                display_name=evt_display_name,
            ),
            timeout=10.0
        )
        
        # Overwrite LLM-proposed id with UUID from DB (only if evt is an object, not dict)
        try:
            if not isinstance(evt, dict):
                evt.id = created_evt.get("id")
                evt.key = created_evt.get("key")
        except Exception:
            pass

        # Link user stories (batch processing)
        us_ids = getattr(evt, "user_story_ids", []) or []
        if us_ids:
            link_tasks = []
            for us_id in us_ids:
                link_task = asyncio.wait_for(
                    asyncio.to_thread(
                        ctx.client.link_user_story_to_event,
                        us_id,
                        created_evt.get("id")
                    ),
                    timeout=5.0
                )
                link_tasks.append(link_task)
            
            # Process in batches of 10
            BATCH_SIZE = 10
            for batch_start in range(0, len(link_tasks), BATCH_SIZE):
                batch = link_tasks[batch_start:batch_start + BATCH_SIZE]
                try:
                    await asyncio.gather(*batch, return_exceptions=True)
                except Exception:
                    pass  # Individual failures are ignored

        return {
            "event": created_evt,
            "evt": evt,
            "cmd_id": cmd_id,
        }, None
    except asyncio.TimeoutError:
        return None, "Event creation timeout"
    except Exception as e:
        return None, f"Event creation failed: {e}"


async def extract_events_phase(ctx: IngestionWorkflowContext) -> AsyncGenerator[ProgressEvent, None]:
    """
    Phase 6: extract events per aggregate and persist them.
    """
    yield ProgressEvent(phase=IngestionPhase.EXTRACTING_EVENTS, message="Event 추출 중...", progress=75)

    all_events: dict[str, Any] = {}

    for bc in ctx.bounded_contexts:
        # Legacy field used only for prompt text; keep stable without prefix-based ids.
        bc_id_short = (getattr(bc, "name", "") or "").strip()
        bc_id = bc.get("id") if isinstance(bc, dict) else getattr(bc, "id", None)
        bc_name = bc.get("name") if isinstance(bc, dict) else getattr(bc, "name", "")
        bc_aggregates = ctx.aggregates_by_bc.get(bc_id, [])

        for agg in bc_aggregates:
            agg_id = agg.get("id") if isinstance(agg, dict) else getattr(agg, "id", None)
            agg_name = agg.get("name") if isinstance(agg, dict) else getattr(agg, "name", "")
            commands = ctx.commands_by_agg.get(agg_id, [])
            if not commands:
                continue

            commands_text = "\n".join(
                [
                    f"- {cmd.get('name') if isinstance(cmd, dict) else getattr(cmd, 'name', '')}: {cmd.get('description') if isinstance(cmd, dict) else getattr(cmd, 'description', '')}"
                    for cmd in commands
                ]
            )

            prompt = EXTRACT_EVENTS_PROMPT.format(
                aggregate_name=agg_name,
                bc_name=bc_name,
                bc_short=bc_id_short,
                commands=commands_text,
            )
            display_lang = getattr(ctx, "display_language", "ko") or "ko"
            prompt += (
                "\n\nFor each Event output displayName: a short UI label in Korean (e.g. '주문 접수됨', '결제 완료')."
                if display_lang == "ko"
                else "\n\nFor each Event output displayName: a short UI label in English (e.g. 'Order Placed', 'Payment Completed')."
            )

            if ctx.source_report:
                from api.features.ingestion.workflow.utils.report_context import get_events_context
                prompt += "\n\n" + get_events_context(ctx.source_report)

            structured_llm = ctx.llm.with_structured_output(EventList)

            try:
                evt_response = await asyncio.wait_for(
                    asyncio.to_thread(
                        structured_llm.invoke,
                        [SystemMessage(content=SYSTEM_PROMPT), HumanMessage(content=prompt)]
                    ),
                    timeout=300.0,
                )
                events = evt_response.events
            except asyncio.TimeoutError:
                SmartLogger.log(
                    "ERROR",
                    "Event extraction timed out (300s)",
                    category="ingestion.workflow.events.timeout",
                    params={"session_id": ctx.session.id, "bc_id": bc_id, "agg_id": agg_id},
                )
                events = []
            except Exception as e:
                SmartLogger.log(
                    "ERROR",
                    "Event extraction failed (LLM)",
                    category="ingestion.workflow.events",
                    params={"session_id": ctx.session.id, "bc_id": bc_id, "agg_id": agg_id, "error": str(e)},
                )
                events = []

            all_events[agg_id] = events

            # Process all events in parallel
            if events:
                # Check cancellation before parallel processing
                if getattr(ctx.session, "is_cancelled", False):
                    yield ProgressEvent(
                        phase=IngestionPhase.ERROR,
                        message="❌ 생성이 중단되었습니다",
                        progress=getattr(ctx.session, "progress", 0) or 0,
                        data={"error": "Cancelled by user", "cancelled": True},
                    )
                    return

                # Build command name → id lookup for explicit mapping
                cmd_name_to_id = {}
                for cmd in commands:
                    c_name = (cmd.get("name") if isinstance(cmd, dict) else getattr(cmd, "name", "")).strip()
                    c_id = cmd.get("id") if isinstance(cmd, dict) else getattr(cmd, "id", None)
                    if c_name and c_id:
                        cmd_name_to_id[c_name] = c_id

                tasks = []
                for i, evt in enumerate(events):
                    # Try explicit mapping via emitting_command_name first
                    emitting_cmd_name = (
                        (evt.get("emitting_command_name") if isinstance(evt, dict) else getattr(evt, "emitting_command_name", None)) or ""
                    ).strip()

                    cmd_id = cmd_name_to_id.get(emitting_cmd_name) if emitting_cmd_name else None

                    # Fallback to index-based mapping if explicit mapping fails
                    if not cmd_id:
                        if emitting_cmd_name:
                            evt_name = evt.get("name") if isinstance(evt, dict) else getattr(evt, "name", "")
                            SmartLogger.log(
                                "WARN",
                                f"Event '{evt_name}' references unknown command '{emitting_cmd_name}', falling back to index mapping",
                                category="ingestion.workflow.events.mapping_fallback",
                                params={"session_id": ctx.session.id, "event_name": evt_name, "emitting_command_name": emitting_cmd_name},
                            )
                        if i < len(commands):
                            cmd = commands[i]
                            cmd_id = cmd.get("id") if isinstance(cmd, dict) else getattr(cmd, "id", None)
                        elif commands:
                            cmd = commands[0]
                            cmd_id = cmd.get("id") if isinstance(cmd, dict) else getattr(cmd, "id", None)

                    tasks.append(_create_event_with_links(evt, i, cmd_id, ctx))
                
                results = await asyncio.gather(*tasks, return_exceptions=True)
                
                # Process results and yield progress events
                created_count = 0
                for evt_idx, result in enumerate(results):
                    # Check cancellation during result processing
                    if getattr(ctx.session, "is_cancelled", False):
                        yield ProgressEvent(
                            phase=IngestionPhase.ERROR,
                            message="❌ 생성이 중단되었습니다",
                            progress=getattr(ctx.session, "progress", 0) or 0,
                            data={"error": "Cancelled by user", "cancelled": True},
                        )
                        return
                    
                    if isinstance(result, Exception):
                        SmartLogger.log(
                            "ERROR",
                            f"Event creation exception: {result}",
                            category="ingestion.neo4j.event.create.error",
                            params={"session_id": ctx.session.id, "event_index": evt_idx + 1, "error": str(result)}
                        )
                        continue
                    
                    created_evt_data, error = result
                    if error:
                        SmartLogger.log(
                            "ERROR",
                            f"Event creation failed: {error}",
                            category="ingestion.workflow.events.skip",
                            params={"session_id": ctx.session.id, "event_index": evt_idx + 1, "error": error}
                        )
                        continue
                    
                    if created_evt_data:
                        created_count += 1
                        created_evt = created_evt_data["event"]
                        evt = created_evt_data["evt"]
                        cmd_id = created_evt_data["cmd_id"]

                        # Handle both dict and object formats for event
                        evt_name = evt.get("name") if isinstance(evt, dict) else getattr(evt, "name", "")
                        yield ProgressEvent(
                            phase=IngestionPhase.EXTRACTING_EVENTS,
                            message=f"Event 생성: {evt_name} ({created_count}/{len(events)})",
                            progress=80,
                            data={
                                "type": "Event",
                                "object": {
                                    "id": created_evt.get("id"),
                                    "name": evt_name,
                                    "type": "Event",
                                    "parentId": cmd_id,
                                },
                            },
                        )

    ctx.events_by_agg = all_events


