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
from api.platform.env import get_llm_provider_model
from api.platform.observability.request_logging import summarize_for_log
from api.platform.observability.smart_logger import SmartLogger


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
    domain_type = getattr(bc, "domain_type", None)
    
    try:
        created_bc = await asyncio.wait_for(
            asyncio.to_thread(
                ctx.client.create_bounded_context,
                name=bc.name,
                description=bc.description,
                domain_type=domain_type
            ),
            timeout=10.0
        )
        
        # Overwrite LLM-proposed id with UUID from DB (canonical)
        try:
            bc.id = created_bc.get("id")
        except Exception:
            pass
        # Preserve natural key (helps downstream property generation prompts)
        try:
            bc.key = created_bc.get("key")
        except Exception:
            pass
        
        PHASE_END = 30
        progress_events = []
        
        # BC 생성 이벤트
        progress_events.append(ProgressEvent(
            phase=IngestionPhase.IDENTIFYING_BC,
            message=f"Bounded Context 생성: {bc.name}",
            progress=PHASE_END - 2 + int((2 * bc_idx / max(total_bcs, 1))),
            data={
                "type": "BoundedContext",
                "object": {
                    "id": created_bc.get("id"),
                    "name": bc.name,
                    "type": "BoundedContext",
                    "description": bc.description,
                    "userStoryIds": bc.user_story_ids,
                },
            },
        ))
        
        # User Story 링크 처리 (배치 처리)
        linked_count = 0
        failed_count = 0
        skipped_count = 0
        failed_us_ids = []
        skipped_us_ids = []
        
        us_ids = getattr(bc, "user_story_ids", []) or []
        if us_ids:
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
                        await link_task
                        linked_count += 1
                    except asyncio.TimeoutError:
                        failed_count += 1
                        failed_us_ids.append(us_id)
                    except Exception as e:
                        # User Story가 ctx에 없거나 Neo4j에 없는 경우
                        us_in_ctx = next((us for us in ctx.user_stories if us.id == us_id), None)
                        if not us_in_ctx:
                            skipped_count += 1
                            skipped_us_ids.append(us_id)
                        else:
                            failed_count += 1
                            failed_us_ids.append(us_id)
        
        return {
            "bounded_context": created_bc,
            "bc": bc,
            "linked_count": linked_count,
            "failed_count": failed_count,
            "skipped_count": skipped_count,
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
                "bc_name": bc.name,
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
    
    # User Stories를 텍스트로 변환하는 함수
    def us_to_text(us) -> str:
        # Ensure role is valid before formatting
        role = (getattr(us, "role", "") or "").strip()
        if not role or role.lower() in ("user", "사용자", ""):
            # Fallback to "customer" if role is still invalid
            role = "customer"
        return f"[{us.id}] As a {role}, I want to {us.action}, so that {us.benefit}"
    
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
            prompt = IDENTIFY_BC_FROM_STORIES_PROMPT.format(user_stories=stories_text_with_ids)
            
            t_llm0 = time.perf_counter()
            bc_response = await asyncio.to_thread(
                structured_llm.invoke,
                [SystemMessage(content=SYSTEM_PROMPT), HumanMessage(content=prompt)]
            )
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
            
            # 청크 내 모든 User Story가 할당되었는지 검증
            chunk_assigned_us_ids = set()
            for bc in bcs:
                chunk_assigned_us_ids.update(getattr(bc, "user_story_ids", []) or [])
            chunk_us_ids = {us.id for us in story_chunk}
            chunk_unassigned = chunk_us_ids - chunk_assigned_us_ids
            
            if chunk_unassigned:
                # 누락된 User Story를 LLM에게 다시 할당 요청
                unassigned_stories = [us for us in story_chunk if us.id in chunk_unassigned]
                unassigned_text = "\n".join([us_to_text(us) for us in unassigned_stories])
                existing_bcs_text = "\n".join([
                    f"- {bc.name}: {bc.description} (Current user_story_ids: {', '.join(getattr(bc, 'user_story_ids', []) or [])})"
                    for bc in bcs
                ])
                
                fix_prompt = f"""The following User Stories from the previous analysis were NOT assigned to any Bounded Context. You MUST assign each of them to the most appropriate existing BC.

Existing Bounded Contexts:
{existing_bcs_text}

Unassigned User Stories (MUST be assigned):
{unassigned_text}

For each unassigned User Story, determine which existing Bounded Context it best fits and add its ID to that BC's user_story_ids list. If no existing BC is appropriate, create a new BC.

CRITICAL: Every User Story listed above MUST be assigned to exactly ONE BC. Return the complete updated list of BoundedContextCandidate objects with all User Stories assigned."""
                
                fix_response = await asyncio.to_thread(
                    structured_llm.invoke,
                    [SystemMessage(content=SYSTEM_PROMPT), HumanMessage(content=fix_prompt)]
                )
                fixed_bcs = getattr(fix_response, "bounded_contexts", []) or []
                
                # 수정된 BC로 교체
                if fixed_bcs:
                    bcs = fixed_bcs
            
            chunk_results.append(bcs)
            
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
        prompt = IDENTIFY_BC_FROM_STORIES_PROMPT.format(user_stories=stories_text_with_ids)

        bc_response = await asyncio.to_thread(
            structured_llm.invoke,
            [SystemMessage(content=SYSTEM_PROMPT), HumanMessage(content=prompt)]
        )

        bc_candidates = bc_response.bounded_contexts
        ctx.bounded_contexts = bc_candidates
        
        yield ProgressEvent(
            phase=IngestionPhase.IDENTIFYING_BC,
            message=f"Bounded Context 식별 완료 (총 {len(bc_candidates)}개)",
            progress=PHASE_END - 2
        )

    # bc_candidates는 위에서 ctx.bounded_contexts에 저장됨
    bc_candidates = ctx.bounded_contexts
    
    # BC 후보의 user_story_ids 검증: 존재하지 않는 ID 제거 및 중복 할당 방지
    valid_us_ids = {us.id for us in ctx.user_stories}
    us_to_bc_map: dict[str, str] = {}  # User Story ID -> BC 이름 (중복 할당 추적)
    
    for bc in bc_candidates:
        original_ids = getattr(bc, "user_story_ids", []) or []
        # 존재하는 User Story ID만 필터링
        valid_ids = [us_id for us_id in original_ids if us_id in valid_us_ids]
        invalid_ids = [us_id for us_id in original_ids if us_id not in valid_us_ids]
        
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
        
        # BC 객체 업데이트 (리스트에도 반영되도록)
        updated_bc = None
        try:
            setattr(bc, "user_story_ids", final_ids)
            updated_bc = bc
        except Exception:
            # Pydantic model인 경우 model_copy 사용
            try:
                if hasattr(bc, "model_copy"):
                    updated_bc = bc.model_copy(update={"user_story_ids": final_ids})
                elif hasattr(bc, "copy"):
                    updated_bc = bc.copy(update={"user_story_ids": final_ids})
                else:
                    updated_bc = bc
            except Exception:
                updated_bc = bc
        
        # 리스트에 업데이트된 BC 객체 반영
        if updated_bc is not None and updated_bc is not bc:
            bc_idx_in_list = bc_candidates.index(bc) if bc in bc_candidates else -1
            if bc_idx_in_list >= 0:
                bc_candidates[bc_idx_in_list] = updated_bc
                bc = updated_bc
    
    # 검증 후 빈 user_story_ids를 가진 BC 제거 (BC는 최소 하나의 User Story를 가져야 함)
    bc_candidates_with_stories = []
    empty_bcs = []
    for bc in bc_candidates:
        final_ids = getattr(bc, "user_story_ids", []) or []
        if not final_ids:
            empty_bcs.append(bc.name)
        else:
            bc_candidates_with_stories.append(bc)
    
    # 빈 BC 제거 후 업데이트
    bc_candidates = bc_candidates_with_stories
    ctx.bounded_contexts = bc_candidates

    # 누락된 User Story 확인 및 자동 할당
    all_assigned_us_ids = set()
    for bc in bc_candidates:
        all_assigned_us_ids.update(getattr(bc, "user_story_ids", []) or [])
    
    all_us_ids = {us.id for us in ctx.user_stories}
    unassigned_us_ids = all_us_ids - all_assigned_us_ids
    
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
            [
                f"[{us.id}] As a {getattr(us, 'role', 'user')}, I want to {getattr(us, 'action', '?')}"
                + (f", so that {getattr(us, 'benefit', '')}" if getattr(us, "benefit", None) else "")
                for us in unassigned_stories
            ]
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
            response = await asyncio.to_thread(
                llm.invoke,
                [SystemMessage(content=SYSTEM_PROMPT), HumanMessage(content=assignment_prompt)]
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
                            try:
                                setattr(target_bc, "user_story_ids", current_ids)
                            except Exception:
                                # Pydantic model인 경우
                                if hasattr(target_bc, "model_copy"):
                                    target_bc = target_bc.model_copy(update={"user_story_ids": current_ids})
                                    bc_candidates[bc_idx] = target_bc
                                elif hasattr(target_bc, "copy"):
                                    target_bc = target_bc.copy(update={"user_story_ids": current_ids})
                                    bc_candidates[bc_idx] = target_bc
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
    
    # 생성 결과 요약
    SmartLogger.log(
        "INFO",
        f"Bounded contexts identified: {len(bc_candidates)} BCs created",
        category="ingestion.workflow.bc.summary",
        params={
            "session_id": ctx.session.id,
            "bc_count": len(bc_candidates),
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
        
        total_bcs = len(bc_candidates)
        tasks = []
        for bc_idx, bc in enumerate(bc_candidates):
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
    
    # Phase 완료
    yield ProgressEvent(
        phase=IngestionPhase.IDENTIFYING_BC,
        message=f"Bounded Context 식별 완료",
        progress=PHASE_END,
    )


