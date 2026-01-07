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
from api.features.ingestion.event_storming.nodes import AggregateList
from api.features.ingestion.event_storming.prompts import EXTRACT_AGGREGATES_PROMPT, SYSTEM_PROMPT
from api.features.ingestion.workflow.ingestion_workflow_context import IngestionWorkflowContext
from api.platform.env import get_llm_provider_model
from api.platform.observability.request_logging import summarize_for_log
from api.platform.observability.smart_logger import SmartLogger


async def extract_aggregates_phase(ctx: IngestionWorkflowContext) -> AsyncGenerator[ProgressEvent, None]:
    """
    Phase 4: extract aggregates per BC and persist them.
    """
    yield ProgressEvent(phase=IngestionPhase.EXTRACTING_AGGREGATES, message="Aggregate 추출 중...", progress=45)

    all_aggregates: dict[str, Any] = {}
    progress_per_bc = 10 // max(len(ctx.bounded_contexts), 1)

    for bc_idx, bc in enumerate(ctx.bounded_contexts):
        # Legacy field used only for prompt text; keep stable without prefix-based ids.
        bc_id_short = (getattr(bc, "name", "") or "").strip()
        breakdowns_text = f"User Stories: {', '.join(bc.user_story_ids)}"

        prompt = EXTRACT_AGGREGATES_PROMPT.format(
            bc_name=bc.name,
            bc_id=bc.id,
            bc_id_short=bc_id_short,
            bc_description=bc.description,
            breakdowns=breakdowns_text,
        )

        structured_llm = ctx.llm.with_structured_output(AggregateList)

        provider, model = get_llm_provider_model()
        if AI_AUDIT_LOG_ENABLED:
            SmartLogger.log(
                "INFO",
                "Ingestion: extract aggregates - LLM invoke starting.",
                category="ingestion.llm.extract_aggregates.start",
                params={
                    "session_id": ctx.session.id,
                    "llm": {"provider": provider, "model": model},
                    "bc": {"id": bc.id, "name": bc.name},
                    "prompt": prompt if AI_AUDIT_LOG_FULL_PROMPT else summarize_for_log(prompt),
                    "system_prompt": SYSTEM_PROMPT,
                }
            )

        t_llm0 = time.perf_counter()
        agg_response = structured_llm.invoke([SystemMessage(content=SYSTEM_PROMPT), HumanMessage(content=prompt)])
        llm_ms = int((time.perf_counter() - t_llm0) * 1000)

        if AI_AUDIT_LOG_ENABLED:
            try:
                resp_dump = agg_response.model_dump() if hasattr(agg_response, "model_dump") else agg_response.dict()
            except Exception:
                resp_dump = {"__type__": type(agg_response).__name__, "__repr__": repr(agg_response)[:1000]}
            aggs = getattr(agg_response, "aggregates", []) or []
            SmartLogger.log(
                "INFO",
                "Ingestion: extract aggregates - LLM invoke completed.",
                category="ingestion.llm.extract_aggregates.done",
                params={
                    "session_id": ctx.session.id,
                    "llm": {"provider": provider, "model": model},
                    "bc": {"id": bc.id, "name": bc.name},
                    "llm_ms": llm_ms,
                    "result": {
                        "aggregate_ids": summarize_for_log([getattr(a, "id", None) for a in aggs]),
                        "response": resp_dump if AI_AUDIT_LOG_FULL_OUTPUT else summarize_for_log(resp_dump, max_list=5000, max_dict_items=5000),
                    },
                }
            )

        aggregates = agg_response.aggregates
        all_aggregates[bc.id] = aggregates

        SmartLogger.log(
            "INFO",
            "Aggregates extracted",
            category="ingestion.workflow.aggregates",
            params={
                "session_id": ctx.session.id,
                "bc_id": bc.id,
                "bc_name": bc.name,
                "aggregates": summarize_for_log(aggregates, max_list=5000, max_dict_items=5000),
            },
        )

        for agg in aggregates:
            created_agg = ctx.client.create_aggregate(
                name=agg.name,
                bc_id=bc.id,
                root_entity=agg.root_entity,
                invariants=agg.invariants,
            )
            # Overwrite LLM-proposed id with UUID from DB (canonical)
            try:
                agg.id = created_agg.get("id")
            except Exception:
                pass
            # Preserve natural key (needed by downstream property generation prompts)
            try:
                agg.key = created_agg.get("key")
            except Exception:
                pass

            # Traceability: UserStory -> Aggregate
            for us_id in getattr(agg, "user_story_ids", []) or []:
                try:
                    ctx.client.link_user_story_to_aggregate(us_id, created_agg.get("id"))
                except Exception:
                    pass

            yield ProgressEvent(
                phase=IngestionPhase.EXTRACTING_AGGREGATES,
                message=f"Aggregate 생성: {agg.name}",
                progress=45 + progress_per_bc * bc_idx,
                data={
                    "type": "Aggregate",
                    "object": {"id": created_agg.get("id"), "name": agg.name, "type": "Aggregate", "parentId": bc.id},
                },
            )
            await asyncio.sleep(0.15)

    ctx.aggregates_by_bc = all_aggregates


