from __future__ import annotations

import asyncio
import time
from typing import AsyncGenerator

from langchain_core.messages import HumanMessage, SystemMessage

from api.platform.env import (
    AI_AUDIT_LOG_ENABLED,
    AI_AUDIT_LOG_FULL_OUTPUT,
    AI_AUDIT_LOG_FULL_PROMPT,
)
from api.features.ingestion.ingestion_contracts import IngestionPhase, ProgressEvent
from api.features.ingestion.event_storming.nodes import BoundedContextList
from api.features.ingestion.event_storming.prompts import IDENTIFY_BC_FROM_STORIES_PROMPT, SYSTEM_PROMPT
from api.features.ingestion.workflow.ingestion_workflow_context import IngestionWorkflowContext
from api.platform.env import get_llm_provider_model
from api.platform.observability.request_logging import sha256_text, summarize_for_log
from api.platform.observability.smart_logger import SmartLogger


async def identify_bounded_contexts_phase(ctx: IngestionWorkflowContext) -> AsyncGenerator[ProgressEvent, None]:
    """
    Phase 3: identify bounded contexts using LLM, create them in Neo4j, and link user stories.
    """
    yield ProgressEvent(phase=IngestionPhase.IDENTIFYING_BC, message="Bounded Context 식별 중...", progress=25)

    stories_text = "\n".join(
        [f"[{us.id}] As a {us.role}, I want to {us.action}, so that {us.benefit}" for us in ctx.user_stories]
    )

    structured_llm = ctx.llm.with_structured_output(BoundedContextList)
    prompt = IDENTIFY_BC_FROM_STORIES_PROMPT.format(user_stories=stories_text)

    provider, model = get_llm_provider_model()
    if AI_AUDIT_LOG_ENABLED:
        SmartLogger.log(
            "INFO",
            "Ingestion: identify BCs - LLM invoke starting.",
            category="ingestion.llm.identify_bc.start",
            params={
                "session_id": ctx.session.id,
                "llm": {"provider": provider, "model": model},
                "user_stories_count": len(ctx.user_stories),
                "prompt_len": len(prompt),
                "prompt_sha256": sha256_text(prompt),
                "prompt": prompt if AI_AUDIT_LOG_FULL_PROMPT else summarize_for_log(prompt),
                "system_sha256": sha256_text(SYSTEM_PROMPT),
            }
        )

    t_llm0 = time.perf_counter()
    bc_response = structured_llm.invoke([SystemMessage(content=SYSTEM_PROMPT), HumanMessage(content=prompt)])
    llm_ms = int((time.perf_counter() - t_llm0) * 1000)

    if AI_AUDIT_LOG_ENABLED:
        try:
            resp_dump = bc_response.model_dump() if hasattr(bc_response, "model_dump") else bc_response.dict()
        except Exception:
            resp_dump = {"__type__": type(bc_response).__name__, "__repr__": repr(bc_response)[:1000]}
        bcs = getattr(bc_response, "bounded_contexts", []) or []
        SmartLogger.log(
            "INFO",
            "Ingestion: identify BCs - LLM invoke completed.",
            category="ingestion.llm.identify_bc.done",
            params={
                "session_id": ctx.session.id,
                "llm": {"provider": provider, "model": model},
                "llm_ms": llm_ms,
                "result": {
                    "bounded_contexts_count": len(bcs),
                    "bounded_context_ids": summarize_for_log([getattr(bc, "id", None) for bc in bcs]),
                    "response": resp_dump if AI_AUDIT_LOG_FULL_OUTPUT else summarize_for_log(resp_dump),
                },
            }
        )

    bc_candidates = bc_response.bounded_contexts
    ctx.bounded_contexts = bc_candidates

    SmartLogger.log(
        "INFO",
        "Bounded contexts identified",
        category="ingestion.workflow.bc",
        params={"session_id": ctx.session.id, "count": len(bc_candidates), "ids": [bc.id for bc in bc_candidates][:10]},
    )

    for bc_idx, bc in enumerate(bc_candidates):
        ctx.client.create_bounded_context(id=bc.id, name=bc.name, description=bc.description)

        yield ProgressEvent(
            phase=IngestionPhase.IDENTIFYING_BC,
            message=f"Bounded Context 생성: {bc.name}",
            progress=30 + (10 * bc_idx // max(len(bc_candidates), 1)),
            data={
                "type": "BoundedContext",
                "object": {
                    "id": bc.id,
                    "name": bc.name,
                    "type": "BoundedContext",
                    "description": bc.description,
                    "userStoryIds": bc.user_story_ids,
                },
            },
        )
        await asyncio.sleep(0.2)

        for us_id in bc.user_story_ids:
            try:
                ctx.client.link_user_story_to_bc(us_id, bc.id)
                yield ProgressEvent(
                    phase=IngestionPhase.IDENTIFYING_BC,
                    message=f"User Story {us_id} → {bc.name}",
                    progress=30 + (10 * bc_idx // max(len(bc_candidates), 1)),
                    data={
                        "type": "UserStoryAssigned",
                        "object": {"id": us_id, "type": "UserStory", "targetBcId": bc.id, "targetBcName": bc.name},
                    },
                )
                await asyncio.sleep(0.1)
            except Exception as e:
                SmartLogger.log(
                    "WARNING",
                    "User story to BC link skipped",
                    category="ingestion.neo4j.us_to_bc",
                    params={"session_id": ctx.session.id, "user_story_id": us_id, "bc_id": bc.id, "error": str(e)},
                )


