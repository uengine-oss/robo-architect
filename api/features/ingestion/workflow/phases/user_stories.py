from __future__ import annotations

import asyncio
from typing import Any, AsyncGenerator

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
    estimate_tokens,
    USER_STORY_CHUNK_SIZE,
    USER_STORY_CHUNK_OVERLAP_RATIO,
)
from api.features.ingestion.workflow.utils.user_story_normalize import (
    dedup_key,
    canonicalize_role,
    canonicalize_action,
)
from api.platform.observability.smart_logger import SmartLogger


def normalize_and_dedup_user_stories(stories: list[Any], session_id: str) -> list[Any]:
    """
    User Story 목록을 정규화하고 중복을 제거합니다.
    청킹 여부와 무관하게 항상 적용되어야 합니다.
    """
    seen = set()
    out = []

    for us in stories:
        role = (getattr(us, "role", "") or "").strip()
        action = (getattr(us, "action", "") or "").strip()
        benefit = (getattr(us, "benefit", "") or "").strip()

        if not action:
            continue

        key = dedup_key(role, action, benefit)
        if key in seen:
            continue
        seen.add(key)

        # 저장용 표준화
        role_c = canonicalize_role(role)
        action_c = canonicalize_action(action)

        try:
            setattr(us, "role", role_c)
            setattr(us, "action", action_c)
        except Exception:
            if hasattr(us, "model_copy"):
                us = us.model_copy(update={"role": role_c, "action": action_c})
            elif hasattr(us, "copy"):
                us = us.copy(update={"role": role_c, "action": action_c})

        out.append(us)

    SmartLogger.log(
        "INFO",
        "User story normalize+dedup summary",
        category="ingestion.user_stories.dedup.summary",
        params={
            "session_id": session_id,
            "raw_story_count": len(stories),
            "dedup_story_count": len(out),
            "dedup_ratio": round(len(out) / max(len(stories), 1), 4),
        },
    )
    return out


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
    
    # 정규화 적용 (안전장치)
    role = canonicalize_role(role)
    action = canonicalize_action(action)
    
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


