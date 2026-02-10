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
from api.features.ingestion.workflow.utils.chunking import (
    should_chunk,
    split_text_with_overlap,
    merge_chunk_results,
    calculate_chunk_progress,
)
from api.platform.env import get_llm_provider_model
from api.platform.observability.request_logging import summarize_for_log
from api.platform.observability.smart_logger import SmartLogger


async def _create_readmodel_with_links(
    rm: Any,
    rm_idx: int,
    total_rms: int,
    bc: Any,
    bc_idx: int,
    ctx: IngestionWorkflowContext,
) -> tuple[dict[str, Any] | None, ProgressEvent | None, str]:
    """
    Create a single readmodel with user story links.
    Returns (created_readmodel_dict, progress_event, error_message)
    """
    name = (getattr(rm, "name", "") or "").strip()
    if not name:
        return None, None, "ReadModel name is empty"
    
    description = getattr(rm, "description", None)
    actor = getattr(rm, "actor", "user") or "user"
    is_multiple_result = getattr(rm, "isMultipleResult", None)
    user_story_ids = list(getattr(rm, "user_story_ids", []) or [])
    
    try:
        created = await asyncio.wait_for(
            asyncio.to_thread(
                ctx.client.create_readmodel,
                name=name,
                bc_id=bc.id,
                description=description,
                provisioning_type="CQRS",
                actor=actor,
                is_multiple_result=is_multiple_result,
            ),
            timeout=10.0
        )
        
        # Keep a runtime copy with traceability for later UI phase.
        ctx.readmodels_by_bc[bc.id].append(
            {
                **created,
                "type": "ReadModel",
                "bcId": bc.id,
                "user_story_ids": user_story_ids,
            }
        )
        
        progress_per_bc = 6 // max(len(ctx.bounded_contexts), 1)
        progress_event = ProgressEvent(
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
        
        return {
            "readmodel": created,
            "rm": rm,
            "bc": bc,
        }, progress_event, None
    except asyncio.TimeoutError:
        return None, None, "ReadModel creation timeout"
    except Exception as e:
        SmartLogger.log(
            "WARNING",
            "ReadModel create skipped",
            category="ingestion.neo4j.readmodel",
            params={"session_id": ctx.session.id, "readmodel_name": name, "bc_id": bc.id, "error": str(e)},
        )
        return None, None, f"ReadModel creation failed: {e}"


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

        # 전체 프롬프트 텍스트 구성 (청킹 판단용)
        full_prompt_text = EXTRACT_READMODELS_PROMPT.format(
            bc_name=bc.name,
            bc_id=bc.id,
            bc_description=getattr(bc, "description", "") or "",
            user_stories=user_stories_text,
            events=events_text,
        )
        
        # 청킹 필요 여부 판단
        if should_chunk(full_prompt_text):
            # user_stories_text와 events_text를 각각 청킹
            # 더 큰 텍스트를 기준으로 청킹하되, 두 필드를 모두 포함
            user_stories_chunks = split_text_with_overlap(user_stories_text) if should_chunk(user_stories_text) else [(user_stories_text, 0, len(user_stories_text))]
            events_chunks = split_text_with_overlap(events_text) if should_chunk(events_text) else [(events_text, 0, len(events_text))]
            
            # 더 많은 청크 수를 기준으로 처리
            total_chunks = max(len(user_stories_chunks), len(events_chunks))
            
            chunk_results = []
            
            for i in range(total_chunks):
                # Check cancellation before processing chunk
                if getattr(ctx.session, "is_cancelled", False):
                    yield ProgressEvent(
                        phase=IngestionPhase.ERROR,
                        message="❌ 생성이 중단되었습니다",
                        progress=getattr(ctx.session, "progress", 0) or 0,
                        data={"error": "Cancelled by user", "cancelled": True},
                    )
                    return
                
                # 각 청크에서 해당 인덱스의 텍스트 가져오기
                chunk_user_stories, _, _ = user_stories_chunks[i] if i < len(user_stories_chunks) else (user_stories_chunks[-1][0], 0, 0)
                chunk_events, _, _ = events_chunks[i] if i < len(events_chunks) else (events_chunks[-1][0], 0, 0)
                
                chunk_prompt = EXTRACT_READMODELS_PROMPT.format(
                    bc_name=bc.name,
                    bc_id=bc.id,
                    bc_description=getattr(bc, "description", "") or "",
                    user_stories=chunk_user_stories,
                    events=chunk_events,
                )
                
                structured_llm = ctx.llm.with_structured_output(ReadModelList)
                
                provider, model = get_llm_provider_model()
                if AI_AUDIT_LOG_ENABLED:
                    SmartLogger.log(
                        "INFO",
                        f"Ingestion: extract readmodels (chunk {i+1}/{total_chunks}) - LLM invoke starting.",
                        category="ingestion.llm.extract_readmodels.start",
                        params={
                            "session_id": ctx.session.id,
                            "llm": {"provider": provider, "model": model},
                            "bc": {"id": bc.id, "name": bc.name},
                            "chunk_index": i + 1,
                            "total_chunks": total_chunks,
                        }
                    )
                
                t_llm0 = time.perf_counter()
                try:
                    rm_response = await asyncio.wait_for(
                        asyncio.to_thread(
                            structured_llm.invoke,
                            [SystemMessage(content=SYSTEM_PROMPT), HumanMessage(content=chunk_prompt)]
                        ),
                        timeout=300.0  # 5분 타임아웃
                    )
                    llm_ms = int((time.perf_counter() - t_llm0) * 1000)
                except asyncio.TimeoutError:
                    llm_ms = int((time.perf_counter() - t_llm0) * 1000)
                    SmartLogger.log(
                        "ERROR",
                        f"ReadModel extraction LLM timeout for chunk {i+1}/{total_chunks} (BC: {bc.name})",
                        category="ingestion.llm.extract_readmodels.timeout",
                        params={
                            "session_id": ctx.session.id,
                            "bc_id": bc.id,
                            "bc_name": bc.name,
                            "chunk_index": i + 1,
                            "total_chunks": total_chunks,
                            "elapsed_ms": llm_ms,
                        },
                    )
                    chunk_readmodels = []
                    chunk_results.append(chunk_readmodels)
                    continue
                except Exception as llm_error:
                    llm_ms = int((time.perf_counter() - t_llm0) * 1000)
                    SmartLogger.log(
                        "ERROR",
                        f"ReadModel extraction LLM error for chunk {i+1}/{total_chunks} (BC: {bc.name})",
                        category="ingestion.llm.extract_readmodels.error",
                        params={
                            "session_id": ctx.session.id,
                            "bc_id": bc.id,
                            "bc_name": bc.name,
                            "chunk_index": i + 1,
                            "total_chunks": total_chunks,
                            "error": str(llm_error),
                            "error_type": type(llm_error).__name__,
                            "elapsed_ms": llm_ms,
                        },
                    )
                    chunk_readmodels = []
                    chunk_results.append(chunk_readmodels)
                    continue
                
                # Check cancellation after chunk processing
                if getattr(ctx.session, "is_cancelled", False):
                    yield ProgressEvent(
                        phase=IngestionPhase.ERROR,
                        message="❌ 생성이 중단되었습니다",
                        progress=getattr(ctx.session, "progress", 0) or 0,
                        data={"error": "Cancelled by user", "cancelled": True},
                    )
                    return
                
                chunk_readmodels = getattr(rm_response, "readmodels", []) or []
                chunk_results.append(chunk_readmodels)
            
            # 결과 병합 (중복 제거: name 우선)
            readmodels = merge_chunk_results(
                chunk_results,
                dedupe_key=lambda rm: getattr(rm, "name", None) or getattr(rm, "id", None) or f"__fallback_{id(rm)}"
            )
        else:
            # 청킹 불필요한 경우
            prompt = EXTRACT_READMODELS_PROMPT.format(
                bc_name=bc.name,
                bc_id=bc.id,
                bc_description=getattr(bc, "description", "") or "",
                user_stories=user_stories_text,
                events=events_text,
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
                try:
                    rm_response = await asyncio.wait_for(
                        asyncio.to_thread(
                            structured_llm.invoke,
                            [SystemMessage(content=SYSTEM_PROMPT), HumanMessage(content=prompt)]
                        ),
                        timeout=300.0  # 5분 타임아웃
                    )
                    llm_ms = int((time.perf_counter() - t_llm0) * 1000)
                    readmodels = getattr(rm_response, "readmodels", []) or []
                except asyncio.TimeoutError:
                    llm_ms = int((time.perf_counter() - t_llm0) * 1000)
                    SmartLogger.log(
                        "ERROR",
                        f"ReadModel extraction LLM timeout (BC: {bc.name})",
                        category="ingestion.llm.extract_readmodels.timeout",
                        params={
                            "session_id": ctx.session.id,
                            "bc_id": bc.id,
                            "bc_name": bc.name,
                            "elapsed_ms": llm_ms,
                        },
                    )
                    readmodels = []
                except Exception as llm_error:
                    llm_ms = int((time.perf_counter() - t_llm0) * 1000)
                    SmartLogger.log(
                        "ERROR",
                        f"ReadModel extraction LLM error (BC: {bc.name})",
                        category="ingestion.llm.extract_readmodels.error",
                        params={
                            "session_id": ctx.session.id,
                            "bc_id": bc.id,
                            "bc_name": bc.name,
                            "error": str(llm_error),
                            "error_type": type(llm_error).__name__,
                            "elapsed_ms": llm_ms,
                        },
                    )
                    readmodels = []

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
                    "ERROR",
                    "ReadModel extraction failed (LLM)",
                    category="ingestion.workflow.readmodels",
                    params={"session_id": ctx.session.id, "bc_id": bc.id, "error": str(e)},
                )
                readmodels = []

        all_readmodels[bc.id] = readmodels
        ctx.readmodels_by_bc[bc.id] = []

        # Process all readmodels in parallel
        if readmodels:
            # Check cancellation before parallel processing
            if getattr(ctx.session, "is_cancelled", False):
                yield ProgressEvent(
                    phase=IngestionPhase.ERROR,
                    message="❌ 생성이 중단되었습니다",
                    progress=getattr(ctx.session, "progress", 0) or 0,
                    data={"error": "Cancelled by user", "cancelled": True},
                )
                return
            
            total_rms = len(readmodels)
            tasks = []
            for rm_idx, rm in enumerate(readmodels):
                tasks.append(_create_readmodel_with_links(rm, rm_idx, total_rms, bc, bc_idx, ctx))
            
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Process results and yield progress events
            for rm_idx, result in enumerate(results):
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
                        f"ReadModel creation exception: {result}",
                        category="ingestion.neo4j.readmodel.create.error",
                        params={"session_id": ctx.session.id, "readmodel_index": rm_idx + 1, "error": str(result)}
                    )
                    continue
                
                created_rm_data, progress_event, error = result
                if error:
                    SmartLogger.log(
                        "ERROR",
                        f"ReadModel creation failed: {error}",
                        category="ingestion.workflow.readmodels.skip",
                        params={"session_id": ctx.session.id, "readmodel_index": rm_idx + 1, "error": error}
                    )
                    continue
                
                if created_rm_data and progress_event:
                    yield progress_event

    # Keep the raw LLM candidates too (optional)
    # ctx.readmodels_by_bc already holds the persisted/normalized objects.
    _ = all_readmodels


