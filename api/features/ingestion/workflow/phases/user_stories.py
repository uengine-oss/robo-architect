from __future__ import annotations

import asyncio
from typing import Any, AsyncGenerator

from api.features.ingestion.ingestion_contracts import IngestionPhase, ProgressEvent
from api.features.ingestion.figma_to_user_stories import (
    extract_user_stories_from_figma,
    extract_user_stories_from_figma_chunk,
    parse_and_chunk_figma_nodes,
    _build_node_maps,
    _describe_node,
    MAX_CONCURRENT_CHUNKS as FIGMA_MAX_CONCURRENT,
)
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
        f"User story normalize+dedup: raw={len(stories)} dedup={len(out)}",
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
    us_display_name = getattr(us, "displayName", None) or ""
    
    try:
        # User Story 생성 — bulk 결과 캐시에서 조회 (FR-001).
        # 페이즈 진입 시 단일 bulk_create_user_stories() 호출로 일괄 생성된 결과를
        # `_bulk_us_results` 딕셔너리에 미리 저장해두고, 여기서는 룩업만 수행.
        bulk_results: dict[str, dict[str, Any]] = getattr(ctx, "_bulk_us_results", None) or {}
        result = bulk_results.get(us.id)
        if not result or not result.get("id"):
            return None, None, f"bulk_create_user_stories returned empty result for {us.id}"

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
    실패 시 청크를 반으로 분할하여 양쪽 모두 처리합니다 (최대 2회).
    
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
    async def _process_text_recursive(text: str, depth: int = 0) -> tuple[list[Any], int]:
        """
        재귀적으로 텍스트를 처리합니다.
        실패 시 반으로 분할하여 양쪽 모두 처리합니다.
        """
        if depth > max_retries:
            SmartLogger.log(
                "ERROR",
                f"Chunk {chunk_idx + 1} failed after {max_retries} recursive splits",
                category="ingestion.user_stories.chunk.failed",
                params={
                    "chunk_idx": chunk_idx + 1,
                    "total_chunks": total_chunks,
                    "depth": depth,
                    "text_length": len(text),
                },
            )
            return [], depth
        
        try:
            stories = await asyncio.to_thread(extract_user_stories_from_text, text)
            
            # 청크별 상세 로깅 (기준 튜닝을 위한 디버깅 정보)
            chunk_tokens = estimate_tokens(text)
            chunk_info = (
                f"[CHUNK DEBUG] chunk={chunk_idx + 1}/{total_chunks}, "
                f"tokens={chunk_tokens}, stories={len(stories)}, depth={depth}"
            )
            print(chunk_info)
            SmartLogger.log(
                "INFO",
                f"Chunk {chunk_idx + 1} processed: {len(stories)} stories for {chunk_tokens} tokens (depth: {depth})",
                category="ingestion.user_stories.chunk.processed",
                params={
                    "chunk_idx": chunk_idx + 1,
                    "total_chunks": total_chunks,
                    "chunk_tokens": chunk_tokens,
                    "stories_count": len(stories),
                    "depth": depth,
                    "text_length": len(text),
                }
            )
            
            # 불충분 출력 감지: 정상 응답이지만 출력이 너무 적은 경우
            # 보수적 기준: 1800 토큰 이상인데 6개 미만이면 거의 확실히 이상
            # (정상 변동 범위를 고려하여 과도한 split 방지)
            
            # 1800 토큰 이상인데 6개 미만이면 불충분으로 판단
            # 이 기준은 정상 변동(10~25개)을 고려하여 매우 보수적으로 설정
            if chunk_tokens >= 1800 and len(stories) < 6:
                # 불충분한 출력으로 판단하여 예외 발생 (split 로직 재사용)
                SmartLogger.log(
                    "WARN",
                    f"Chunk {chunk_idx + 1} incomplete output detected: {len(stories)} stories for {chunk_tokens} tokens "
                    f"(threshold: <6 stories for >=1800 tokens)",
                    category="ingestion.user_stories.chunk.incomplete_output",
                    params={
                        "chunk_idx": chunk_idx + 1,
                        "total_chunks": total_chunks,
                        "chunk_tokens": chunk_tokens,
                        "stories_count": len(stories),
                        "threshold_tokens": 1800,
                        "threshold_stories": 6,
                        "depth": depth,
                    }
                )
                raise RuntimeError(
                    f"incomplete_output: tokens={chunk_tokens}, stories={len(stories)} "
                    f"(expected at least 6 stories for {chunk_tokens} tokens)"
                )
            
            return stories, depth
        except Exception as e:
            # 실패 시 반으로 분할하여 양쪽 모두 처리
            text_length = len(text)
            
            # 문단 경계에서 분할 (가능한 경우)
            if "\n\n" in text:
                paragraphs = text.split("\n\n")
                mid_point = len(paragraphs) // 2
                if mid_point > 0:
                    first_half = "\n\n".join(paragraphs[:mid_point])
                    second_half = "\n\n".join(paragraphs[mid_point:])
                else:
                    # 문단이 너무 적으면 중간에서 분할
                    first_half = text[:text_length // 2]
                    second_half = text[text_length // 2:]
            else:
                # 문단 구분자가 없으면 중간에서 분할
                first_half = text[:text_length // 2]
                second_half = text[text_length // 2:]
            
            SmartLogger.log(
                "WARN",
                f"Chunk {chunk_idx + 1} failed, splitting and retrying both halves (depth {depth + 1}/{max_retries})",
                category="ingestion.user_stories.chunk.retry",
                params={
                    "chunk_idx": chunk_idx + 1,
                    "depth": depth + 1,
                    "original_size": text_length,
                    "first_half_size": len(first_half),
                    "second_half_size": len(second_half),
                    "error": str(e),
                },
            )
            
            # 양쪽 모두 재귀적으로 처리
            first_stories, first_depth = await _process_text_recursive(first_half, depth + 1)
            second_stories, second_depth = await _process_text_recursive(second_half, depth + 1)
            
            # 더 깊은 재시도 횟수 반환
            max_depth = max(first_depth, second_depth)
            all_stories = first_stories + second_stories
            
            return all_stories, max_depth
    
    async with semaphore:
        return await _process_text_recursive(chunk_text, 0)


async def extract_user_stories_phase(ctx: IngestionWorkflowContext) -> AsyncGenerator[ProgressEvent, None]:
    """
    Phase 2: extract user stories and persist them to Neo4j.
    Supports chunking for large requirements documents with parallel processing.
    """
    PHASE_START = 10
    PHASE_END = 20
    MERGE_RATIO = 0.1  # 병합 작업이 10% 차지
    MAX_CONCURRENT_CHUNKS = 3  # 동시 처리 청크 수 (출력 안정성 우선, 429 위험 최소화)
    
    # Phase 시작
    yield ProgressEvent(
        phase=IngestionPhase.EXTRACTING_USER_STORIES,
        message="User Story 추출 시작...",
        progress=PHASE_START
    )

    # Figma source: extract user stories from UI node data (chunked by screen)
    _figma_processed = False
    if ctx.source_type == "figma":
        yield ProgressEvent(
            phase=IngestionPhase.EXTRACTING_USER_STORIES,
            message="Figma UI 요소 분석 중...",
            progress=PHASE_START + 2,
        )

        try:
            # Parse nodes and split into screen-based chunks
            nodes, children_map, screen_chunks = parse_and_chunk_figma_nodes(ctx.content)
            total_chunks = len(screen_chunks)

            # Build per-screen node structure summaries for UI wireframe phase
            all_top_frames = [f for chunk in screen_chunks for f in chunk]
            for frame in all_top_frames:
                screen_name = frame.get("name", "")
                if screen_name:
                    screen_lines = _describe_node(frame, children_map, 0)
                    ctx.figma_screens[screen_name] = "\n".join(screen_lines)

            SmartLogger.log(
                "INFO",
                f"Figma chunking: {total_chunks} chunk(s) from {len(nodes)} nodes",
                category="ingestion.user_stories.figma.chunking",
                params={"session_id": ctx.session.id, "total_chunks": total_chunks, "total_nodes": len(nodes)},
            )

            # Collect valid screen names for fuzzy matching validation
            valid_screen_names = set(ctx.figma_screens.keys())

            if total_chunks == 1:
                # Small storyboard: single LLM call
                figma_stories = await asyncio.to_thread(extract_user_stories_from_figma, ctx.content, valid_screen_names)
            else:
                # Large storyboard: parallel chunk processing
                semaphore = asyncio.Semaphore(FIGMA_MAX_CONCURRENT)
                all_chunk_stories: list = []

                async def process_chunk(chunk_idx: int, chunk: list) -> list:
                    async with semaphore:
                        if getattr(ctx.session, "is_cancelled", False):
                            return []
                        return await asyncio.to_thread(
                            extract_user_stories_from_figma_chunk,
                            nodes, chunk, children_map, chunk_idx, total_chunks,
                            valid_screen_names,
                        )

                tasks = []
                for ci, chunk in enumerate(screen_chunks):
                    tasks.append(process_chunk(ci, chunk))

                for ci, coro in enumerate(asyncio.as_completed(tasks)):
                    if getattr(ctx.session, "is_cancelled", False):
                        yield ProgressEvent(
                            phase=IngestionPhase.ERROR,
                            message="❌ 생성이 중단되었습니다",
                            progress=getattr(ctx.session, "progress", 0) or 0,
                            data={"error": "Cancelled by user", "cancelled": True},
                        )
                        return

                    chunk_result = await coro
                    all_chunk_stories.extend(chunk_result)

                    chunk_progress = PHASE_START + 2 + int(((ci + 1) / total_chunks) * (PHASE_END - PHASE_START - 4))
                    yield ProgressEvent(
                        phase=IngestionPhase.EXTRACTING_USER_STORIES,
                        message=f"Figma UI 분석 중... ({ci + 1}/{total_chunks} 청크, {len(all_chunk_stories)}개 US)",
                        progress=chunk_progress,
                    )

                figma_stories = all_chunk_stories

            user_stories = normalize_and_dedup_user_stories(figma_stories, ctx.session.id)

            # Re-assign sequential IDs
            for idx, us in enumerate(user_stories, start=1):
                new_id = f"US-{idx:03d}"
                try:
                    setattr(us, "id", new_id)
                except Exception:
                    if hasattr(us, "model_copy"):
                        us = us.model_copy(update={"id": new_id})

            ctx.user_stories = user_stories
            yield ProgressEvent(
                phase=IngestionPhase.EXTRACTING_USER_STORIES,
                message=f"Figma UI 분석 완료 (User Story {len(user_stories)}개 추출, {total_chunks}개 청크)",
                progress=PHASE_END - 2,
            )
            _figma_processed = True
        except Exception as e:
            SmartLogger.log(
                "ERROR",
                "Figma user story extraction failed",
                category="ingestion.user_stories.figma.error",
                params={"session_id": ctx.session.id, "error": str(e)},
            )
            yield ProgressEvent(
                phase=IngestionPhase.ERROR,
                message=f"Figma UI 분석 실패: {e}",
                progress=PHASE_START + 5,
                data={"error": str(e)},
            )
            return

    input_content = ctx.content
    _hybrid_processed = False
    should_chunk_result = False

    # Hybrid mode: BPM (Phase 1~4) → User Stories. One group = one BpmTask.
    if ctx.source_type == "hybrid":
        from api.features.ingestion.hybrid.bpm_context_builder import (
            build_grouped_unit_contexts_from_bpm,
        )
        from api.features.ingestion.hybrid.bpm_to_user_stories import (
            extract_user_stories_from_bpm_group,
        )

        hsid = getattr(ctx.session, "hybrid_source_session_id", None)
        if not hsid:
            yield ProgressEvent(
                phase=IngestionPhase.ERROR,
                message="❌ hybrid_source_session_id 가 세션에 없습니다",
                progress=getattr(ctx.session, "progress", 0) or 0,
                data={"error": "missing_hybrid_source_session_id"},
            )
            return

        grouped_contexts = build_grouped_unit_contexts_from_bpm(hsid)
        if grouped_contexts:
            all_hb_stories: list = []
            total_groups = len(grouped_contexts)
            SmartLogger.log(
                "INFO",
                f"Hybrid: {total_groups} BpmTask groups detected",
                category="ingestion.user_stories.hybrid.grouped",
                params={"session_id": ctx.session.id, "hybrid_source_session_id": hsid, "total_groups": total_groups},
            )

            for grp_idx, (grp_name, grp_unit_ids, grp_context) in enumerate(grouped_contexts):
                if getattr(ctx.session, "is_cancelled", False):
                    yield ProgressEvent(
                        phase=IngestionPhase.ERROR,
                        message="❌ 생성이 중단되었습니다",
                        progress=getattr(ctx.session, "progress", 0) or 0,
                        data={"error": "Cancelled by user", "cancelled": True},
                    )
                    return

                progress = PHASE_START + int((grp_idx / total_groups) * (PHASE_END - PHASE_START - 4))
                yield ProgressEvent(
                    phase=IngestionPhase.EXTRACTING_USER_STORIES,
                    message=f"User Story 추출 중... (Task: {grp_name} {grp_idx+1}/{total_groups})",
                    progress=progress,
                )

                try:
                    grp_stories = await asyncio.to_thread(extract_user_stories_from_bpm_group, grp_context)
                    primary_unit_id = grp_unit_ids[0] if grp_unit_ids else ""
                    for us in grp_stories:
                        us.source_unit_id = primary_unit_id  # task_id — 역추적
                    all_hb_stories.extend(grp_stories)
                except Exception as e:
                    SmartLogger.log(
                        "ERROR",
                        f"US extraction failed for hybrid Task {grp_name}",
                        category="ingestion.user_stories.hybrid.group_error",
                        params={"session_id": ctx.session.id, "task": grp_name, "error": str(e)},
                    )

            user_stories = normalize_and_dedup_user_stories(all_hb_stories, ctx.session.id)
            for idx, us in enumerate(user_stories, start=1):
                new_id = f"US-{idx:03d}"
                try:
                    setattr(us, "id", new_id)
                except Exception:
                    if hasattr(us, "model_copy"):
                        us = us.model_copy(update={"id": new_id})

            ctx.user_stories = user_stories

            # ─── Hybrid input boost — prefetch BL info per UserStory ─────────
            # Downstream legacy ES phases (aggregates/commands/events_from_us/
            # gwt/bcs/readmodels/policies) read `ctx.hybrid_us_rules` to weave
            # analyzer Rule.statement / Example GWT / writes.op /
            # coupled_domains / guard_rule_id chain into their LLM prompts.
            # See Phase5_EventStorming_Promotion_PRD §12 (v3 input boost) for the rationale.
            try:
                from api.features.ingestion.hybrid.bpm_context_builder import (
                    fetch_hybrid_us_rules,
                )
                # Each US's source_unit_id is the BpmTask.id it was extracted from.
                us_to_task: list[tuple[str, str]] = [
                    (us.id, getattr(us, "source_unit_id", "") or "")
                    for us in user_stories
                    if getattr(us, "source_unit_id", None)
                ]
                if us_to_task:
                    ctx.hybrid_us_rules = fetch_hybrid_us_rules(hsid, us_to_task)
                    enriched_us = sum(1 for v in ctx.hybrid_us_rules.values() if v)
                    SmartLogger.log(
                        "INFO",
                        f"Hybrid input boost: {enriched_us}/{len(us_to_task)} US enriched with BL info",
                        category="ingestion.user_stories.hybrid.boost",
                        params={
                            "session_id": ctx.session.id,
                            "hybrid_source_session_id": hsid,
                            "enriched_us": enriched_us,
                            "total_us": len(us_to_task),
                            "total_bl_entries": sum(len(v) for v in ctx.hybrid_us_rules.values()),
                        },
                    )
            except Exception as boost_err:
                SmartLogger.log(
                    "WARN",
                    "Hybrid BL prefetch failed; downstream phases will fall back to US-text-only LLM input",
                    category="ingestion.user_stories.hybrid.boost.error",
                    params={"session_id": ctx.session.id, "error": str(boost_err)},
                )

            yield ProgressEvent(
                phase=IngestionPhase.EXTRACTING_USER_STORIES,
                message=f"User Story 추출 완료 (총 {len(user_stories)}개, BPM Task {total_groups}개 처리)",
                progress=PHASE_END - 2,
            )
            _hybrid_processed = True

    if not _figma_processed and not _hybrid_processed:
        # 스캐닝 및 청킹 판단
        content_tokens = estimate_tokens(input_content)
        should_chunk_result = should_chunk(input_content, max_tokens=USER_STORY_CHUNK_SIZE)

        # 디버깅: 청킹 판단 로그 (표준 출력에도 출력)
        chunking_info = (
            f"[CHUNKING DEBUG] content_tokens={content_tokens}, "
            f"threshold={USER_STORY_CHUNK_SIZE}, "
            f"should_chunk={should_chunk_result}, "
            f"comparison={content_tokens} > {USER_STORY_CHUNK_SIZE} = {content_tokens > USER_STORY_CHUNK_SIZE}"
        )
        print(chunking_info)
        SmartLogger.log(
            "INFO",
            f"User Story extraction: chunking decision - {chunking_info}",
            category="ingestion.user_stories.chunking.decision",
            params={
                "session_id": ctx.session.id,
                "content_length": len(ctx.content),
                "content_tokens": content_tokens,
                "chunk_size_threshold": USER_STORY_CHUNK_SIZE,
                "should_chunk": should_chunk_result,
                "comparison": f"{content_tokens} > {USER_STORY_CHUNK_SIZE} = {content_tokens > USER_STORY_CHUNK_SIZE}",
            },
        )

    if not _figma_processed and not _hybrid_processed and should_chunk_result:
        print(f"[CHUNKING DEBUG] Entering chunking path - will split into chunks")
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
            input_content,
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

                # ── 청크 단위 incremental tree 표시 ──
                # 각 청크의 user story 들을 그 즉시 트리에 띄움. ID 는 청크별로
                # 이미 unique ("US-{chunk_idx+1}-{n}") 하므로 그대로 사용.
                # 나중에 dedup 으로 제거되는 항목은 UserStoryConsolidated 이벤트로
                # 트리에서 제거됨. 이후의 per-row gather 도 같은 ID 로 다시 emit
                # 하지만 frontend addUserStory 는 idempotent (exists 체크) 이라
                # 무해함.
                for s in stories:
                    s_role = (getattr(s, "role", "") or "").strip()
                    s_action = (getattr(s, "action", "") or "").strip()
                    if not s_action:
                        continue
                    s_benefit = getattr(s, "benefit", None)
                    s_id = getattr(s, "id", None)
                    if not s_id:
                        continue
                    s_priority = getattr(s, "priority", "medium")
                    s_ui_desc = getattr(s, "ui_description", None) or ""
                    yield ProgressEvent(
                        phase=IngestionPhase.EXTRACTING_USER_STORIES,
                        message=f"User Story 추출됨: {s_role}: {s_action[:30]}",
                        progress=chunk_complete_progress,
                        data={
                            "type": "UserStory",
                            "object": {
                                "id": s_id,
                                "name": f"{s_role}: {s_action[:30]}...",
                                "type": "UserStory",
                                "role": s_role,
                                "action": s_action,
                                "benefit": s_benefit,
                                "priority": s_priority,
                                "ui_description": s_ui_desc,
                                "provisional": True,  # dedup 전, 임시 표시
                            },
                        },
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
        # 청크 단위 incremental 표시와의 정합성을 위해, 청크에서 부여된 ID
        # ("US-{chunk}-{n}") 를 canonical 로 유지함. (이전에는 여기서 US-001,
        # US-002 식으로 재명명했으나, 그러면 frontend 트리에서 ID 정체성이
        # 깨짐 — chunk 단계에서 emit 했던 노드를 식별 못 함.)
        pre_dedup_ids = [getattr(s, "id", None) for s in all_stories if getattr(s, "id", None)]
        deduplicated_by_content = normalize_and_dedup_user_stories(all_stories, ctx.session.id, is_analyzer=ctx.source_type == "analyzer_graph")
        post_dedup_ids = {getattr(s, "id", None) for s in deduplicated_by_content if getattr(s, "id", None)}
        dedup_dropped_ids = [sid for sid in pre_dedup_ids if sid not in post_dedup_ids]

        # ── Cross-chunk semantic consolidation (LLM-based) ──
        # 청크 경계로 쪼개진 user story 들을 합치고, 필드 단위 규칙들을
        # acceptance_criteria 로 흡수. 실패 시 fail-open (입력 그대로).
        yield ProgressEvent(
            phase=IngestionPhase.EXTRACTING_USER_STORIES,
            message=f"User Story 통합 분석 중... ({len(deduplicated_by_content)}개 → 사용자 가치 단위로 정리)",
            progress=PHASE_END - 5,
        )
        from api.features.ingestion.requirements_to_user_stories import consolidate_user_stories
        consolidated, consolidation_dropped_ids = await asyncio.to_thread(
            consolidate_user_stories, deduplicated_by_content, ctx.session.id
        )

        # 트리에서 제거되어야 하는 ID = dedup 으로 빠진 것 + consolidation 으로 흡수된 것
        all_dropped_ids = list(dict.fromkeys([*dedup_dropped_ids, *consolidation_dropped_ids]))
        if all_dropped_ids:
            yield ProgressEvent(
                phase=IngestionPhase.EXTRACTING_USER_STORIES,
                message=f"User Story 정리: {len(all_dropped_ids)}개 흡수/중복 제거",
                progress=PHASE_END - 4,
                data={
                    "type": "UserStoryConsolidated",
                    "removedIds": all_dropped_ids,
                },
            )

        # Consolidation 결과로 acceptance_criteria 가 채워진 canonical user story
        # 들을 다시 트리에 emit (frontend addUserStory 가 upsert 라 in-place 갱신).
        # 이때 provisional=false 로 표시.
        for cs in consolidated:
            try:
                cs_role = (getattr(cs, "role", "") or "").strip()
                cs_action = (getattr(cs, "action", "") or "").strip()
                if not cs_action:
                    continue
                yield ProgressEvent(
                    phase=IngestionPhase.EXTRACTING_USER_STORIES,
                    message=f"User Story 정리됨: {cs_role}: {cs_action[:30]}",
                    progress=PHASE_END - 3,
                    data={
                        "type": "UserStory",
                        "object": {
                            "id": cs.id,
                            "name": f"{cs_role}: {cs_action[:30]}...",
                            "type": "UserStory",
                            "role": cs_role,
                            "action": cs_action,
                            "benefit": getattr(cs, "benefit", None),
                            "priority": getattr(cs, "priority", "medium"),
                            "ui_description": getattr(cs, "ui_description", "") or "",
                            "acceptance_criteria": list(getattr(cs, "acceptance_criteria", []) or []),
                            "provisional": False,
                        },
                    },
                )
            except Exception:
                pass

        user_stories = consolidated
        
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
    elif not _figma_processed and not _hybrid_processed:
        # 기존 로직 (청킹 불필요)
        print(f"[CHUNKING DEBUG] Entering non-chunking path - processing entire document at once")
        yield ProgressEvent(
            phase=IngestionPhase.EXTRACTING_USER_STORIES,
            message="User Story 추출 중...",
            progress=PHASE_START + 5
        )

        user_stories = await asyncio.to_thread(extract_user_stories_from_text, input_content)
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

        # ── Pre-build bulk rows + run ONE bulk_create_user_stories call ──
        # FR-001 (spec 018): every entity type writes through a bulk helper.
        # The per-row tasks below then look up their result instead of doing a
        # Neo4j round-trip each.
        bulk_rows: list[dict[str, Any]] = []
        for us in ctx.user_stories:
            role = (getattr(us, "role", "") or "").strip()
            action = (getattr(us, "action", "") or "").strip()
            if not action:
                continue
            role = canonicalize_role(role)
            action = canonicalize_action(action)
            if not role or role.lower() in ("user", "사용자", ""):
                from api.features.ingestion.requirements_to_user_stories import _infer_role_from_context
                benefit = getattr(us, "benefit", "") or ""
                inferred = _infer_role_from_context(action, benefit)
                role = inferred if inferred else "customer"
                try:
                    setattr(us, "role", role)
                except Exception:
                    pass
            ui_desc = ensure_nonempty_ui_description(
                role,
                action,
                getattr(us, "benefit", None),
                getattr(us, "ui_description", None),
            )
            bulk_rows.append(
                {
                    "id": us.id,
                    "role": role,
                    "action": action,
                    "benefit": getattr(us, "benefit", None),
                    "priority": getattr(us, "priority", "medium"),
                    "status": "draft",
                    "ui_description": ui_desc,
                    "display_name": getattr(us, "displayName", None) or None,
                    "source_screen_name": getattr(us, "source_screen_name", None),
                    "source_unit_id": getattr(us, "source_unit_id", None),
                    "sequence": getattr(us, "sequence", None),
                    "acceptance_criteria": list(getattr(us, "acceptance_criteria", []) or []),
                }
            )
        from api.features.ingestion.suspend_gate import session_call_slot
        try:
            async with session_call_slot(ctx.session):
                bulk_results_list = await asyncio.to_thread(
                    ctx.client.bulk_create_user_stories,
                    bulk_rows,
                    session_id=ctx.session.id,
                    phase="extracting_user_stories",
                )
        except Exception as exc:  # noqa: BLE001
            SmartLogger.log(
                "ERROR",
                f"bulk_create_user_stories failed: {exc}",
                category="ingestion.batch.user_story.flush_failed",
                params={"session_id": ctx.session.id, "rowCount": len(bulk_rows), "error": str(exc)},
            )
            bulk_results_list = []
        ctx._bulk_us_results = {  # type: ignore[attr-defined]
            row["id"]: dict(res)
            for row, res in zip(bulk_rows, bulk_results_list)
            if res.get("ok") and res.get("id")
        }

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