async def _process_chunk_with_retry(
    chunk_text: str,
    chunk_idx: int,
    total_chunks: int,
    start_char: int,
    end_char: int,
    semaphore: asyncio.Semaphore,
    max_retries: int = 2,
) -> tuple[list[Any], int]:
    """
    청크를 처리하고 실패 시 재시도합니다.
    실패 시 청크를 반으로 분할하여 재시도합니다 (최대 2회).
    
    Args:
        chunk_text: 처리할 청크 텍스트
        chunk_idx: 청크 인덱스
        total_chunks: 전체 청크 수
        start_char: 시작 문자 위치
        end_char: 끝 문자 위치
        semaphore: 동시 실행 제어용 세마포어
        max_retries: 최대 재시도 횟수
    
    Returns:
        (stories, retry_count): 추출된 User Story 리스트와 재시도 횟수
    """
    async with semaphore:
        retry_count = 0
        current_text = chunk_text
        all_stories = []
        
        while retry_count <= max_retries:
            try:
                stories = await asyncio.to_thread(extract_user_stories_from_text, current_text)
                all_stories.extend(stories)
                
                # 성공: 재시도 없이 완료된 경우
                if retry_count == 0:
                    return all_stories, 0
                
                # 재시도 후 성공: 나머지 부분도 처리해야 함
                # 하지만 현재는 첫 번째 절반만 처리하고 반환
                # (전체 청크를 재분할하는 것은 복잡하므로 현재 구현에서는 첫 절반만 반환)
                return all_stories, retry_count
                
            except Exception as e:
                retry_count += 1
                
                if retry_count > max_retries:
                    # 최대 재시도 횟수 초과
                    SmartLogger.log(
                        "ERROR",
                        f"Chunk {chunk_idx + 1} failed after {max_retries} retries",
                        category="ingestion.user_stories.chunk.failed",
                        params={
                            "chunk_idx": chunk_idx + 1,
                            "total_chunks": total_chunks,
                            "retry_count": retry_count - 1,
                            "error": str(e),
                            "error_type": type(e).__name__,
                        },
                    )
                    # 지금까지 수집한 stories 반환 (있으면)
                    return all_stories, retry_count - 1
                
                # 청크를 반으로 분할하여 재시도
                text_length = len(current_text)
                
                # 문단 경계에서 분할 (가능한 경우)
                if "\n\n" in current_text:
                    paragraphs = current_text.split("\n\n")
                    mid_point = len(paragraphs) // 2
                    if mid_point > 0:
                        # 첫 번째 절반만 사용
                        current_text = "\n\n".join(paragraphs[:mid_point])
                    else:
                        # 문단이 너무 적으면 중간에서 분할
                        current_text = current_text[:text_length // 2]
                else:
                    # 문단 구분자가 없으면 중간에서 분할
                    current_text = current_text[:text_length // 2]
                
                SmartLogger.log(
                    "WARN",
                    f"Chunk {chunk_idx + 1} failed, retrying with split (attempt {retry_count}/{max_retries})",
                    category="ingestion.user_stories.chunk.retry",
                    params={
                        "chunk_idx": chunk_idx + 1,
                        "retry_count": retry_count,
                        "original_size": text_length,
                        "split_size": len(current_text),
                        "error": str(e),
                    },
                )


async def extract_user_stories_phase(ctx: IngestionWorkflowContext) -> AsyncGenerator[ProgressEvent, None]:
    """
    Phase 2: extract user stories and persist them to Neo4j.
    Supports chunking for large requirements documents with parallel processing.
    """
    PHASE_START = 10
    PHASE_END = 20
    MERGE_RATIO = 0.1  # 병합 작업이 10% 차지
    MAX_CONCURRENT_CHUNKS = 4  # 동시 처리 청크 수
    
    # Phase 시작
    yield ProgressEvent(
        phase=IngestionPhase.EXTRACTING_USER_STORIES,
        message="User Story 추출 시작...",
        progress=PHASE_START
    )
    
    # 스캐닝 및 청킹 판단
    if should_chunk(ctx.content, max_tokens=USER_STORY_CHUNK_SIZE):
        yield ProgressEvent(
            phase=IngestionPhase.EXTRACTING_USER_STORIES,
            message="대용량 요구사항 스캐닝 중...",
            progress=PHASE_START + 1
        )
        
        # Overlap 크기 계산 (5%)
        # chunk_size는 토큰 단위이므로, 문자 단위로 변환하여 overlap 계산
        # 대략적으로 1 토큰 ≈ 4 문자 (영어 기준, 한글은 더 작을 수 있음)
        # 안전하게 토큰 수를 직접 추정하여 overlap 계산
        estimated_chunk_tokens = USER_STORY_CHUNK_SIZE
        overlap_tokens = int(estimated_chunk_tokens * USER_STORY_CHUNK_OVERLAP_RATIO)
        # 토큰을 문자로 변환 (보수적으로 1 토큰 = 3 문자로 가정)
        overlap_chars = overlap_tokens * 3
        
        chunks = split_text_with_overlap(
            ctx.content,
            chunk_size=USER_STORY_CHUNK_SIZE,
            overlap_size=overlap_chars
        )
        total_chunks = len(chunks)
        
        yield ProgressEvent(
            phase=IngestionPhase.EXTRACTING_USER_STORIES,
            message=f"요구사항을 {total_chunks}개 청크로 분할 완료 (병렬 처리: 최대 {MAX_CONCURRENT_CHUNKS}개 동시)",
            progress=PHASE_START + 2
        )
        
        # 세마포어로 동시 실행 제어
        semaphore = asyncio.Semaphore(MAX_CONCURRENT_CHUNKS)
        
        # 청크 처리 태스크 생성
        async def process_chunk_task(i: int, chunk_text: str, start_char: int, end_char: int):
            """청크 처리 태스크"""
            # Check cancellation
            if getattr(ctx.session, "is_cancelled", False):
                return i, [], 0
            
            # 청크 처리 시작 알림
            chunk_progress = calculate_chunk_progress(
                PHASE_START + 2,
                PHASE_END - int((PHASE_END - PHASE_START) * MERGE_RATIO),
                i,
                total_chunks,
                merge_progress_ratio=0
            )
            # Progress는 메인 루프에서 처리
            
            # 청크 처리 (재시도 포함)
            stories, retry_count = await _process_chunk_with_retry(
                chunk_text, i, total_chunks, start_char, end_char, semaphore
            )
            
            # 각 청크의 User Story ID에 청크 번호를 포함시켜 고유성 보장
            for story in stories:
                original_id = getattr(story, "id", None)
                if original_id and original_id.startswith("US-"):
                    try:
                        chunk_prefix = f"US-{i+1}-"
                        if "-" in original_id[3:]:  # 이미 청크 번호가 있는 경우
                            continue
                        number_part = original_id[3:]
                        new_id = f"{chunk_prefix}{number_part}"
                        try:
                            setattr(story, "id", new_id)
                        except Exception:
                            if hasattr(story, "model_copy"):
                                story = story.model_copy(update={"id": new_id})
                            elif hasattr(story, "copy"):
                                story = story.copy(update={"id": new_id})
                    except Exception:
                        pass
            
            return i, stories, retry_count
        
        # 모든 청크를 병렬로 처리
        tasks = [
            process_chunk_task(i, chunk_text, start_char, end_char)
            for i, (chunk_text, start_char, end_char) in enumerate(chunks)
        ]
        
        # 병렬 실행 및 진행 상황 추적
        chunk_results = [None] * total_chunks
        completed_count = 0
        
        # asyncio.as_completed를 사용하여 완료되는 대로 처리
        for coro in asyncio.as_completed(tasks):
            # Check cancellation
            if getattr(ctx.session, "is_cancelled", False):
                yield ProgressEvent(
                    phase=IngestionPhase.ERROR,
                    message="❌ 생성이 중단되었습니다",
                    progress=getattr(ctx.session, "progress", 0) or 0,
                    data={"error": "Cancelled by user", "cancelled": True},
                )
                return
            
            try:
                chunk_idx, stories, retry_count = await coro
                chunk_results[chunk_idx] = stories
                completed_count += 1
                
                # 진행 상황 업데이트
                chunk_complete_progress = calculate_chunk_progress(
                    PHASE_START + 2,
                    PHASE_END - int((PHASE_END - PHASE_START) * MERGE_RATIO),
                    completed_count,
                    total_chunks,
                    merge_progress_ratio=0
                )
                
                retry_msg = f" (재시도 {retry_count}회)" if retry_count > 0 else ""
                yield ProgressEvent(
                    phase=IngestionPhase.EXTRACTING_USER_STORIES,
                    message=f"청크 {chunk_idx + 1}/{total_chunks} 완료 ({len(stories)}개 User Story 추출){retry_msg}",
                    progress=chunk_complete_progress
                )
            except Exception as e:
                SmartLogger.log(
                    "ERROR",
                    f"Chunk processing task failed",
                    category="ingestion.user_stories.chunk.task_failed",
                    params={
                        "session_id": ctx.session.id,
                        "error": str(e),
                        "error_type": type(e).__name__,
                    },
                )
                completed_count += 1
        
        # None인 결과는 빈 리스트로 변환
        chunk_results = [result if result is not None else [] for result in chunk_results]
        
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
        
        # 내용 기반 중복 제거 및 정규화 (공통 함수 사용)
        deduplicated_by_content = normalize_and_dedup_user_stories(all_stories, ctx.session.id)
        
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
        # 청킹 여부와 무관하게 항상 정규화 및 중복 제거 적용
        user_stories = normalize_and_dedup_user_stories(user_stories, ctx.session.id)
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


