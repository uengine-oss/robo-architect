from __future__ import annotations

import asyncio
from typing import AsyncGenerator

from api.features.ingestion.ingestion_contracts import IngestionPhase, ProgressEvent
from api.features.ingestion.requirements_to_user_stories import (
    ensure_nonempty_ui_description,
    extract_user_stories_from_text,
)
from api.features.ingestion.workflow.ingestion_workflow_context import IngestionWorkflowContext
from api.features.ingestion.workflow.utils.chunking import (
    should_chunk,
    split_text_with_overlap,
    merge_chunk_results,
    calculate_chunk_progress,
)
from api.platform.observability.smart_logger import SmartLogger


async def _create_user_story_with_verification(
    us: Any,
    us_idx: int,
    total_us: int,
    ctx: IngestionWorkflowContext,
) -> tuple[dict[str, Any] | None, ProgressEvent | None, str]:
    """
    Create a single user story with verification.
    Returns (created_user_story_dict, progress_event, error_message)
    """
    # Final validation: ensure role is not empty or generic
    role = getattr(us, "role", "") or ""
    action = getattr(us, "action", "") or ""
    
    # Strip and validate
    role = role.strip()
    action = action.strip()
    
    # If role is still empty or generic, try to infer or use fallback
    if not role or role.lower() in ("user", "사용자", ""):
        from api.features.ingestion.requirements_to_user_stories import _infer_role_from_context
        benefit = getattr(us, "benefit", "") or ""
        inferred_role = _infer_role_from_context(action, benefit)
        role = inferred_role if inferred_role else "customer"
        # Update the user story object
        try:
            setattr(us, "role", role)
        except Exception:
            pass
    
    # Skip if action is still empty
    if not action:
        return None, None, "User story action is empty"
    
    ui_desc = ensure_nonempty_ui_description(
        role,
        action,
        getattr(us, "benefit", None),
        getattr(us, "ui_description", None),
    )
    
    try:
        # User Story 생성
        result = await asyncio.wait_for(
            asyncio.to_thread(
                ctx.client.create_user_story,
                id=us.id,
                role=role,
                action=action,
                benefit=getattr(us, "benefit", None),
                priority=getattr(us, "priority", "medium"),
                status="draft",
                ui_description=ui_desc,
            ),
            timeout=10.0
        )
        
        # 생성 결과 검증
        if not result or not result.get("id"):
            return None, None, f"create_user_story returned empty result for {us.id}"
        
        # 실제로 DB에 저장되었는지 확인
        with ctx.client.session() as verify_session:
            verify_result = verify_session.run(
                "MATCH (us:UserStory {id: $id}) RETURN us.id as id",
                id=us.id
            )
            verify_record = verify_result.single()
            if not verify_record:
                return None, None, f"User Story {us.id} was not found in Neo4j after creation"
        
        PHASE_END = 20
        progress_event = ProgressEvent(
            phase=IngestionPhase.EXTRACTING_USER_STORIES,
            message=f"User Story 생성: ({us_idx + 1}/{total_us})",
            progress=PHASE_END - 2 + int((2 * (us_idx + 1) / max(total_us, 1))),
            data={
                "type": "UserStory",
                "object": {
                    "id": us.id,
                    "name": f"{role}: {action[:30]}...",
                    "type": "UserStory",
                    "role": role,
                    "action": action,
                    "benefit": getattr(us, "benefit", None),
                    "priority": getattr(us, "priority", "medium"),
                    "ui_description": ui_desc,
                },
            },
        )
        
        return {
            "user_story": result,
            "us": us,
        }, progress_event, None
    except asyncio.TimeoutError:
        return None, None, "User story creation timeout"
    except Exception as e:
        SmartLogger.log(
            "ERROR",
            "User story create failed",
            category="ingestion.neo4j.user_story.create_failed",
            params={
                "session_id": ctx.session.id,
                "id": us.id,
                "role": role,
                "action": action,
                "error": str(e),
                "error_type": type(e).__name__,
            },
        )
        return None, None, f"User story creation failed: {e}"


