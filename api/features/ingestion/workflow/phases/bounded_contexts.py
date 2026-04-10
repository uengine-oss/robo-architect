from __future__ import annotations

import asyncio
import json
import re
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
from api.features.ingestion.workflow.utils.chunking import (
    should_chunk_list,
    split_list_with_overlap,
    merge_chunk_results,
    calculate_chunk_progress,
)
from api.features.ingestion.workflow.utils.user_story_format import format_us_text
from api.platform.env import get_llm_provider_model
from api.platform.observability.request_logging import summarize_for_log
from api.platform.observability.smart_logger import SmartLogger


_EVENT_CLUSTER_BUDGET_TOKENS = 5000  # Max token budget for event clustering hint


def _build_event_cluster_hint(ctx: Any) -> str:
    """Build event clustering hint from Phase 4 results.

    Groups events by US and extracts common domain keywords from event names
    to suggest natural BC boundaries.  For example, events like
    AutoPaymentBlocked, AutoPaymentAccountRegistered, AutoPaymentChannelInfoSet
    all share the "AutoPayment" prefix → suggest a single "AutoPayment" BC.
    """
    events = getattr(ctx, "events_from_us", None) or []
    if not events:
        return ""

    # Group events by US, then extract domain keyword from event name prefix
    # e.g., "AutoPaymentBlocked" → "AutoPayment", "OrderPlaced" → "Order"
    import re
    _PASCAL_SPLIT = re.compile(r"(?<=[a-z])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])")

    domain_to_events: dict[str, list[str]] = {}
    for evt in events:
        name = evt.get("name") if isinstance(evt, dict) else getattr(evt, "name", "")
        if not name:
            continue
        # Extract domain prefix: take first 1-2 PascalCase words as domain
        parts = _PASCAL_SPLIT.split(name)
        if len(parts) >= 2:
            # Use first 2 words as domain key (e.g., AutoPayment, OrderPlacement, Account)
            domain = parts[0] + parts[1] if len(parts[0]) <= 4 else parts[0]
        else:
            domain = parts[0] if parts else name
        domain_to_events.setdefault(domain, []).append(name)

    if not domain_to_events:
        return ""

    # Sort by event count (largest clusters first), filter out singletons
    sorted_domains = sorted(
        domain_to_events.items(), key=lambda x: len(x[1]), reverse=True
    )
    significant = [(d, evts) for d, evts in sorted_domains if len(evts) >= 2]

    if not significant:
        return ""

    lines = []
    for domain, evts in significant[:30]:  # Top 30 clusters
        sample = ", ".join(evts[:5])
        if len(evts) > 5:
            sample += f" ... +{len(evts) - 5} more"
        lines.append(f"- **{domain}** ({len(evts)} events): {sample}")

    body = "\n".join(lines)

    # Token budget check
    from api.features.ingestion.workflow.utils.chunking import estimate_tokens
    if estimate_tokens(body) > _EVENT_CLUSTER_BUDGET_TOKENS:
        # Compress: show only domain name + count
        lines = [f"- {d} ({len(e)} events)" for d, e in significant[:30]]
        body = "\n".join(lines)

    return (
        "\n\n## Event Domain Clusters (from previous phase)\n"
        "The following event clusters were detected. Events sharing the same domain prefix "
        "strongly suggest they belong to the SAME Bounded Context:\n\n"
        + body
        + "\n\nUse these clusters as primary signals for BC boundaries. "
        "User Stories whose events fall into the same cluster should be in the same BC.\n"
    )


async def _create_bc_with_links(
    bc: Any,
    bc_idx: int,
    total_bcs: int,
    ctx: IngestionWorkflowContext,
) -> tuple[dict[str, Any] | None, list[ProgressEvent], str]:
    """
    Create a single bounded context with user story links.
    Returns (created_bc_dict, progress_events, error_message)
    """
    # Handle both dict and object formats
    bc_name = bc.get("name") if isinstance(bc, dict) else getattr(bc, "name", "")
    bc_description = bc.get("description") if isinstance(bc, dict) else getattr(bc, "description", "")
    domain_type = bc.get("domain_type") if isinstance(bc, dict) else getattr(bc, "domain_type", None)
    bc_display_name = bc.get("displayName") if isinstance(bc, dict) else getattr(bc, "displayName", None)
    if not bc_display_name:
        bc_display_name = bc_name
    
    # BC 생성 전에 user_story_ids를 먼저 읽어옴
    us_ids = []
    try:
        # 방법 1: Pydantic model_dump 사용 (가장 안전)
        if hasattr(bc, "model_dump"):
            bc_dict = bc.model_dump()
            us_ids = bc_dict.get("user_story_ids", [])
        elif hasattr(bc, "dict"):
            bc_dict = bc.dict()
            us_ids = bc_dict.get("user_story_ids", [])
        # 방법 2: dict 접근
        elif isinstance(bc, dict):
            us_ids = bc.get("user_story_ids", [])
        # 방법 3: 직접 속성 접근 (fallback)
        else:
            us_ids = getattr(bc, "user_story_ids", None)
            if us_ids is None:
                us_ids = []
    except Exception as e:
        SmartLogger.log(
            "WARN",
            f"Failed to get user_story_ids from BC {bc_name} before creation: {e}",
            category="ingestion.workflow.bc.get_user_story_ids_error",
            params={
                "session_id": ctx.session.id,
                "bc_name": bc_name,
                "error": str(e),
            },
        )
    
    # 리스트가 아니거나 비어있으면 빈 리스트로 설정
    if not isinstance(us_ids, list):
        us_ids = []
    us_ids = [us_id for us_id in us_ids if us_id]  # None이나 빈 문자열 제거
    
    try:
        created_bc = await asyncio.wait_for(
            asyncio.to_thread(
                ctx.client.create_bounded_context,
                name=bc_name,
                description=bc_description,
                domain_type=domain_type,
                user_story_ids=us_ids,
                display_name=bc_display_name,
            ),
            timeout=10.0
        )
        
        # Overwrite LLM-proposed id with UUID from DB (canonical) - only if bc is an object, not dict
        try:
            if not isinstance(bc, dict):
                bc.id = created_bc.get("id")
        except Exception:
            pass
        # Preserve natural key (helps downstream property generation prompts)
        try:
            if not isinstance(bc, dict):
                bc.key = created_bc.get("key")
        except Exception:
            pass
        
        PHASE_END = 30
        progress_events = []
        
        # BC 생성 이벤트
        progress_events.append(ProgressEvent(
            phase=IngestionPhase.IDENTIFYING_BC,
            message=f"Bounded Context 생성: {bc_name}",
            progress=PHASE_END - 2 + int((2 * bc_idx / max(total_bcs, 1))),
            data={
                "type": "BoundedContext",
                "object": {
                    "id": created_bc.get("id"),
                    "name": bc_name,
                    "type": "BoundedContext",
                    "description": bc_description,
                    "userStoryIds": us_ids,
                },
            },
        ))
        
        # User Story 링크 처리 (배치 처리)
        linked_count = 0
        failed_count = 0
        skipped_count = 0
        failed_us_ids = []
        skipped_us_ids = []
        
        # us_ids는 이미 위에서 읽어왔음
        # 항상 로그 출력 (us_ids가 비어있어도)
        SmartLogger.log(
            "INFO" if us_ids else "WARN",
            f"BC {bc_name} linking check: {len(us_ids)} User Story IDs found",
            category="ingestion.workflow.bc.linking_check",
            params={
                "session_id": ctx.session.id,
                "bc_id": created_bc.get("id"),
                "bc_name": bc_name,
                "user_story_ids": us_ids,
                "user_story_count": len(us_ids),
                "bc_type": type(bc).__name__,
                "bc_has_user_story_ids_attr": hasattr(bc, "user_story_ids") if not isinstance(bc, dict) else False,
            },
        )
        
        if us_ids:
            SmartLogger.log(
                "INFO",
                f"Linking {len(us_ids)} User Stories to BC {bc_name}",
                category="ingestion.workflow.bc.linking_start",
                params={
                    "session_id": ctx.session.id,
                    "bc_id": created_bc.get("id"),
                    "bc_name": bc_name,
                    "user_story_ids": us_ids,
                },
            )
            
            link_tasks = []
            for us_id in us_ids:
                link_task = asyncio.wait_for(
                    asyncio.to_thread(
                        ctx.client.link_user_story_to_bc,
                        us_id,
                        created_bc.get("id")
                    ),
                    timeout=5.0
                )
                link_tasks.append((us_id, link_task))
            
            # Process in batches of 10
            BATCH_SIZE = 10
            for batch_start in range(0, len(link_tasks), BATCH_SIZE):
                batch = link_tasks[batch_start:batch_start + BATCH_SIZE]
                for us_id, link_task in batch:
                    try:
                        link_result = await link_task
                        # link_user_story_to_bc는 (success, diagnostic) 튜플을 반환할 수 있음
                        if isinstance(link_result, tuple):
                            success, diagnostic = link_result
                            if success:
                                linked_count += 1
                                # 프론트엔드에 User Story 할당 이벤트 전송
                                # User Story 정보 찾기
                                us_obj = next((us for us in ctx.user_stories if us.id == us_id), None)
                                us_data = {
                                    "id": us_id,
                                    "targetBcId": created_bc.get("id"),
                                    "targetBcName": bc_name,
                                }
                                if us_obj:
                                    us_data.update({
                                        "role": getattr(us_obj, "role", ""),
                                        "action": getattr(us_obj, "action", ""),
                                        "benefit": getattr(us_obj, "benefit", ""),
                                        "priority": getattr(us_obj, "priority", ""),
                                        "status": getattr(us_obj, "status", "draft"),
                                    })
                                us_assigned_event = ProgressEvent(
                                    phase=IngestionPhase.IDENTIFYING_BC,
                                    message=f"User Story {us_id} 할당됨: {bc_name}",
                                    progress=PHASE_END - 1,
                                    data={
                                        "type": "UserStoryAssigned",
                                        "object": us_data,
                                    },
                                )
                                progress_events.append(us_assigned_event)
                            else:
                                failed_count += 1
                                failed_us_ids.append(us_id)
                                SmartLogger.log(
                                    "WARN",
                                    f"Failed to link User Story {us_id} to BC {bc_name}",
                                    category="ingestion.workflow.bc.link_failed",
                                    params={
                                        "session_id": ctx.session.id,
                                        "user_story_id": us_id,
                                        "bc_id": created_bc.get("id"),
                                        "bc_name": bc_name,
                                        "diagnostic": diagnostic,
                                    },
                                )
                        else:
                            # Boolean 반환인 경우
                            if link_result:
                                linked_count += 1
                                # 프론트엔드에 User Story 할당 이벤트 전송
                                # User Story 정보 찾기
                                us_obj = next((us for us in ctx.user_stories if us.id == us_id), None)
                                us_data = {
                                    "id": us_id,
                                    "targetBcId": created_bc.get("id"),
                                    "targetBcName": bc_name,
                                }
                                if us_obj:
                                    us_data.update({
                                        "role": getattr(us_obj, "role", ""),
                                        "action": getattr(us_obj, "action", ""),
                                        "benefit": getattr(us_obj, "benefit", ""),
                                        "priority": getattr(us_obj, "priority", ""),
                                        "status": getattr(us_obj, "status", "draft"),
                                    })
                                us_assigned_event = ProgressEvent(
                                    phase=IngestionPhase.IDENTIFYING_BC,
                                    message=f"User Story {us_id} 할당됨: {bc_name}",
                                    progress=PHASE_END - 1,
                                    data={
                                        "type": "UserStoryAssigned",
                                        "object": us_data,
                                    },
                                )
                                progress_events.append(us_assigned_event)
                            else:
                                failed_count += 1
                                failed_us_ids.append(us_id)
                    except asyncio.TimeoutError:
                        failed_count += 1
                        failed_us_ids.append(us_id)
                        SmartLogger.log(
                            "WARN",
                            f"Timeout linking User Story {us_id} to BC {bc_name}",
                            category="ingestion.workflow.bc.link_timeout",
                            params={
                                "session_id": ctx.session.id,
                                "user_story_id": us_id,
                                "bc_id": created_bc.get("id"),
                                "bc_name": bc.name,
                            },
                        )
                    except Exception as e:
                        # User Story가 ctx에 없거나 Neo4j에 없는 경우
                        us_in_ctx = next((us for us in ctx.user_stories if us.id == us_id), None)
                        if not us_in_ctx:
                            skipped_count += 1
                            skipped_us_ids.append(us_id)
                            SmartLogger.log(
                                "WARN",
                                f"Skipping User Story {us_id} - not found in context",
                                category="ingestion.workflow.bc.link_skipped",
                                params={
                                    "session_id": ctx.session.id,
                                    "user_story_id": us_id,
                                    "bc_id": created_bc.get("id"),
                                    "bc_name": bc.name,
                                },
                            )
                        else:
                            failed_count += 1
                            failed_us_ids.append(us_id)
                            SmartLogger.log(
                                "ERROR",
                                f"Exception linking User Story {us_id} to BC {bc_name}: {e}",
                                category="ingestion.workflow.bc.link_exception",
                                params={
                                    "session_id": ctx.session.id,
                                    "user_story_id": us_id,
                                    "bc_id": created_bc.get("id"),
                                    "bc_name": bc.name,
                                    "error": str(e),
                                    "error_type": type(e).__name__,
                                },
                            )
            
            SmartLogger.log(
                "INFO",
                f"BC {bc_name} linking completed: {linked_count} linked, {failed_count} failed, {skipped_count} skipped",
                category="ingestion.workflow.bc.linking_summary",
                params={
                    "session_id": ctx.session.id,
                    "bc_id": created_bc.get("id"),
                    "bc_name": bc.name,
                    "linked_count": linked_count,
                    "failed_count": failed_count,
                    "skipped_count": skipped_count,
                    "failed_us_ids": failed_us_ids,
                    "skipped_us_ids": skipped_us_ids,
                },
            )
        else:
            # us_ids가 비어있을 때 상세 로그 출력
            SmartLogger.log(
                "WARN",
                f"BC {bc_name} has no user_story_ids assigned - skipping link creation",
                category="ingestion.workflow.bc.no_user_stories",
                params={
                    "session_id": ctx.session.id,
                    "bc_id": created_bc.get("id"),
                    "bc_name": bc.name,
                    "bc_type": type(bc).__name__,
                    "bc_has_user_story_ids_attr": hasattr(bc, "user_story_ids"),
                    "bc_attrs": [attr for attr in dir(bc) if not attr.startswith("_")][:20],
                },
            )
        
        return {
            "bounded_context": created_bc,
            "bc": bc,
            "linked_count": linked_count,
            "failed_count": failed_count,
            "skipped_count": skipped_count,
            "failed_us_ids": failed_us_ids,
            "skipped_us_ids": skipped_us_ids,
        }, progress_events, None
    except asyncio.TimeoutError:
        return None, [], "Bounded context creation timeout"
    except Exception as e:
        SmartLogger.log(
            "ERROR",
            "Bounded context create failed",
            category="ingestion.neo4j.bounded_context.create_failed",
            params={
                "session_id": ctx.session.id,
                "bc_name": bc_name,
                "error": str(e),
                "error_type": type(e).__name__,
            },
        )
        return None, [], f"Bounded context creation failed: {e}"


