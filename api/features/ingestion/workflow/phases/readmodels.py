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
from api.features.ingestion.event_storming.structured_outputs import ReadModelList
from api.features.ingestion.event_storming.prompts import EXTRACT_READMODELS_PROMPT, SYSTEM_PROMPT
from api.features.ingestion.workflow.ingestion_workflow_context import IngestionWorkflowContext
from api.platform.env import get_llm_provider_model
from api.platform.observability.request_logging import summarize_for_log
from api.platform.observability.smart_logger import SmartLogger

async def extract_readmodels_phase(ctx: IngestionWorkflowContext) -> AsyncGenerator[ProgressEvent, None]:
    """
    Phase: extract ReadModels per BC and persist them.

    - ReadModel names follow Noun+Purpose (PascalCase), e.g., OrderSummary
    - provisioningType is fixed to CQRS (initial version)
    """
    yield ProgressEvent(
        phase=IngestionPhase.EXTRACTING_READMODELS,
        message="ReadModel 추출 중...",
        progress=82,
    )

    all_readmodels: dict[str, Any] = {}
    progress_per_bc = 6 // max(len(ctx.bounded_contexts), 1)

    for bc_idx, bc in enumerate(ctx.bounded_contexts or []):
        # User stories in this BC (include ui_description to support UI phase later)
        bc_user_stories = []
        for us in ctx.user_stories or []:
            if us.id in getattr(bc, "user_story_ids", []) or []:
                ui_desc = getattr(us, "ui_description", "") or ""
                bc_user_stories.append(
                    f"[{us.id}] As a {us.role}, I want to {us.action}, so that {us.benefit}"
                    + (f" (ui_description: {ui_desc})" if ui_desc.strip() else "")
                )

        user_stories_text = "\n".join(bc_user_stories) if bc_user_stories else "No user stories"

        # Events in this BC (flatten events for all aggregates in this BC)
        events_lines: list[str] = []
        for agg in ctx.aggregates_by_bc.get(bc.id, []) or []:
            for evt in ctx.events_by_agg.get(agg.id, []) or []:
                desc = getattr(evt, "description", "") or ""
                events_lines.append(f"- {evt.name}" + (f": {desc}" if desc else ""))
        events_text = "\n".join(events_lines) if events_lines else "No events"

        prompt = EXTRACT_READMODELS_PROMPT.format(
            bc_name=bc.name,
            bc_id=bc.id,
            bc_description=getattr(bc, "description", "") or "",
            user_stories=user_stories_text[:6000],
            events=events_text[:6000],
        )

        structured_llm = ctx.llm.with_structured_output(ReadModelList)

        try:
            provider, model = get_llm_provider_model()
            if AI_AUDIT_LOG_ENABLED:
                SmartLogger.log(
                    "INFO",
                    "Ingestion: extract readmodels - LLM invoke starting.",
                    category="ingestion.llm.extract_readmodels.start",
                    params={
                        "session_id": ctx.session.id,
                        "llm": {"provider": provider, "model": model},
                        "bc": {"id": bc.id, "name": bc.name},
                        "prompt": prompt if AI_AUDIT_LOG_FULL_PROMPT else summarize_for_log(prompt),
                        "system_prompt": SYSTEM_PROMPT,
                    },
                )

            t_llm0 = time.perf_counter()
            rm_response = structured_llm.invoke([SystemMessage(content=SYSTEM_PROMPT), HumanMessage(content=prompt)])
            llm_ms = int((time.perf_counter() - t_llm0) * 1000)
            readmodels = getattr(rm_response, "readmodels", []) or []

            if AI_AUDIT_LOG_ENABLED:
                try:
                    resp_dump = rm_response.model_dump() if hasattr(rm_response, "model_dump") else rm_response.dict()
                except Exception:
                    resp_dump = {"__type__": type(rm_response).__name__, "__repr__": repr(rm_response)[:1000]}
                SmartLogger.log(
                    "INFO",
                    "Ingestion: extract readmodels - LLM invoke completed.",
                    category="ingestion.llm.extract_readmodels.done",
                    params={
                        "session_id": ctx.session.id,
                        "llm": {"provider": provider, "model": model},
                        "bc": {"id": bc.id, "name": bc.name},
                        "llm_ms": llm_ms,
                        "result": {
                            "readmodel_names": summarize_for_log([getattr(rm, "name", None) for rm in readmodels]),
                            "response": resp_dump
                            if AI_AUDIT_LOG_FULL_OUTPUT
                            else summarize_for_log(resp_dump, max_list=5000, max_dict_items=5000),
                        },
                    },
                )
        except Exception as e:
            SmartLogger.log(
                "WARNING",
                "ReadModel extraction failed (LLM)",
                category="ingestion.workflow.readmodels",
                params={"session_id": ctx.session.id, "bc_id": bc.id, "error": str(e)},
            )
            readmodels = []

        all_readmodels[bc.id] = readmodels
        ctx.readmodels_by_bc[bc.id] = []

        if readmodels:
            SmartLogger.log(
                "INFO",
                "ReadModels extracted",
                category="ingestion.workflow.readmodels",
                params={
                    "session_id": ctx.session.id,
                    "bc_id": bc.id,
                    "bc_name": bc.name,
                    "readmodels": summarize_for_log(readmodels, max_list=5000, max_dict_items=5000),
                },
            )

        for rm in readmodels:
            name = (getattr(rm, "name", "") or "").strip()
            if not name:
                continue

            description = getattr(rm, "description", None)
            user_story_ids = list(getattr(rm, "user_story_ids", []) or [])

            try:
                created = ctx.client.create_readmodel(
                    name=name,
                    bc_id=bc.id,
                    description=description,
                    provisioning_type="CQRS",
                )
            except Exception as e:
                SmartLogger.log(
                    "WARNING",
                    "ReadModel create skipped",
                    category="ingestion.neo4j.readmodel",
                    params={"session_id": ctx.session.id, "readmodel_name": name, "bc_id": bc.id, "error": str(e)},
                )
                continue

            # Keep a runtime copy with traceability for later UI phase.
            ctx.readmodels_by_bc[bc.id].append(
                {
                    **created,
                    "type": "ReadModel",
                    "bcId": bc.id,
                    "user_story_ids": user_story_ids,
                }
            )

            yield ProgressEvent(
                phase=IngestionPhase.EXTRACTING_READMODELS,
                message=f"ReadModel 생성: {name}",
                progress=82 + progress_per_bc * bc_idx,
                data={
                    "type": "ReadModel",
                    "object": {
                        "id": created.get("id"),
                        "name": created.get("name", name),
                        "type": "ReadModel",
                        "parentId": bc.id,
                        "description": created.get("description", description),
                        "provisioningType": created.get("provisioningType", "CQRS"),
                        "userStoryIds": user_story_ids,
                    },
                },
            )
            await asyncio.sleep(0.1)

    # Keep the raw LLM candidates too (optional)
    # ctx.readmodels_by_bc already holds the persisted/normalized objects.
    _ = all_readmodels