async def extract_user_stories_phase(ctx: IngestionWorkflowContext) -> AsyncGenerator[ProgressEvent, None]:
    """
    Phase 2: extract user stories and persist them to Neo4j.
    Supports chunking for large requirements documents.
    """
    PHASE_START = 10
    PHASE_END = 20
    MERGE_RATIO = 0.1  # 병합 작업이 10% 차지
    
    # Phase 시작
    yield ProgressEvent(
        phase=IngestionPhase.EXTRACTING_USER_STORIES,
        message="User Story 추출 시작...",
        progress=PHASE_START
    )
    
    # 스캐닝 및 청킹 판단
    if should_chunk(ctx.content):
        yield ProgressEvent(
            phase=IngestionPhase.EXTRACTING_USER_STORIES,
            message="대용량 요구사항 스캐닝 중...",
            progress=PHASE_START + 1
        )
        
        chunks = split_text_with_overlap(ctx.content)
        total_chunks = len(chunks)
        
        yield ProgressEvent(
            phase=IngestionPhase.EXTRACTING_USER_STORIES,
            message=f"요구사항을 {total_chunks}개 청크로 분할 완료",
            progress=PHASE_START + 2
        )
        
        chunk_results = []
        processing_range = (PHASE_END - PHASE_START - 2) * (1 - MERGE_RATIO)
        
        for i, (chunk_text, start_char, end_char) in enumerate(chunks):
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
                merge_progress_ratio=0  # 청크 처리 중에는 merge 비율 제외
            )
            yield ProgressEvent(
                phase=IngestionPhase.EXTRACTING_USER_STORIES,
                message=f"청크 {i+1}/{total_chunks} 처리 중... ({start_char:,}~{end_char:,} 문자)",
                progress=chunk_progress
            )
            
            # 청크별 User Story 추출 (동기 함수를 비동기로 실행)
            # Note: asyncio.to_thread cannot be cancelled, but we check before and after
            stories = await asyncio.to_thread(extract_user_stories_from_text, chunk_text)
            
            # 각 청크의 User Story ID에 청크 번호를 포함시켜 고유성 보장
            # 예: US-001 -> US-1-001, US-2-001 등
            for story in stories:
                original_id = getattr(story, "id", None)
                if original_id and original_id.startswith("US-"):
                    # US-001 형식인 경우 청크 번호 추가
                    try:
                        # US-001 -> US-1-001
                        chunk_prefix = f"US-{i+1}-"
                        if "-" in original_id[3:]:  # 이미 청크 번호가 있는 경우 (US-1-001)
                            # 이미 처리된 경우 다음 story로
                            continue
                        number_part = original_id[3:]  # "001"
                        new_id = f"{chunk_prefix}{number_part}"
                        try:
                            setattr(story, "id", new_id)
                        except Exception:
                            # Pydantic model인 경우
                            if hasattr(story, "model_copy"):
                                story = story.model_copy(update={"id": new_id})
                            elif hasattr(story, "copy"):
                                story = story.copy(update={"id": new_id})
                    except Exception:
                        pass  # ID 업데이트 실패해도 story는 유지
            
            # Check cancellation after chunk processing
            if getattr(ctx.session, "is_cancelled", False):
                yield ProgressEvent(
                    phase=IngestionPhase.ERROR,
                    message="❌ 생성이 중단되었습니다",
                    progress=getattr(ctx.session, "progress", 0) or 0,
                    data={"error": "Cancelled by user", "cancelled": True},
                )
                return
            
            chunk_results.append(stories)
            
            # 청크 처리 완료
            chunk_complete_progress = calculate_chunk_progress(
                PHASE_START + 2,
                PHASE_END - int((PHASE_END - PHASE_START) * MERGE_RATIO),
                i + 1,
                total_chunks,
                merge_progress_ratio=0
            )
            yield ProgressEvent(
                phase=IngestionPhase.EXTRACTING_USER_STORIES,
                message=f"청크 {i+1}/{total_chunks} 완료 ({len(stories)}개 User Story 추출)",
                progress=chunk_complete_progress
            )
        
        # 결과 병합 시작
        yield ProgressEvent(
            phase=IngestionPhase.EXTRACTING_USER_STORIES,
            message=f"{total_chunks}개 청크 결과 병합 중...",
            progress=PHASE_END - 3
        )
        
        # 결과 병합 (내용 기반 중복 제거만 수행)
        # 각 청크에서 추출된 User Story들은 이미 청크 번호가 포함된 고유 ID를 가지고 있음
        all_stories = []
        for results in chunk_results:
            all_stories.extend(results)
        
        # 내용 기반 중복 제거 (role:action:benefit 조합)
        # 같은 내용의 User Story는 하나만 유지 (ID는 나중에 순차적으로 재생성)
        seen_content = set()
        deduplicated_by_content = []
        
        for us in all_stories:
            role = (getattr(us, "role", "") or "").strip()
            action = (getattr(us, "action", "") or "").strip()
            benefit = (getattr(us, "benefit", "") or "").strip()
            
            # action이 비어있으면 스킵 (유효하지 않은 User Story)
            if not action:
                continue
            
            content_key = f"{role}:{action}:{benefit}"
            if content_key not in seen_content:
                seen_content.add(content_key)
                deduplicated_by_content.append(us)
        
        # 병합 후 순차적인 ID로 재생성 (US-001, US-002, ...)
        for idx, us in enumerate(deduplicated_by_content, start=1):
            new_id = f"US-{idx:03d}"  # US-001, US-002, ...
            try:
                setattr(us, "id", new_id)
            except Exception:
                if hasattr(us, "model_copy"):
                    us = us.model_copy(update={"id": new_id})
                    deduplicated_by_content[idx - 1] = us
                elif hasattr(us, "copy"):
                    us = us.copy(update={"id": new_id})
                    deduplicated_by_content[idx - 1] = us
        
        user_stories = deduplicated_by_content
        
        # 병합 후 role 재검증 (청킹 처리 중 일부 role이 제대로 추론되지 않았을 수 있음)
        from api.features.ingestion.requirements_to_user_stories import _infer_role_from_context
        validated_stories = []
        for us in user_stories:
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
                        except Exception:
                            pass
            
            # Skip if action is still empty
            if not action:
                continue
            
            validated_stories.append(us)
        
        ctx.user_stories = validated_stories
        
        # 결과 병합 완료
        yield ProgressEvent(
            phase=IngestionPhase.EXTRACTING_USER_STORIES,
            message=f"User Story 추출 완료 (총 {len(user_stories)}개)",
            progress=PHASE_END - 2
        )
    else:
        # 기존 로직 (청킹 불필요)
        yield ProgressEvent(
            phase=IngestionPhase.EXTRACTING_USER_STORIES,
            message="User Story 추출 중...",
            progress=PHASE_START + 5
        )
        
        user_stories = await asyncio.to_thread(extract_user_stories_from_text, ctx.content)
        ctx.user_stories = user_stories
        
        yield ProgressEvent(
            phase=IngestionPhase.EXTRACTING_USER_STORIES,
            message=f"User Story 추출 완료 (총 {len(user_stories)}개)",
            progress=PHASE_END - 2
        )

    # Neo4j에 User Story 저장 - 병렬 처리
    created_count = 0
    skipped_count = 0
    failed_count = 0
    skipped_ids = []
    failed_ids = []
    
    # 병합이 완료되었으므로 ctx.user_stories는 이미 내용 기반으로 중복 제거되고 순차적인 ID가 부여된 상태
    
    if ctx.user_stories:
        # Check cancellation before parallel processing
        if getattr(ctx.session, "is_cancelled", False):
            yield ProgressEvent(
                phase=IngestionPhase.ERROR,
                message="❌ 생성이 중단되었습니다",
                progress=getattr(ctx.session, "progress", 0) or 0,
                data={"error": "Cancelled by user", "cancelled": True},
            )
            return
        
        total_us = len(ctx.user_stories)
        tasks = []
        for us_idx, us in enumerate(ctx.user_stories):
            tasks.append(_create_user_story_with_verification(us, us_idx, total_us, ctx))
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Process results and yield progress events
        for us_idx, result in enumerate(results):
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
                failed_count += 1
                failed_ids.append(ctx.user_stories[us_idx].id)
                SmartLogger.log(
                    "ERROR",
                    f"User story creation exception: {result}",
                    category="ingestion.neo4j.user_story.create.error",
                    params={"session_id": ctx.session.id, "user_story_index": us_idx + 1, "error": str(result)}
                )
                continue
            
            created_us_data, progress_event, error = result
            if error:
                if "action is empty" in error:
                    skipped_count += 1
                    skipped_ids.append(ctx.user_stories[us_idx].id)
                else:
                    failed_count += 1
                    failed_ids.append(ctx.user_stories[us_idx].id)
                    SmartLogger.log(
                        "ERROR",
                        f"User story creation failed: {error}",
                        category="ingestion.workflow.user_stories.skip",
                        params={"session_id": ctx.session.id, "user_story_index": us_idx + 1, "error": error}
                    )
                continue
            
            if created_us_data and progress_event:
                created_count += 1
                yield progress_event
    
    # 생성 결과 요약 로그
    SmartLogger.log(
        "INFO",
        f"User Story creation completed: {created_count} created, {skipped_count} skipped, {failed_count} failed",
        category="ingestion.user_stories.creation_summary",
        params={
            "session_id": ctx.session.id,
            "total": len(ctx.user_stories),
            "created_count": created_count,
            "skipped_count": skipped_count,
            "failed_count": failed_count,
            "skipped_ids": skipped_ids,
            "failed_ids": failed_ids,
        },
    )

    # 최종 결과에 생성 성공/실패 정보 포함
    yield ProgressEvent(
        phase=IngestionPhase.EXTRACTING_USER_STORIES,
        message=f"User Story 추출 완료: {created_count}개 생성됨 (총 {len(ctx.user_stories)}개 중 {skipped_count}개 스킵, {failed_count}개 실패)",
        progress=PHASE_END,
        data={
            "count": len(ctx.user_stories),
            "created_count": created_count,
            "skipped_count": skipped_count,
            "failed_count": failed_count,
            "skipped_ids": skipped_ids,
            "failed_ids": failed_ids,
            "items": [{"id": us.id, "role": us.role, "action": us.action[:50]} for us in ctx.user_stories],
        },
    )


