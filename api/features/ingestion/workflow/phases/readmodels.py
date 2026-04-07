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
    rm_display_name = getattr(rm, "displayName", None) or (rm.get("displayName") if isinstance(rm, dict) else None)
    if not rm_display_name:
        rm_display_name = name
    description = getattr(rm, "description", None)
    actor = getattr(rm, "actor", "user") or "user"
    is_multiple_result = getattr(rm, "isMultipleResult", None)
    user_story_ids = list(getattr(rm, "user_story_ids", []) or [])
    
    # Handle both dict and object formats
    bc_id = bc.get("id") if isinstance(bc, dict) else getattr(bc, "id", None)
    
    try:
        created = await asyncio.wait_for(
            asyncio.to_thread(
                ctx.client.create_readmodel,
                name=name,
                bc_id=bc_id,
                description=description,
                provisioning_type="CQRS",
                actor=actor,
                is_multiple_result=is_multiple_result,
                display_name=rm_display_name,
            ),
            timeout=10.0
        )
        
        # Keep a runtime copy with traceability for later UI phase.
        if bc_id not in ctx.readmodels_by_bc:
            ctx.readmodels_by_bc[bc_id] = []
        ctx.readmodels_by_bc[bc_id].append(
            {
                **created,
                "type": "ReadModel",
                "bcId": bc_id,
                "user_story_ids": user_story_ids,
            }
        )
        
        progress_per_bc = 6 // max(len(ctx.bounded_contexts), 1)
        # trigger event의 sequence를 가져와 ReadModel 배치에 사용
        rm_sequence = None
        trigger_event_names_val = list(getattr(rm, "trigger_event_names", []) or [])
        if trigger_event_names_val:
            try:
                with ctx.client.session() as _s:
                    _r = _s.run(
                        "MATCH (evt:Event {name: $name}) RETURN evt.sequence AS seq LIMIT 1",
                        name=trigger_event_names_val[0],
                    ).single()
                    if _r and _r["seq"] is not None:
                        rm_sequence = int(_r["seq"])
            except Exception:
                pass

        progress_event = ProgressEvent(
            phase=IngestionPhase.EXTRACTING_READMODELS,
            message=f"ReadModel 생성: {name}",
            progress=82 + progress_per_bc * bc_idx,
            data={
                "type": "ReadModel",
                "object": {
                    "id": created.get("id"),
                    "name": created.get("name", name),
                    "displayName": rm_display_name,
                    "type": "ReadModel",
                    "parentId": bc_id,
                    "bcId": bc_id,
                    "actor": actor,
                    "sequence": rm_sequence,
                    "triggerEventNames": trigger_event_names_val,
                    "description": created.get("description", description),
                    "provisioningType": created.get("provisioningType", "CQRS"),
                },
            },
        )
        
        # Create CQRS relationships: ReadModel -> Event (trigger_event_names)
        trigger_event_names = list(getattr(rm, "trigger_event_names", []) or [])
        if trigger_event_names:
            link_tasks = []
            for evt_name in trigger_event_names:
                evt_name = (evt_name or "").strip()
                if not evt_name:
                    continue
                link_tasks.append(
                    asyncio.wait_for(
                        asyncio.to_thread(
                            ctx.client.link_readmodel_to_event,
                            readmodel_id=created.get("id"),
                            event_name=evt_name,
                        ),
                        timeout=5.0,
                    )
                )
            if link_tasks:
                await asyncio.gather(*link_tasks, return_exceptions=True)

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
            params={"session_id": ctx.session.id, "readmodel_name": name, "bc_id": bc_id, "error": str(e)},
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

    # Cross-BC ReadModel dedup: track names already generated in previous BCs
    _existing_readmodel_names: list[str] = []

    for bc_idx, bc in enumerate(ctx.bounded_contexts or []):
        # Handle both dict and object formats
        bc_id = bc.get("id") if isinstance(bc, dict) else getattr(bc, "id", None)
        bc_name = bc.get("name") if isinstance(bc, dict) else getattr(bc, "name", "")
        
        # BC 객체에서 user_story_ids를 안전하게 읽어오기
        bc_us_ids = []
        try:
            if hasattr(bc, "model_dump"):
                bc_dict = bc.model_dump()
                bc_us_ids = bc_dict.get("user_story_ids", [])
            elif hasattr(bc, "dict"):
                bc_dict = bc.dict()
                bc_us_ids = bc_dict.get("user_story_ids", [])
            elif isinstance(bc, dict):
                bc_us_ids = bc.get("user_story_ids", [])
            else:
                bc_us_ids = getattr(bc, "user_story_ids", None) or []
        except Exception:
            bc_us_ids = getattr(bc, "user_story_ids", None) or []
        
        if not isinstance(bc_us_ids, list):
            bc_us_ids = []
        bc_us_ids = [us_id for us_id in bc_us_ids if us_id]  # None이나 빈 문자열 제거
        
        # User stories in this BC (include ui_description to support UI phase later)
        bc_user_stories = []
        for us in ctx.user_stories or []:
            if us.id in bc_us_ids:
                ui_desc = getattr(us, "ui_description", "") or ""
                bc_user_stories.append(
                    f"[{us.id}] As a {us.role}, I want to {us.action}, so that {us.benefit}"
                    + (f" (ui_description: {ui_desc})" if ui_desc.strip() else "")
                )

        user_stories_text = "\n".join(bc_user_stories) if bc_user_stories else "No user stories"

        # Events in this BC (Neo4j BC -[:HAS_EVENT]-> Event 경로)
        bc_id = bc.get("id") if isinstance(bc, dict) else getattr(bc, "id", None)
        bc_name = bc.get("name") if isinstance(bc, dict) else getattr(bc, "name", "")
        events_lines: list[str] = []
        try:
            with ctx.client.session() as _evt_sess:
                _evt_result = _evt_sess.run(
                    """
                    MATCH (bc:BoundedContext {id: $bc_id})-[:HAS_EVENT]->(evt:Event)
                    RETURN evt.name AS name, evt.description AS description
                    ORDER BY evt.sequence
                    """,
                    bc_id=bc_id,
                )
                for _r in _evt_result:
                    evt_name = _r["name"] or ""
                    desc = _r["description"] or ""
                    events_lines.append(f"- {evt_name}" + (f": {desc}" if desc else ""))
        except Exception:
            pass
        events_text = "\n".join(events_lines) if events_lines else "No events"

        # Cross-BC events: 다른 BC의 이벤트 (Neo4j 조회)
        cross_bc_events_lines: list[str] = []
        try:
            with ctx.client.session() as _xbc_sess:
                _xbc_result = _xbc_sess.run(
                    """
                    MATCH (bc:BoundedContext)-[:HAS_EVENT]->(evt:Event)
                    WHERE bc.id <> $bc_id
                    RETURN evt.name AS name, bc.name AS bcName
                    ORDER BY bc.name, evt.sequence
                    """,
                    bc_id=bc_id,
                )
                for _r in _xbc_result:
                    cross_bc_events_lines.append(f"- {_r['name']} (BC: {_r['bcName']})")
        except Exception:
            pass

        if cross_bc_events_lines:
            events_text += "\n\n--- Cross-BC Events (from other Bounded Contexts) ---\n"
            events_text += "\n".join(cross_bc_events_lines)

        display_lang = getattr(ctx, "display_language", "ko") or "ko"
        display_name_tail = (
            "\n\nFor each ReadModel output displayName: a short UI label in Korean (e.g. '주문 목록', '주문 요약')."
            if display_lang == "ko"
            else "\n\nFor each ReadModel output displayName: a short UI label in English (e.g. 'Order List', 'Order Summary')."
        )
        # 전체 프롬프트 텍스트 구성 (청킹 판단용)
        full_prompt_text = EXTRACT_READMODELS_PROMPT.format(
            bc_name=bc_name,
            bc_id=bc_id,
            bc_description=(bc.get("description") if isinstance(bc, dict) else getattr(bc, "description", "")) or "",
            user_stories=user_stories_text,
            events=events_text,
        ) + display_name_tail

        # Cross-BC ReadModel dedup: inject existing names into prompt
        if _existing_readmodel_names:
            from api.features.ingestion.workflow.utils.chunking import format_accumulated_names
            dedup_warning = (
                "\n\n## CROSS-BC READMODEL DEDUPLICATION\n"
                "The following ReadModel names have ALREADY been created in other Bounded Contexts. "
                "Do NOT create ReadModels with these exact names. If this BC needs similar query capability, "
                "use a distinct name that reflects this BC's specific perspective.\n"
                "Already existing: " + format_accumulated_names(_existing_readmodel_names)
            )
            full_prompt_text += dedup_warning

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
                    bc_name=bc_name,
                    bc_id=bc_id,
                    bc_description=bc.get("description") if isinstance(bc, dict) else getattr(bc, "description", "") or "",
                    user_stories=chunk_user_stories,
                    events=chunk_events,
                ) + display_name_tail                # Cross-BC ReadModel dedup for chunks too
                if _existing_readmodel_names:
                    chunk_prompt += (
                        "\n\n## CROSS-BC READMODEL DEDUPLICATION\n"
                        "The following ReadModel names have ALREADY been created in other Bounded Contexts. "
                        "Do NOT create ReadModels with these exact names.\n"
                        "Already existing: " + format_accumulated_names(_existing_readmodel_names)
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
                            "bc": {"id": bc_id, "name": bc_name},
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
                        f"ReadModel extraction LLM timeout for chunk {i+1}/{total_chunks} (BC: {bc_name})",
                        category="ingestion.llm.extract_readmodels.timeout",
                        params={
                            "session_id": ctx.session.id,
                            "bc_id": bc_id,
                            "bc_name": bc_name,
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
                        f"ReadModel extraction LLM error for chunk {i+1}/{total_chunks} (BC: {bc_name})",
                        category="ingestion.llm.extract_readmodels.error",
                        params={
                            "session_id": ctx.session.id,
                            "bc_id": bc_id,
                            "bc_name": bc_name,
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
            prompt = full_prompt_text

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
                            "bc": {"id": bc_id, "name": bc_name},
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
                        f"ReadModel extraction LLM timeout (BC: {bc_name})",
                        category="ingestion.llm.extract_readmodels.timeout",
                        params={
                            "session_id": ctx.session.id,
                            "bc_id": bc_id,
                            "bc_name": bc_name,
                            "elapsed_ms": llm_ms,
                        },
                    )
                    readmodels = []
                except Exception as llm_error:
                    llm_ms = int((time.perf_counter() - t_llm0) * 1000)
                    SmartLogger.log(
                        "ERROR",
                        f"ReadModel extraction LLM error (BC: {bc_name})",
                        category="ingestion.llm.extract_readmodels.error",
                        params={
                            "session_id": ctx.session.id,
                            "bc_id": bc_id,
                            "bc_name": bc_name,
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
                            "bc": {"id": bc_id, "name": bc_name},
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
                    params={"session_id": ctx.session.id, "bc_id": bc_id, "error": str(e)},
                )
                readmodels = []

        all_readmodels[bc_id] = readmodels
        ctx.readmodels_by_bc[bc_id] = []

        # Track readmodel names for cross-BC dedup
        for rm in readmodels:
            rm_name = (getattr(rm, "name", "") or "").strip()
            if rm_name and rm_name not in _existing_readmodel_names:
                _existing_readmodel_names.append(rm_name)

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

    # ── CQRS 미연결 이벤트 보고 ──────────────────────────────────
    # ReadModel phase 완료 후, TRIGGERED_BY 관계가 없는 Event를 집계하여 경고 로그.
    try:
        with ctx.client.session() as _check_sess:
            _orphan_result = _check_sess.run(
                """
                MATCH (e:Event)
                WHERE NOT (()-[:TRIGGERED_BY]->(e))
                  AND NOT e.name ENDS WITH 'Failed'
                OPTIONAL MATCH (bc:BoundedContext)-[:HAS_EVENT]->(e)
                RETURN e.name AS event, bc.name AS bc
                ORDER BY bc, e.name
                """
            )
            orphan_events = [(r["event"], r["bc"]) for r in _orphan_result]
            if orphan_events:
                SmartLogger.log(
                    "WARN",
                    f"{len(orphan_events)} non-failure Events have no ReadModel CQRS projection. "
                    f"These events will not appear in any UI view. "
                    f"Examples: {[f'{e}({bc})' for e, bc in orphan_events[:8]]}",
                    category="ingestion.workflow.readmodels.cqrs_orphan_events",
                    params={
                        "session_id": ctx.session.id,
                        "orphan_count": len(orphan_events),
                        "events": [{"name": e, "bc": bc} for e, bc in orphan_events],
                    },
                )
    except Exception:
        pass

    # Keep the raw LLM candidates too (optional)
    # ctx.readmodels_by_bc already holds the persisted/normalized objects.
    _ = all_readmodels