async def identify_bounded_contexts_phase(ctx: IngestionWorkflowContext) -> AsyncGenerator[ProgressEvent, None]:
    """
    Phase 3: identify bounded contexts using LLM, create them in Neo4j, and link user stories.
    Supports chunking for large user stories lists.
    """
    PHASE_START = 20
    PHASE_END = 30
    MERGE_RATIO = 0.1
    
    # Phase 시작
    yield ProgressEvent(
        phase=IngestionPhase.IDENTIFYING_BC,
        message="Bounded Context 식별 시작...",
        progress=PHASE_START
    )
    
    # BC 식별 전에 User Story role 재검증 (Neo4j에서 읽어온 값이 최신인지 확인)
    from api.features.ingestion.requirements_to_user_stories import _infer_role_from_context
    for us in ctx.user_stories:
        role = (getattr(us, "role", "") or "").strip()
        action = (getattr(us, "action", "") or "").strip()
        benefit = (getattr(us, "benefit", "") or "").strip()
        
        # Role 재검증 및 추론
        if not role or role.lower() in ("user", "사용자", ""):
            inferred_role = _infer_role_from_context(action, benefit)
            if inferred_role:
                role = inferred_role
            else:
                role = "customer"
            
            # Update role in the user story object
            try:
                setattr(us, "role", role)
            except Exception:
                try:
                    if hasattr(us, "model_copy"):
                        us = us.model_copy(update={"role": role})
                    elif hasattr(us, "copy"):
                        us = us.copy(update={"role": role})
                except Exception:
                    # Create new instance if update fails
                    try:
                        story_dict = us.model_dump() if hasattr(us, "model_dump") else (us.dict() if hasattr(us, "dict") else dict(us))
                        story_dict["role"] = role
                        from api.features.ingestion.ingestion_contracts import GeneratedUserStory
                        us = GeneratedUserStory(**story_dict)
                        # Replace in context
                        idx = ctx.user_stories.index(us) if us in ctx.user_stories else None
                        if idx is not None:
                            ctx.user_stories[idx] = us
                    except Exception:
                        pass
    
    _bl_map = getattr(ctx, 'bl_by_user_story', None)

    # User Stories를 텍스트로 변환하는 함수
    def us_to_text(us) -> str:
        return format_us_text(us, bl_map=_bl_map)

    # analyzer_graph 전용: BC 과다 생성 방지 가이드 + 이벤트 클러스터링 힌트
    _analyzer_consolidation_guide = ""
    if getattr(ctx, "source_type", "") == "analyzer_graph":
        _analyzer_consolidation_guide = (
            "\n\n## CRITICAL: Legacy Code Analysis — Bounded Context Consolidation\n"
            "These User Stories were extracted from legacy code (functions/procedures). "
            "Legacy systems often have HUNDREDS of small functions that each handle one task. "
            "Do NOT create one BC per function or per small feature.\n\n"
            "**Consolidation rules for code-analyzed systems:**\n"
            "1. Group by BUSINESS DOMAIN (e.g., '자동납부', '청구', '계정관리'), not by function name\n"
            "2. Functions that operate on the SAME database tables belong to the SAME BC\n"
            "3. Functions with similar prefixes (e.g., ProcessAutoDebit*, ValidateAutoDebit*, ChangeAutoDebit*) "
            "are almost certainly the SAME BC\n"
            "4. Target: 5~15 BCs for a typical legacy system. More than 20 is almost always over-split\n"
            "5. A BC should contain 5~50 User Stories. A BC with only 1~2 User Stories should be merged\n"
            "6. Consider the [도메인 커플링] hints in User Stories — coupled domains suggest BC boundaries\n"
        )

    # 이벤트 클러스터링 힌트: Phase 4에서 추출된 이벤트를 도메인 키워드로 그룹핑
    # (모든 source_type에서 활용 — events_from_us가 있으면 동작)
    _event_cluster_hint = _build_event_cluster_hint(ctx)
    
    # 청킹 필요 여부 판단
    if should_chunk_list(ctx.user_stories, item_to_text=us_to_text, max_items=50):
        yield ProgressEvent(
            phase=IngestionPhase.IDENTIFYING_BC,
            message=f"대용량 User Stories 스캐닝 중... ({len(ctx.user_stories)}개)",
            progress=PHASE_START + 1
        )
        
        # User Story 리스트를 청크로 분할 (overlap: 3개)
        story_chunks = split_list_with_overlap(ctx.user_stories, chunk_size=30, overlap_count=3)
        total_chunks = len(story_chunks)
        
        yield ProgressEvent(
            phase=IngestionPhase.IDENTIFYING_BC,
            message=f"User Stories를 {total_chunks}개 청크로 분할 완료",
            progress=PHASE_START + 2
        )
        
        chunk_results = []
        # 이전 청크까지 누적된 BC 목록 — 다음 청크에 전달하여 중복 BC 생성 방지
        _accumulated_bcs: list[dict[str, str]] = []  # [{name, description, user_story_ids_summary}]

        for i, story_chunk in enumerate(story_chunks):
            # Check cancellation before processing chunk
            if getattr(ctx.session, "is_cancelled", False):
                yield ProgressEvent(
                    phase=IngestionPhase.ERROR,
                    message="❌ 생성이 중단되었습니다",
                    progress=getattr(ctx.session, "progress", 0) or 0,
                    data={"error": "Cancelled by user", "cancelled": True},
                )
                return

            # 청크 처리 시작
            chunk_progress = calculate_chunk_progress(
                PHASE_START + 2,
                PHASE_END - int((PHASE_END - PHASE_START) * MERGE_RATIO),
                i,
                total_chunks,
                merge_progress_ratio=0
            )
            yield ProgressEvent(
                phase=IngestionPhase.IDENTIFYING_BC,
                message=f"청크 {i+1}/{total_chunks} 처리 중... ({len(story_chunk)}개 User Stories)",
                progress=chunk_progress
            )

            # 청크별 BC 추출
            stories_text = "\n".join([us_to_text(us) for us in story_chunk])
            # 청크 내 모든 User Story ID 목록을 프롬프트에 포함하여 검증 가능하도록
            chunk_us_ids = [us.id for us in story_chunk]
            stories_text_with_ids = f"Total User Stories in this chunk: {len(chunk_us_ids)}\nUser Story IDs: {', '.join(chunk_us_ids)}\n\n{stories_text}"
            structured_llm = ctx.llm.with_structured_output(BoundedContextList)
            display_lang = getattr(ctx, "display_language", "ko") or "ko"
            display_name_instruction = (
                "\n\nFor each Bounded Context you output, also provide displayName: a short UI label in Korean (e.g. '주문 관리', '결제')."
                if display_lang == "ko"
                else "\n\nFor each Bounded Context you output, also provide displayName: a short UI label in English (e.g. 'Order Management', 'Payment')."
            )
            prompt = IDENTIFY_BC_FROM_STORIES_PROMPT.format(user_stories=stories_text_with_ids) + display_name_instruction + _event_cluster_hint + _analyzer_consolidation_guide

            # 이전 청크에서 이미 식별된 BC 목록 전달 — 동일 도메인 US는 기존 BC에 할당 유도
            if _accumulated_bcs:
                from api.features.ingestion.workflow.utils.chunking import ACCUMULATED_NAMES_MAX
                shown_bcs = _accumulated_bcs[:ACCUMULATED_NAMES_MAX]
                existing_bc_lines = []
                for prev_bc in shown_bcs:
                    existing_bc_lines.append(
                        f"- {prev_bc['name']}: {prev_bc['description']} "
                        f"(assigned: {prev_bc['us_count']} User Stories)"
                    )
                if len(_accumulated_bcs) > ACCUMULATED_NAMES_MAX:
                    existing_bc_lines.append(
                        f"... and {len(_accumulated_bcs) - ACCUMULATED_NAMES_MAX} more BCs"
                    )
                prompt += (
                    "\n\n## ALREADY IDENTIFIED BOUNDED CONTEXTS (from previous chunks)\n"
                    "The following BCs have already been identified from earlier User Stories. "
                    "If a User Story in THIS chunk belongs to one of these existing BCs, "
                    "assign it to that BC using the EXACT SAME NAME. "
                    "Only create a NEW BC if no existing one fits.\n\n"
                    + "\n".join(existing_bc_lines)
                )


            t_llm0 = time.perf_counter()
            try:
                bc_response = await asyncio.wait_for(
                    asyncio.to_thread(
                        structured_llm.invoke,
                        [SystemMessage(content=SYSTEM_PROMPT), HumanMessage(content=prompt)]
                    ),
                    timeout=300.0,
                )
            except asyncio.TimeoutError:
                SmartLogger.log(
                    "ERROR",
                    "BC identification timed out (300s)",
                    category="ingestion.workflow.bc.timeout",
                    params={"session_id": ctx.session.id, "chunk_index": i + 1},
                )
                continue
            except Exception as e:
                # Validation error: user_story_ids가 비어있거나 누락된 경우
                SmartLogger.log(
                    "ERROR",
                    f"BC identification failed: LLM response validation error - {str(e)}",
                    category="ingestion.workflow.bc.llm_validation_error",
                    params={
                        "session_id": ctx.session.id,
                        "chunk_index": i + 1,
                        "error": str(e),
                        "error_type": type(e).__name__,
                    },
                )
                # 재시도 또는 기본값으로 처리
                raise
            llm_ms = int((time.perf_counter() - t_llm0) * 1000)
            
            # Check cancellation after chunk processing
            if getattr(ctx.session, "is_cancelled", False):
                yield ProgressEvent(
                    phase=IngestionPhase.ERROR,
                    message="❌ 생성이 중단되었습니다",
                    progress=getattr(ctx.session, "progress", 0) or 0,
                    data={"error": "Cancelled by user", "cancelled": True},
                )
                return
            
            bcs = getattr(bc_response, "bounded_contexts", []) or []
            
            # BC 응답 검증: 모든 BC가 user_story_ids를 가지고 있는지 확인 (Pydantic model_dump 사용)
            for bc in bcs:
                us_ids = []
                try:
                    if hasattr(bc, "model_dump"):
                        bc_dict = bc.model_dump()
                        us_ids = bc_dict.get("user_story_ids", [])
                    elif hasattr(bc, "dict"):
                        bc_dict = bc.dict()
                        us_ids = bc_dict.get("user_story_ids", [])
                    elif isinstance(bc, dict):
                        us_ids = bc.get("user_story_ids", [])
                    else:
                        us_ids = getattr(bc, "user_story_ids", None) or []
                except Exception:
                    us_ids = getattr(bc, "user_story_ids", None) or []
                
                if not isinstance(us_ids, list) or len(us_ids) == 0:
                    SmartLogger.log(
                        "ERROR",
                        f"BC {getattr(bc, 'name', 'unknown')} has empty or missing user_story_ids - this violates the model constraint",
                        category="ingestion.workflow.bc.empty_user_stories_after_llm",
                        params={
                            "session_id": ctx.session.id,
                            "chunk_index": i + 1,
                            "bc_name": getattr(bc, "name", "unknown"),
                            "bc_id": getattr(bc, "id", None),
                        },
                    )
            
            # BC 식별 결과 로깅 (각 BC의 user_story_ids 확인)
            for bc in bcs:
                us_ids = []
                try:
                    if hasattr(bc, "model_dump"):
                        bc_dict = bc.model_dump()
                        us_ids = bc_dict.get("user_story_ids", [])
                    elif hasattr(bc, "dict"):
                        bc_dict = bc.dict()
                        us_ids = bc_dict.get("user_story_ids", [])
                    elif isinstance(bc, dict):
                        us_ids = bc.get("user_story_ids", [])
                    else:
                        us_ids = getattr(bc, "user_story_ids", []) or []
                except Exception:
                    us_ids = getattr(bc, "user_story_ids", []) or []
                SmartLogger.log(
                    "INFO" if us_ids else "WARN",
                    f"BC identified: {getattr(bc, 'name', 'unknown')} with {len(us_ids)} User Stories",
                    category="ingestion.workflow.bc.identified",
                    params={
                        "session_id": ctx.session.id,
                        "chunk_index": i + 1,
                        "bc_name": getattr(bc, "name", "unknown"),
                        "user_story_ids": us_ids,
                        "user_story_count": len(us_ids),
                        "bc_type": type(bc).__name__,
                    },
                )
            
            # 청크 내 모든 User Story가 할당되었는지 검증 (Pydantic model_dump 사용)
            chunk_assigned_us_ids = set()
            for bc in bcs:
                us_ids = []
                try:
                    if hasattr(bc, "model_dump"):
                        bc_dict = bc.model_dump()
                        us_ids = bc_dict.get("user_story_ids", [])
                    elif hasattr(bc, "dict"):
                        bc_dict = bc.dict()
                        us_ids = bc_dict.get("user_story_ids", [])
                    elif isinstance(bc, dict):
                        us_ids = bc.get("user_story_ids", [])
                    else:
                        us_ids = getattr(bc, "user_story_ids", []) or []
                except Exception:
                    us_ids = getattr(bc, "user_story_ids", []) or []
                chunk_assigned_us_ids.update(us_ids)
            chunk_us_ids = {us.id for us in story_chunk}
            chunk_unassigned = chunk_us_ids - chunk_assigned_us_ids
            
            if chunk_unassigned:
                # 누락된 User Story를 LLM에게 다시 할당 요청
                unassigned_stories = [us for us in story_chunk if us.id in chunk_unassigned]
                unassigned_text = "\n".join([us_to_text(us) for us in unassigned_stories])
                # BC의 user_story_ids를 안전하게 가져오기
                bc_info_list = []
                for bc in bcs:
                    us_ids = []
                    try:
                        if hasattr(bc, "model_dump"):
                            bc_dict = bc.model_dump()
                            us_ids = bc_dict.get("user_story_ids", [])
                        elif hasattr(bc, "dict"):
                            bc_dict = bc.dict()
                            us_ids = bc_dict.get("user_story_ids", [])
                        elif isinstance(bc, dict):
                            us_ids = bc.get("user_story_ids", [])
                        else:
                            us_ids = getattr(bc, "user_story_ids", []) or []
                    except Exception:
                        us_ids = getattr(bc, "user_story_ids", []) or []
                    bc_info_list.append(f"- {bc.name}: {bc.description} (Current user_story_ids: {', '.join(us_ids)})")
                existing_bcs_text = "\n".join(bc_info_list)
                
                fix_prompt = f"""The following User Stories from the previous analysis were NOT assigned to any Bounded Context. You MUST assign each of them to the most appropriate existing BC.

Existing Bounded Contexts:
{existing_bcs_text}

Unassigned User Stories (MUST be assigned):
{unassigned_text}

For each unassigned User Story, determine which existing Bounded Context it best fits and add its ID to that BC's user_story_ids list. If no existing BC is appropriate, create a new BC.

CRITICAL: Every User Story listed above MUST be assigned to exactly ONE BC. Return the complete updated list of BoundedContextCandidate objects with all User Stories assigned."""
                
                fix_response = await asyncio.wait_for(
                    asyncio.to_thread(
                        structured_llm.invoke,
                        [SystemMessage(content=SYSTEM_PROMPT), HumanMessage(content=fix_prompt)]
                    ),
                    timeout=300.0,
                )
                fixed_bcs = getattr(fix_response, "bounded_contexts", []) or []
                
                # 수정된 BC로 교체
                if fixed_bcs:
                    bcs = fixed_bcs
            
            chunk_results.append(bcs)

            # 이 청크에서 식별된 BC를 누적 목록에 추가 (다음 청크에 전달용)
            for bc in bcs:
                bc_name = getattr(bc, "name", "")
                bc_desc = getattr(bc, "description", "")
                us_ids = []
                try:
                    if hasattr(bc, "model_dump"):
                        us_ids = bc.model_dump().get("user_story_ids", [])
                    elif isinstance(bc, dict):
                        us_ids = bc.get("user_story_ids", [])
                    else:
                        us_ids = getattr(bc, "user_story_ids", []) or []
                except Exception:
                    us_ids = getattr(bc, "user_story_ids", []) or []
                # 이미 같은 이름의 BC가 있으면 US 수만 갱신
                existing = next((b for b in _accumulated_bcs if b["name"] == bc_name), None)
                if existing:
                    existing["us_count"] = str(int(existing["us_count"]) + len(us_ids))
                else:
                    _accumulated_bcs.append({
                        "name": bc_name,
                        "description": bc_desc,
                        "us_count": str(len(us_ids)),
                    })

            # 청크 처리 완료
            chunk_complete_progress = calculate_chunk_progress(
                PHASE_START + 2,
                PHASE_END - int((PHASE_END - PHASE_START) * MERGE_RATIO),
                i + 1,
                total_chunks,
                merge_progress_ratio=0
            )
            yield ProgressEvent(
                phase=IngestionPhase.IDENTIFYING_BC,
                message=f"청크 {i+1}/{total_chunks} 완료 ({len(bcs)}개 BC 식별)",
                progress=chunk_complete_progress
            )
        
        # 결과 병합 시작
        yield ProgressEvent(
            phase=IngestionPhase.IDENTIFYING_BC,
            message=f"{total_chunks}개 청크 결과 병합 중...",
            progress=PHASE_END - 3
        )
        
        # 결과 병합 (중복 제거: key 우선, 없으면 name, 둘 다 없으면 id)
        bc_candidates = merge_chunk_results(
            chunk_results,
            dedupe_key=lambda bc: (
                getattr(bc, "key", None) or 
                getattr(bc, "name", None) or 
                getattr(bc, "id", None) or 
                f"__fallback_{id(bc)}"  # 최후의 수단: 객체 ID
            )
        )
        
        # BC 병합 후 user_story_ids 합치기: 같은 이름의 BC가 여러 청크에서 나타날 때 user_story_ids를 합쳐야 함
        bc_by_name: dict[str, list[Any]] = {}
        for bc in bc_candidates:
            bc_name = getattr(bc, "name", None) or ""
            if bc_name not in bc_by_name:
                bc_by_name[bc_name] = []
            bc_by_name[bc_name].append(bc)
        
        # 같은 이름의 BC가 여러 개 있으면 user_story_ids를 합침
        merged_bc_candidates = []
        for bc_name, bcs_with_same_name in bc_by_name.items():
            if len(bcs_with_same_name) == 1:
                # 중복이 없으면 그대로 사용
                merged_bc_candidates.append(bcs_with_same_name[0])
            else:
                # 중복이 있으면 첫 번째 BC를 기준으로 user_story_ids를 합침
                base_bc = bcs_with_same_name[0]
                all_us_ids = set()
                
                # 모든 BC의 user_story_ids 수집
                for bc in bcs_with_same_name:
                    us_ids = []
                    try:
                        if hasattr(bc, "model_dump"):
                            bc_dict = bc.model_dump()
                            us_ids = bc_dict.get("user_story_ids", [])
                        elif hasattr(bc, "dict"):
                            bc_dict = bc.dict()
                            us_ids = bc_dict.get("user_story_ids", [])
                        elif isinstance(bc, dict):
                            us_ids = bc.get("user_story_ids", [])
                        else:
                            us_ids = getattr(bc, "user_story_ids", []) or []
                    except Exception:
                        us_ids = getattr(bc, "user_story_ids", []) or []
                    
                    if isinstance(us_ids, list):
                        all_us_ids.update(us_ids)
                
                # 합친 user_story_ids로 업데이트
                merged_us_ids = list(all_us_ids)
                try:
                    if hasattr(base_bc, "model_copy"):
                        merged_bc = base_bc.model_copy(update={"user_story_ids": merged_us_ids})
                    elif hasattr(base_bc, "copy"):
                        merged_bc = base_bc.copy(update={"user_story_ids": merged_us_ids})
                    else:
                        setattr(base_bc, "user_story_ids", merged_us_ids)
                        merged_bc = base_bc
                except Exception as e:
                    SmartLogger.log(
                        "WARN",
                        f"Failed to merge user_story_ids for BC {bc_name}: {e}",
                        category="ingestion.workflow.bc.merge_user_stories_error",
                        params={
                            "session_id": ctx.session.id,
                            "bc_name": bc_name,
                            "error": str(e),
                        },
                    )
                    merged_bc = base_bc
                
                merged_bc_candidates.append(merged_bc)
                
                SmartLogger.log(
                    "INFO",
                    f"Merged BC {bc_name}: combined {len(bcs_with_same_name)} BCs with {len(merged_us_ids)} total User Stories",
                    category="ingestion.workflow.bc.merge_complete",
                    params={
                        "session_id": ctx.session.id,
                        "bc_name": bc_name,
                        "bc_count": len(bcs_with_same_name),
                        "merged_user_story_count": len(merged_us_ids),
                    },
                )
        
        bc_candidates = merged_bc_candidates
        ctx.bounded_contexts = bc_candidates
        
        # 결과 병합 완료
        yield ProgressEvent(
            phase=IngestionPhase.IDENTIFYING_BC,
            message=f"Bounded Context 식별 완료 (총 {len(bc_candidates)}개)",
            progress=PHASE_END - 2
        )
    else:
        # 기존 로직 (청킹 불필요)
        yield ProgressEvent(
            phase=IngestionPhase.IDENTIFYING_BC,
            message="Bounded Context 식별 중...",
            progress=PHASE_START + 5
        )
        
        stories_text = "\n".join([us_to_text(us) for us in ctx.user_stories])
        # 모든 User Story ID 목록을 프롬프트에 포함하여 검증 가능하도록
        all_us_ids = [us.id for us in ctx.user_stories]
        stories_text_with_ids = f"Total User Stories: {len(all_us_ids)}\nUser Story IDs: {', '.join(all_us_ids)}\n\n{stories_text}"
        structured_llm = ctx.llm.with_structured_output(BoundedContextList)
        display_lang = getattr(ctx, "display_language", "ko") or "ko"
        display_name_instruction = (
            "\n\nFor each Bounded Context you output, also provide displayName: a short UI label in Korean (e.g. '주문 관리', '결제')."
            if display_lang == "ko"
            else "\n\nFor each Bounded Context you output, also provide displayName: a short UI label in English (e.g. 'Order Management', 'Payment')."
        )
        prompt = IDENTIFY_BC_FROM_STORIES_PROMPT.format(user_stories=stories_text_with_ids) + display_name_instruction + _analyzer_consolidation_guide
        bc_response = await asyncio.wait_for(
            asyncio.to_thread(
                structured_llm.invoke,
                [SystemMessage(content=SYSTEM_PROMPT), HumanMessage(content=prompt)]
            ),
            timeout=300.0,
        )

        bc_candidates = bc_response.bounded_contexts
        
        # BC 식별 결과 로깅 (각 BC의 user_story_ids 확인 - Pydantic model_dump 사용)
        for bc in bc_candidates:
            us_ids = []
            try:
                if hasattr(bc, "model_dump"):
                    bc_dict = bc.model_dump()
                    us_ids = bc_dict.get("user_story_ids", [])
                elif hasattr(bc, "dict"):
                    bc_dict = bc.dict()
                    us_ids = bc_dict.get("user_story_ids", [])
                elif isinstance(bc, dict):
                    us_ids = bc.get("user_story_ids", [])
                else:
                    us_ids = getattr(bc, "user_story_ids", []) or []
            except Exception:
                us_ids = getattr(bc, "user_story_ids", []) or []
            
            SmartLogger.log(
                "INFO" if us_ids else "WARN",
                f"BC identified: {getattr(bc, 'name', 'unknown')} with {len(us_ids)} User Stories",
                category="ingestion.workflow.bc.identified",
                params={
                    "session_id": ctx.session.id,
                    "bc_name": getattr(bc, "name", "unknown"),
                    "user_story_ids": us_ids,
                    "user_story_count": len(us_ids),
                    "bc_type": type(bc).__name__,
                },
            )
        
        ctx.bounded_contexts = bc_candidates
        
        yield ProgressEvent(
            phase=IngestionPhase.IDENTIFYING_BC,
            message=f"Bounded Context 식별 완료 (총 {len(bc_candidates)}개)",
            progress=PHASE_END - 2
        )

    # bc_candidates는 위에서 ctx.bounded_contexts에 저장됨
    bc_candidates = ctx.bounded_contexts

    # ── BC 의미적 통합 (Semantic Consolidation) ──────────────────────────
    # BC 후보가 7개 초과일 때만 실행: LLM에 BC 목록을 전달하여 의미적 유사 그룹 식별 후 병합
    BC_CONSOLIDATION_THRESHOLD = 7
    if len(bc_candidates) > BC_CONSOLIDATION_THRESHOLD:
        from api.features.ingestion.event_storming.state import BCConsolidationResult
        from api.features.ingestion.event_storming.prompts import CONSOLIDATE_BCS_PROMPT

        # target_bc_count는 강제가 아닌 참고값.
        # LLM이 BC 목록을 보고 의미적 유사성을 판단하므로 정확한 수치보다는
        # "현재 수가 많다"는 시그널이 중요.
        target_bc_count = max(3, len(bc_candidates) // 2)

        # BC 후보 요약 텍스트 생성
        bc_summary_lines = []
        for bc in bc_candidates:
            bc_name = getattr(bc, "name", "unknown")
            bc_desc = getattr(bc, "description", "")
            us_ids = []
            try:
                if hasattr(bc, "model_dump"):
                    us_ids = bc.model_dump().get("user_story_ids", [])
                elif isinstance(bc, dict):
                    us_ids = bc.get("user_story_ids", [])
                else:
                    us_ids = getattr(bc, "user_story_ids", []) or []
            except Exception:
                us_ids = getattr(bc, "user_story_ids", []) or []
            bc_summary_lines.append(f"- {bc_name}: {bc_desc} (User Stories: {len(us_ids)})")
        bc_candidates_text = "\n".join(bc_summary_lines)

        consolidation_prompt = CONSOLIDATE_BCS_PROMPT.format(
            bc_candidates=bc_candidates_text,
            target_bc_count=target_bc_count,
        )

        yield ProgressEvent(
            phase=IngestionPhase.IDENTIFYING_BC,
            message=f"BC 의미적 통합 분석 중... ({len(bc_candidates)}개 → 목표 ~{target_bc_count}개)",
            progress=PHASE_END - 2,
        )

        try:
            consolidation_llm = ctx.llm.with_structured_output(BCConsolidationResult)
            consolidation_response = await asyncio.wait_for(
                asyncio.to_thread(
                    consolidation_llm.invoke,
                    [SystemMessage(content=SYSTEM_PROMPT), HumanMessage(content=consolidation_prompt)]
                ),
                timeout=120.0,
            )

            merge_instructions = getattr(consolidation_response, "merge_instructions", []) or []

            if merge_instructions:
                # BC 이름 → 인덱스 매핑
                bc_name_to_idx = {getattr(bc, "name", ""): i for i, bc in enumerate(bc_candidates)}
                absorbed_indices: set[int] = set()

                for instruction in merge_instructions:
                    keep_name = instruction.keep
                    absorb_names = instruction.absorb

                    keep_idx = bc_name_to_idx.get(keep_name)
                    if keep_idx is None:
                        continue

                    keep_bc = bc_candidates[keep_idx]

                    # 유지할 BC의 user_story_ids 수집
                    keep_us_ids = set()
                    try:
                        if hasattr(keep_bc, "model_dump"):
                            keep_us_ids = set(keep_bc.model_dump().get("user_story_ids", []))
                        elif isinstance(keep_bc, dict):
                            keep_us_ids = set(keep_bc.get("user_story_ids", []))
                        else:
                            keep_us_ids = set(getattr(keep_bc, "user_story_ids", []) or [])
                    except Exception:
                        keep_us_ids = set(getattr(keep_bc, "user_story_ids", []) or [])

                    for absorb_name in absorb_names:
                        absorb_idx = bc_name_to_idx.get(absorb_name)
                        if absorb_idx is None or absorb_idx in absorbed_indices:
                            continue

                        absorb_bc = bc_candidates[absorb_idx]
                        # 흡수될 BC의 user_story_ids 수집
                        absorb_us_ids = []
                        try:
                            if hasattr(absorb_bc, "model_dump"):
                                absorb_us_ids = absorb_bc.model_dump().get("user_story_ids", [])
                            elif isinstance(absorb_bc, dict):
                                absorb_us_ids = absorb_bc.get("user_story_ids", [])
                            else:
                                absorb_us_ids = getattr(absorb_bc, "user_story_ids", []) or []
                        except Exception:
                            absorb_us_ids = getattr(absorb_bc, "user_story_ids", []) or []

                        keep_us_ids.update(absorb_us_ids)
                        absorbed_indices.add(absorb_idx)

                        SmartLogger.log(
                            "INFO",
                            f"BC semantic merge: {absorb_name} → {keep_name} ({len(absorb_us_ids)} US transferred)",
                            category="ingestion.workflow.bc.semantic_merge",
                            params={
                                "session_id": ctx.session.id,
                                "keep_bc": keep_name,
                                "absorb_bc": absorb_name,
                                "transferred_us_count": len(absorb_us_ids),
                                "rationale": instruction.rationale,
                            },
                        )

                    # 유지할 BC에 합산된 user_story_ids 업데이트
                    merged_ids = list(keep_us_ids)
                    try:
                        if hasattr(keep_bc, "model_copy"):
                            bc_candidates[keep_idx] = keep_bc.model_copy(update={"user_story_ids": merged_ids})
                        elif hasattr(keep_bc, "copy"):
                            bc_candidates[keep_idx] = keep_bc.copy(update={"user_story_ids": merged_ids})
                        else:
                            setattr(keep_bc, "user_story_ids", merged_ids)
                    except Exception as e:
                        SmartLogger.log(
                            "WARN",
                            f"Failed to update user_story_ids for kept BC {keep_name}: {e}",
                            category="ingestion.workflow.bc.semantic_merge_update_error",
                            params={"session_id": ctx.session.id, "bc_name": keep_name, "error": str(e)},
                        )

                # 흡수된 BC 제거
                bc_candidates = [bc for i, bc in enumerate(bc_candidates) if i not in absorbed_indices]
                ctx.bounded_contexts = bc_candidates

                SmartLogger.log(
                    "INFO",
                    f"BC semantic consolidation complete: {len(absorbed_indices)} BCs absorbed, {len(bc_candidates)} BCs remaining",
                    category="ingestion.workflow.bc.semantic_consolidation_summary",
                    params={
                        "session_id": ctx.session.id,
                        "absorbed_count": len(absorbed_indices),
                        "remaining_count": len(bc_candidates),
                        "target_count": target_bc_count,
                    },
                )

                yield ProgressEvent(
                    phase=IngestionPhase.IDENTIFYING_BC,
                    message=f"BC 의미적 통합 완료: {len(absorbed_indices)}개 병합 → {len(bc_candidates)}개 BC",
                    progress=PHASE_END - 2,
                )
            else:
                SmartLogger.log(
                    "INFO",
                    "BC semantic consolidation: no merges needed",
                    category="ingestion.workflow.bc.semantic_consolidation_none",
                    params={"session_id": ctx.session.id, "bc_count": len(bc_candidates)},
                )
        except Exception as e:
            SmartLogger.log(
                "WARN",
                f"BC semantic consolidation failed, continuing without merge: {e}",
                category="ingestion.workflow.bc.semantic_consolidation_error",
                params={"session_id": ctx.session.id, "error": str(e), "error_type": type(e).__name__},
            )
    # ── End BC 의미적 통합 ──────────────────────────────────────────────

    # BC 후보의 user_story_ids 검증: 존재하지 않는 ID 제거 및 중복 할당 방지
    valid_us_ids = {us.id for us in ctx.user_stories}
    us_to_bc_map: dict[str, str] = {}  # User Story ID -> BC 이름 (중복 할당 추적)
    
    SmartLogger.log(
        "INFO",
        f"Validating BC user_story_ids assignments: {len(valid_us_ids)} valid User Stories, {len(bc_candidates)} BCs",
        category="ingestion.workflow.bc.validation_start",
        params={
            "session_id": ctx.session.id,
            "valid_us_count": len(valid_us_ids),
            "bc_count": len(bc_candidates),
        },
    )
    
    for bc in bc_candidates:
        # 여러 방법으로 user_story_ids 가져오기 (Pydantic 모델의 경우 model_dump 우선 사용)
        original_ids = []
        try:
            # 방법 1: Pydantic model_dump 사용 (가장 안전)
            if hasattr(bc, "model_dump"):
                bc_dict = bc.model_dump()
                original_ids = bc_dict.get("user_story_ids", [])
            elif hasattr(bc, "dict"):
                bc_dict = bc.dict()
                original_ids = bc_dict.get("user_story_ids", [])
            # 방법 2: dict 접근
            elif isinstance(bc, dict):
                original_ids = bc.get("user_story_ids", [])
            # 방법 3: 직접 속성 접근 (fallback)
            else:
                original_ids = getattr(bc, "user_story_ids", None)
                if original_ids is None:
                    original_ids = []
        except Exception as e:
            SmartLogger.log(
                "WARN",
                f"Failed to get user_story_ids from BC {getattr(bc, 'name', 'unknown')} during validation: {e}",
                category="ingestion.workflow.bc.validation_get_error",
                params={
                    "session_id": ctx.session.id,
                    "bc_name": getattr(bc, "name", "unknown"),
                    "error": str(e),
                },
            )
        
        if not isinstance(original_ids, list):
            original_ids = []
        original_ids = [us_id for us_id in original_ids if us_id]  # None이나 빈 문자열 제거
        
        # 존재하는 User Story ID만 필터링
        valid_ids = [us_id for us_id in original_ids if us_id in valid_us_ids]
        invalid_ids = [us_id for us_id in original_ids if us_id not in valid_us_ids]
        
        # original_ids가 비어있으면 경고
        if not original_ids:
            SmartLogger.log(
                "ERROR",
                f"BC {getattr(bc, 'name', 'unknown')} has NO user_story_ids from LLM response - this is a critical issue",
                category="ingestion.workflow.bc.no_user_stories_from_llm",
                params={
                    "session_id": ctx.session.id,
                    "bc_name": getattr(bc, "name", "unknown"),
                    "bc_type": type(bc).__name__,
                },
            )
        
        # 중복 할당 체크: 하나의 User Story는 하나의 BC에만 속해야 함 (DDD 원칙)
        deduplicated_ids = []
        duplicate_ids = []
        for us_id in valid_ids:
            if us_id in us_to_bc_map:
                # 이미 다른 BC에 할당됨 - 첫 번째 BC만 유지
                duplicate_ids.append(us_id)
            else:
                # 첫 번째 할당 - 유지
                us_to_bc_map[us_id] = bc.name
                deduplicated_ids.append(us_id)
        
        # user_story_ids 업데이트 (존재하지 않는 ID 제거 + 중복 제거)
        final_ids = deduplicated_ids
        
        # BC 객체 업데이트 (Pydantic model이므로 model_copy 사용)
        updated_bc = None
        try:
            # Pydantic model인 경우 model_copy 사용 (setattr은 제대로 반영되지 않을 수 있음)
            if hasattr(bc, "model_copy"):
                updated_bc = bc.model_copy(update={"user_story_ids": final_ids})
            elif hasattr(bc, "copy"):
                updated_bc = bc.copy(update={"user_story_ids": final_ids})
            else:
                # 일반 객체인 경우 setattr 시도
                setattr(bc, "user_story_ids", final_ids)
                updated_bc = bc
        except Exception as e:
            SmartLogger.log(
                "WARN",
                f"Failed to update user_story_ids for BC {getattr(bc, 'name', 'unknown')}: {e}",
                category="ingestion.workflow.bc.update_user_story_ids_error",
                params={
                    "session_id": ctx.session.id,
                    "bc_name": getattr(bc, "name", "unknown"),
                    "error": str(e),
                },
            )
            updated_bc = bc
        
        # 리스트에 업데이트된 BC 객체 반영
        bc_idx_in_list = bc_candidates.index(bc) if bc in bc_candidates else -1
        if bc_idx_in_list >= 0:
            bc_candidates[bc_idx_in_list] = updated_bc
            # bc 변수도 업데이트하여 이후 참조가 최신 값을 사용하도록 함
            bc = updated_bc
    
    # 검증 후 빈 user_story_ids를 가진 BC 제거 (BC는 최소 하나의 User Story를 가져야 함)
    bc_candidates_with_stories = []
    empty_bcs = []
    for bc in bc_candidates:
        # 여러 방법으로 user_story_ids 확인 (Pydantic 모델의 경우 model_dump 우선 사용)
        final_ids = []
        try:
            # 방법 1: Pydantic model_dump 사용 (가장 안전)
            if hasattr(bc, "model_dump"):
                bc_dict = bc.model_dump()
                final_ids = bc_dict.get("user_story_ids", [])
            elif hasattr(bc, "dict"):
                bc_dict = bc.dict()
                final_ids = bc_dict.get("user_story_ids", [])
            # 방법 2: dict 접근
            elif isinstance(bc, dict):
                final_ids = bc.get("user_story_ids", [])
            # 방법 3: 직접 속성 접근 (fallback)
            else:
                final_ids = getattr(bc, "user_story_ids", None)
                if final_ids is None:
                    final_ids = []
        except Exception:
            pass
        
        if not isinstance(final_ids, list):
            final_ids = []
        final_ids = [us_id for us_id in final_ids if us_id]  # None이나 빈 문자열 제거
        
        if not final_ids:
            empty_bcs.append(bc.name)
            SmartLogger.log(
                "WARN",
                f"BC {bc.name} has empty user_story_ids after validation - will be removed",
                category="ingestion.workflow.bc.empty_after_validation",
                params={
                    "session_id": ctx.session.id,
                    "bc_name": bc.name,
                },
            )
        else:
            bc_candidates_with_stories.append(bc)
            SmartLogger.log(
                "INFO",
                f"BC {bc.name} validated with {len(final_ids)} User Stories",
                category="ingestion.workflow.bc.validated",
                params={
                    "session_id": ctx.session.id,
                    "bc_name": bc.name,
                    "user_story_count": len(final_ids),
                },
            )
    
    if empty_bcs:
        SmartLogger.log(
            "WARN",
            f"Removing {len(empty_bcs)} BCs with no User Stories: {', '.join(empty_bcs)}",
            category="ingestion.workflow.bc.empty_removed",
            params={
                "session_id": ctx.session.id,
                "empty_bc_names": empty_bcs,
            },
        )
    
    # 빈 BC 제거 후 업데이트
    bc_candidates = bc_candidates_with_stories
    ctx.bounded_contexts = bc_candidates

    # 누락된 User Story 확인 및 자동 할당
    all_assigned_us_ids = set()
    for bc in bc_candidates:
        # Pydantic 모델의 경우 model_dump 우선 사용
        us_ids = []
        try:
            if hasattr(bc, "model_dump"):
                bc_dict = bc.model_dump()
                us_ids = bc_dict.get("user_story_ids", [])
            elif hasattr(bc, "dict"):
                bc_dict = bc.dict()
                us_ids = bc_dict.get("user_story_ids", [])
            elif isinstance(bc, dict):
                us_ids = bc.get("user_story_ids", [])
            else:
                us_ids = getattr(bc, "user_story_ids", []) or []
        except Exception:
            us_ids = getattr(bc, "user_story_ids", []) or []
        all_assigned_us_ids.update(us_ids)
    
    all_us_ids = {us.id for us in ctx.user_stories}
    unassigned_us_ids = all_us_ids - all_assigned_us_ids
    
    SmartLogger.log(
        "INFO",
        f"BC assignment validation: {len(all_assigned_us_ids)} assigned, {len(unassigned_us_ids)} unassigned out of {len(all_us_ids)} total",
        category="ingestion.workflow.bc.validation_summary",
        params={
            "session_id": ctx.session.id,
            "total_us_count": len(all_us_ids),
            "assigned_count": len(all_assigned_us_ids),
            "unassigned_count": len(unassigned_us_ids),
            "unassigned_ids": list(unassigned_us_ids),
        },
    )
    
    if unassigned_us_ids:
        SmartLogger.log(
            "WARN",
            f"Found {len(unassigned_us_ids)} User Stories still unassigned after all BC links",
            category="ingestion.workflow.bc.remaining_unassigned",
            params={
                "session_id": ctx.session.id,
                "unassigned_count": len(unassigned_us_ids),
                "unassigned_us_ids": list(unassigned_us_ids),
            },
        )
        
        yield ProgressEvent(
            phase=IngestionPhase.IDENTIFYING_BC,
            message=f"누락된 {len(unassigned_us_ids)}개 User Story를 BC에 자동 할당 중...",
            progress=PHASE_END - 2,
        )
        
        # 누락된 User Story들을 LLM에게 적절한 BC에 할당하도록 요청
        unassigned_stories = [us for us in ctx.user_stories if us.id in unassigned_us_ids]
        unassigned_stories_text = "\n".join(
            [format_us_text(us, bl_map=_bl_map) for us in unassigned_stories]
        )
        
        bc_info_text = "\n".join(
            [
                f"- {bc.name}: {bc.description} (Rationale: {getattr(bc, 'rationale', 'N/A')})"
                for bc in bc_candidates
            ]
        )
        
        assignment_prompt = f"""The following User Stories were not assigned to any Bounded Context during the initial identification phase. Please assign each User Story to the most appropriate existing Bounded Context based on domain alignment, business capability, and cohesion.

Existing Bounded Contexts:
{bc_info_text}

Unassigned User Stories:
{unassigned_stories_text}

For each unassigned User Story, determine which Bounded Context it best fits based on:
1. Domain concepts and terminology
2. Business capability alignment
3. Data ownership and responsibility
4. Actor (role) patterns

Respond with a JSON object mapping User Story IDs to Bounded Context names:
{{
  "US-001": "OrderManagement",
  "US-002": "PaymentProcessing",
  ...
}}

IMPORTANT: Every User Story MUST be assigned to exactly ONE Bounded Context. Do not leave any User Story unassigned."""
        
        try:
            provider, model = get_llm_provider_model()
            llm = ctx.llm
            
            # LLM에게 할당 요청 (structured output 대신 JSON 파싱)
            response = await asyncio.wait_for(
                asyncio.to_thread(
                    llm.invoke,
                    [SystemMessage(content=SYSTEM_PROMPT), HumanMessage(content=assignment_prompt)]
                ),
                timeout=300.0,
            )
            
            # JSON 응답 파싱
            response_text = response.content if hasattr(response, "content") else str(response)
            assignment_dict = {}
            
            # JSON 객체 찾기 (중첩된 중괄호 처리)
            json_start = response_text.find('{')
            if json_start >= 0:
                brace_count = 0
                json_end = json_start
                for i, char in enumerate(response_text[json_start:], start=json_start):
                    if char == '{':
                        brace_count += 1
                    elif char == '}':
                        brace_count -= 1
                        if brace_count == 0:
                            json_end = i + 1
                            break
                
                json_str = response_text[json_start:json_end]
                try:
                    assignment_dict = json.loads(json_str)
                except json.JSONDecodeError:
                    # 정규식으로 간단한 매핑 찾기
                    pattern = r'"([^"]+)"\s*:\s*"([^"]+)"'
                    matches = re.findall(pattern, response_text)
                    assignment_dict = {us_id: bc_name for us_id, bc_name in matches if us_id in unassigned_us_ids}
            else:
                # 정규식으로 간단한 매핑 찾기
                pattern = r'"([^"]+)"\s*:\s*"([^"]+)"'
                matches = re.findall(pattern, response_text)
                assignment_dict = {us_id: bc_name for us_id, bc_name in matches if us_id in unassigned_us_ids}
            
            # 할당 결과를 BC에 반영
            assignment_count = 0
            for us_id, bc_name in assignment_dict.items():
                if us_id in unassigned_us_ids:
                    # 해당 이름의 BC 찾기
                    bc_idx = next((i for i, bc in enumerate(bc_candidates) if bc.name == bc_name), None)
                    if bc_idx is not None:
                        target_bc = bc_candidates[bc_idx]
                        current_ids = getattr(target_bc, "user_story_ids", []) or []
                        if us_id not in current_ids:
                            current_ids.append(us_id)
                            # Pydantic model인 경우 model_copy 사용 (setattr은 제대로 반영되지 않을 수 있음)
                            try:
                                if hasattr(target_bc, "model_copy"):
                                    target_bc = target_bc.model_copy(update={"user_story_ids": current_ids})
                                elif hasattr(target_bc, "copy"):
                                    target_bc = target_bc.copy(update={"user_story_ids": current_ids})
                                else:
                                    # 일반 객체인 경우 setattr 시도
                                    setattr(target_bc, "user_story_ids", current_ids)
                                # 리스트에 업데이트된 BC 객체 반영
                                bc_candidates[bc_idx] = target_bc
                            except Exception as e:
                                SmartLogger.log(
                                    "WARN",
                                    f"Failed to update user_story_ids for BC {bc_name} during auto-assignment: {e}",
                                    category="ingestion.workflow.bc.auto_assignment_update_error",
                                    params={
                                        "session_id": ctx.session.id,
                                        "bc_name": bc_name,
                                        "user_story_id": us_id,
                                        "error": str(e),
                                    },
                                )
                            assignment_count += 1
                            SmartLogger.log(
                                "INFO",
                                f"Auto-assigned User Story {us_id} to BC {bc_name}",
                                category="ingestion.workflow.bc.auto_assigned",
                                params={
                                    "session_id": ctx.session.id,
                                    "user_story_id": us_id,
                                    "bc_name": bc_name,
                                },
                            )
            
            if assignment_count == 0:
                SmartLogger.log(
                    "ERROR",
                    f"Failed to auto-assign any User Stories. All {len(unassigned_us_ids)} remain unassigned.",
                    category="ingestion.workflow.bc.auto_assignment_failed",
                    params={
                        "session_id": ctx.session.id,
                        "unassigned_us_ids": list(unassigned_us_ids),
                    },
                )
        except Exception as e:
            SmartLogger.log(
                "ERROR",
                f"Failed to auto-assign unassigned User Stories: {str(e)}",
                category="ingestion.workflow.bc.auto_assignment_error",
                params={
                    "session_id": ctx.session.id,
                    "unassigned_count": len(unassigned_us_ids),
                    "error": str(e),
                },
            )
    
    # 생성 결과 요약 및 최종 검증
    empty_bc_names = []
    for bc in bc_candidates:
        us_ids = []
        try:
            if hasattr(bc, "model_dump"):
                bc_dict = bc.model_dump()
                us_ids = bc_dict.get("user_story_ids", [])
            elif hasattr(bc, "dict"):
                bc_dict = bc.dict()
                us_ids = bc_dict.get("user_story_ids", [])
            elif isinstance(bc, dict):
                us_ids = bc.get("user_story_ids", [])
            else:
                us_ids = getattr(bc, "user_story_ids", []) or []
        except Exception:
            us_ids = getattr(bc, "user_story_ids", []) or []
        
        if not isinstance(us_ids, list) or len(us_ids) == 0:
            empty_bc_names.append(getattr(bc, "name", "unknown"))
    
    if empty_bc_names:
        SmartLogger.log(
            "ERROR",
            f"Found {len(empty_bc_names)} BCs with empty user_story_ids before creation: {', '.join(empty_bc_names)}",
            category="ingestion.workflow.bc.empty_before_creation",
            params={
                "session_id": ctx.session.id,
                "empty_bc_names": empty_bc_names,
                "bc_count": len(bc_candidates),
            },
        )
    
    SmartLogger.log(
        "INFO",
        f"Bounded contexts identified: {len(bc_candidates)} BCs ready for creation",
        category="ingestion.workflow.bc.summary",
        params={
            "session_id": ctx.session.id,
            "bc_count": len(bc_candidates),
            "empty_bc_count": len(empty_bc_names),
        },
    )

    # Process all bounded contexts in parallel
    if bc_candidates:
        # Check cancellation before parallel processing
        if getattr(ctx.session, "is_cancelled", False):
            yield ProgressEvent(
                phase=IngestionPhase.ERROR,
                message="❌ 생성이 중단되었습니다",
                progress=getattr(ctx.session, "progress", 0) or 0,
                data={"error": "Cancelled by user", "cancelled": True},
            )
            return
        
        # BC 생성 전에 각 BC의 user_story_ids 확인 및 ProgressEvent로 전달
        bc_summary = []
        for bc in bc_candidates:
            us_ids = []
            try:
                if hasattr(bc, "model_dump"):
                    bc_dict = bc.model_dump()
                    us_ids = bc_dict.get("user_story_ids", [])
                elif hasattr(bc, "dict"):
                    bc_dict = bc.dict()
                    us_ids = bc_dict.get("user_story_ids", [])
                elif isinstance(bc, dict):
                    us_ids = bc.get("user_story_ids", [])
                else:
                    us_ids = getattr(bc, "user_story_ids", []) or []
            except Exception:
                us_ids = getattr(bc, "user_story_ids", []) or []
            
            bc_summary.append({
                "name": getattr(bc, "name", "unknown"),
                "user_story_count": len(us_ids) if isinstance(us_ids, list) else 0,
                "has_user_stories": len(us_ids) > 0 if isinstance(us_ids, list) else False
            })
        
        yield ProgressEvent(
            phase=IngestionPhase.IDENTIFYING_BC,
            message=f"BC 생성 준비: {len(bc_candidates)}개 BC, 총 {sum(s['user_story_count'] for s in bc_summary)}개 User Story 할당",
            progress=PHASE_END - 1,
            data={
                "bc_summary": bc_summary,
                "total_bcs": len(bc_candidates),
                "total_user_stories": sum(s['user_story_count'] for s in bc_summary),
            },
        )
        
        total_bcs = len(bc_candidates)
        tasks = []
        for bc_idx, bc in enumerate(bc_candidates):
            bc_name = getattr(bc, "name", "unknown")
            # BC 객체의 user_story_ids를 다시 확인하여 최신 값 사용
            # Pydantic 모델의 경우 model_dump 우선 사용
            us_ids = []
            try:
                # 방법 1: Pydantic model_dump 사용 (가장 안전)
                if hasattr(bc, "model_dump"):
                    bc_dict = bc.model_dump()
                    us_ids = bc_dict.get("user_story_ids", [])
                elif hasattr(bc, "dict"):
                    bc_dict = bc.dict()
                    us_ids = bc_dict.get("user_story_ids", [])
                # 방법 2: dict 접근
                elif isinstance(bc, dict):
                    us_ids = bc.get("user_story_ids", [])
                # 방법 3: 직접 속성 접근 (fallback)
                else:
                    us_ids = getattr(bc, "user_story_ids", None)
                    if us_ids is None:
                        us_ids = []
            except Exception as e:
                SmartLogger.log(
                    "WARN",
                    f"Failed to get user_story_ids from BC {getattr(bc, 'name', 'unknown')} before linking: {e}",
                    category="ingestion.workflow.bc.pre_link_get_error",
                    params={
                        "session_id": ctx.session.id,
                        "bc_name": getattr(bc, "name", "unknown"),
                        "error": str(e),
                    },
                )
            
            if not isinstance(us_ids, list):
                us_ids = []
            us_ids = [us_id for us_id in us_ids if us_id]  # None이나 빈 문자열 제거
            
            # 상세 디버깅 로그: BC 객체의 모든 속성 확인
            bc_debug_info = {
                "bc_name": getattr(bc, "name", "unknown"),
                "bc_type": type(bc).__name__,
                "has_user_story_ids_attr": hasattr(bc, "user_story_ids"),
                "user_story_ids_from_model_dump": None,
                "user_story_ids_from_getattr": None,
                "user_story_ids_final": us_ids,
            }
            
            # model_dump로 확인
            try:
                if hasattr(bc, "model_dump"):
                    bc_dict = bc.model_dump()
                    bc_debug_info["user_story_ids_from_model_dump"] = bc_dict.get("user_story_ids", [])
            except Exception:
                pass
            
            # getattr로 확인
            try:
                bc_debug_info["user_story_ids_from_getattr"] = getattr(bc, "user_story_ids", None)
            except Exception:
                pass
            
            if us_ids:
                SmartLogger.log(
                    "INFO",
                    f"BC {bc.name} will link {len(us_ids)} User Stories: {us_ids}",
                    category="ingestion.workflow.bc.pre_link_check",
                    params={
                        "session_id": ctx.session.id,
                        "bc_name": bc.name,
                        "user_story_ids": us_ids,
                        "user_story_count": len(us_ids),
                        "debug_info": bc_debug_info,
                    },
                )
            else:
                SmartLogger.log(
                    "ERROR",
                    f"BC {bc.name} has NO user_story_ids - will skip linking. Debug info: {bc_debug_info}",
                    category="ingestion.workflow.bc.no_user_stories_pre_link",
                    params={
                        "session_id": ctx.session.id,
                        "bc_name": bc.name,
                        "bc_type": type(bc).__name__,
                        "debug_info": bc_debug_info,
                        "bc_attrs": [attr for attr in dir(bc) if not attr.startswith("_")][:30],
                    },
                )
            tasks.append(_create_bc_with_links(bc, bc_idx, total_bcs, ctx))
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Process results and yield progress events
        for bc_idx, result in enumerate(results):
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
                    f"Bounded context creation exception: {result}",
                    category="ingestion.neo4j.bounded_context.create.error",
                    params={"session_id": ctx.session.id, "bc_index": bc_idx + 1, "error": str(result)}
                )
                continue
            
            created_bc_data, progress_events, error = result
            if error:
                SmartLogger.log(
                    "ERROR",
                    f"Bounded context creation failed: {error}",
                    category="ingestion.workflow.bc.skip",
                    params={"session_id": ctx.session.id, "bc_index": bc_idx + 1, "error": error}
                )
                continue
            
            if created_bc_data and progress_events:
                for progress_event in progress_events:
                    yield progress_event
                
                # BC 생성 및 연결 결과 요약 로깅
                if created_bc_data:
                    linked_count = created_bc_data.get("linked_count", 0)
                    failed_count = created_bc_data.get("failed_count", 0)
                    skipped_count = created_bc_data.get("skipped_count", 0)
                    bc_name = created_bc_data.get("bc", {}).get("name") if isinstance(created_bc_data.get("bc"), dict) else getattr(created_bc_data.get("bc"), "name", "unknown")
                    
                    if linked_count > 0 or failed_count > 0 or skipped_count > 0:
                        yield ProgressEvent(
                            phase=IngestionPhase.IDENTIFYING_BC,
                            message=f"BC {bc_name}: {linked_count}개 User Story 연결 완료 ({failed_count}개 실패, {skipped_count}개 스킵)",
                            progress=PHASE_END - 1,
                            data={
                                "type": "BoundedContext",
                                "bc_name": bc_name,
                                "linked_count": linked_count,
                                "failed_count": failed_count,
                                "skipped_count": skipped_count,
                            },
                        )
    
    # 모든 BC 생성 및 연결 완료 후, 여전히 unassigned 상태인 User Story 확인
    with ctx.client.session() as session:
        # Neo4j에서 실제로 BC에 연결되지 않은 User Story 조회
        unassigned_query = """
        MATCH (us:UserStory)
        WHERE NOT (us)-[:IMPLEMENTS]->(:BoundedContext)
        RETURN us.id as id, us.role as role, us.action as action
        """
        unassigned_result = session.run(unassigned_query)
        remaining_unassigned = [{"id": r["id"], "role": r.get("role"), "action": r.get("action")} for r in unassigned_result]
        
        if remaining_unassigned:
            SmartLogger.log(
                "WARN",
                f"Found {len(remaining_unassigned)} User Stories still unassigned after all BC links",
                category="ingestion.workflow.bc.remaining_unassigned",
                params={
                    "session_id": ctx.session.id,
                    "unassigned_count": len(remaining_unassigned),
                    "unassigned_ids": [us["id"] for us in remaining_unassigned],
                },
            )
            # 각 unassigned User Story를 가장 적절한 BC에 자동 할당 시도
            for us_info in remaining_unassigned:
                us_id = us_info["id"]
                # 모든 BC를 조회하여 가장 적절한 BC 찾기
                bc_query = """
                MATCH (bc:BoundedContext)
                RETURN bc.id as id, bc.name as name, bc.description as description
                ORDER BY bc.name
                """
                bc_result = session.run(bc_query)
                all_bcs = [{"id": r["id"], "name": r["name"], "description": r.get("description", "")} for r in bc_result]
                
                if all_bcs:
                    # 첫 번째 BC에 임시로 할당 (나중에 사용자가 수동으로 변경 가능)
                    # 또는 가장 적절한 BC를 찾는 로직을 추가할 수 있음
                    target_bc = all_bcs[0]  # 임시로 첫 번째 BC 선택
                    try:
                        link_result = ctx.client.link_user_story_to_bc(us_id, target_bc["id"])
                        if isinstance(link_result, tuple):
                            link_success, _ = link_result
                        else:
                            link_success = link_result
                        
                        if link_success:
                            pass  # Auto-assignment successful
                    except Exception as final_link_error:
                        SmartLogger.log(
                            "WARN",
                            f"Failed to auto-assign remaining unassigned User Story {us_id}: {final_link_error}",
                            category="ingestion.workflow.bc.final_auto_assign_failed",
                            params={
                                "session_id": ctx.session.id,
                                "user_story_id": us_id,
                                "error": str(final_link_error),
                            },
                        )
        else:
            pass  # No remaining unassigned user stories
    
    # BC ↔ Event 직접 연결: US -[:IMPLEMENTS]-> BC + US -[:HAS_EVENT]-> Event 경로로 매핑
    try:
        with ctx.client.session() as session:
            # 1. HAS_EVENT 관계 생성
            session.run("""
                MATCH (us:UserStory)-[:IMPLEMENTS]->(bc:BoundedContext)
                MATCH (us)-[:HAS_EVENT]->(evt:Event)
                MERGE (bc)-[:HAS_EVENT]->(evt)
            """)

            # 2. 매핑 결과 조회하여 SSE로 전달
            mapping_result = session.run("""
                MATCH (bc:BoundedContext)-[:HAS_EVENT]->(evt:Event)
                RETURN bc.id AS bcId, bc.name AS bcName,
                       evt.id AS evtId, evt.name AS evtName, evt.sequence AS evtSeq
            """)
            bc_event_map = {}
            for r in mapping_result:
                bc_id = r["bcId"]
                if bc_id not in bc_event_map:
                    bc_event_map[bc_id] = {"bcName": r["bcName"], "events": []}
                bc_event_map[bc_id]["events"].append({
                    "id": r["evtId"], "name": r["evtName"], "sequence": r["evtSeq"],
                })

            total_linked = sum(len(v["events"]) for v in bc_event_map.values())
            if total_linked > 0:
                SmartLogger.log(
                    "INFO",
                    f"Linked {total_linked} Event(s) to {len(bc_event_map)} BC(s)",
                    category="ingestion.workflow.bc.event_link",
                    params={"session_id": ctx.session.id, "linked": total_linked},
                )
                # SSE: BC별 Event 매핑 알림
                for bc_id, info in bc_event_map.items():
                    for evt in info["events"]:
                        yield ProgressEvent(
                            phase=IngestionPhase.IDENTIFYING_BC,
                            message=f"Event → BC: {evt['name']} → {info['bcName']}",
                            progress=PHASE_END - 1,
                            data={
                                "type": "EventBCAssigned",
                                "object": {
                                    "eventId": evt["id"],
                                    "eventName": evt["name"],
                                    "bcId": bc_id,
                                    "bcName": info["bcName"],
                                    "sequence": evt.get("sequence"),
                                },
                            },
                        )
    except Exception as e:
        SmartLogger.log(
            "WARN",
            f"BC-Event linking failed: {e}",
            category="ingestion.workflow.bc.event_link.error",
            params={"session_id": ctx.session.id, "error": str(e)},
        )

    # Phase 완료
    yield ProgressEvent(
        phase=IngestionPhase.IDENTIFYING_BC,
        message=f"Bounded Context 식별 완료",
        progress=PHASE_END,
    )


