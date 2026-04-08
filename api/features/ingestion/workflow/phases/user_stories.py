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


# EJB lifecycle patterns that should NOT become User Stories
_EJB_LIFECYCLE_ACTION_PATTERNS = (
    "ejbcreate", "ejbremove", "ejbactivate", "ejbpassivate",
    "ejbload", "ejbstore", "ejbpostcreate", "ejbfind",
    "setentitycontext", "unsetentitycontext", "setsessioncontext",
    "findbyprimar", "find by primary", "by its primary key",
    "initialize ejb", "clean up resource",
    "handle post-creation", "handle postcreation",
)


_IMPLEMENTATION_DETAIL_PATTERNS = (
    "generate id", "generate repayment id", "record timestamp",
    "calculate total", "set status to", "convert dto", "map entity",
    "validate field", "initialize variable", "parse parameter",
    "format output", "build response", "construct object",
    "assign sequence", "increment counter",
)

_ERROR_HANDLING_PATTERNS = (
    "rollback transaction", "display exception", "throw exception",
    "handle error", "log error", "catch exception",
    "display error message", "return error code", "show error",
    "exception message", "error handling",
)


def _is_low_quality_us(action: str, role: str) -> bool:
    """Check if a User Story represents an implementation detail or error handling step."""
    action_lower = action.lower()
    for pattern in _IMPLEMENTATION_DETAIL_PATTERNS:
        if pattern in action_lower:
            return True
    for pattern in _ERROR_HANDLING_PATTERNS:
        if pattern in action_lower:
            return True
    return False


def _is_ejb_lifecycle_us(action: str, role: str) -> bool:
    """Check if a User Story represents an EJB lifecycle operation."""
    action_lower = action.lower()
    role_lower = role.lower()
    # Filter by action content
    for pattern in _EJB_LIFECYCLE_ACTION_PATTERNS:
        if pattern in action_lower:
            return True
    # Filter by system_administrator role with infrastructure keywords
    if role_lower == "system_administrator" and any(
        kw in action_lower for kw in ("resource", "initialize", "cleanup", "clean up")
    ):
        return True
    return False


def normalize_and_dedup_user_stories(stories: list[Any], session_id: str, is_analyzer: bool = False) -> list[Any]:
    """
    User Story 목록을 정규화하고 중복을 제거합니다.
    청킹 여부와 무관하게 항상 적용되어야 합니다.
    is_analyzer=True인 경우 EJB 라이프사이클 US도 필터링합니다.
    """
    seen = set()
    out = []
    ejb_filtered = 0
    low_quality_filtered = 0

    for us in stories:
        role = (getattr(us, "role", "") or "").strip()
        action = (getattr(us, "action", "") or "").strip()
        benefit = (getattr(us, "benefit", "") or "").strip()

        if not action:
            continue

        # EJB lifecycle US filtering for analyzer graph
        if is_analyzer and _is_ejb_lifecycle_us(action, role):
            ejb_filtered += 1
            continue

        # Low quality US filtering for analyzer graph (implementation details, error handling)
        if is_analyzer and _is_low_quality_us(action, role):
            low_quality_filtered += 1
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

    # 진단을 위한 표준 출력 (dedup 분석)
    dedup_info = (
        f"[DEDUP DEBUG] raw={len(stories)}, dedup={len(out)}, "
        f"ejb_filtered={ejb_filtered}, low_quality_filtered={low_quality_filtered}, "
        f"ratio={round(len(out) / max(len(stories), 1), 4):.2%}"
    )
    print(dedup_info)

    SmartLogger.log(
        "INFO",
        f"User story normalize+dedup summary - {dedup_info}",
        category="ingestion.user_stories.dedup.summary",
        params={
            "session_id": session_id,
            "raw_story_count": len(stories),
            "dedup_story_count": len(out),
            "ejb_filtered_count": ejb_filtered,
            "low_quality_filtered_count": low_quality_filtered,
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
                display_name=us_display_name or None,
                source_screen_name=getattr(us, "source_screen_name", None),
                source_unit_id=getattr(us, "source_unit_id", None),
                sequence=getattr(us, "sequence", None),
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

        # SOURCED_FROM 관계: UserStory → BusinessLogic (sequence 기반 정확 매칭)
        source_uid = getattr(us, "source_unit_id", None)
        source_bl = getattr(us, "source_bl", None) or []
        if source_uid:
            try:
                if source_bl:
                    # sequence 기반 매칭
                    with ctx.client.session() as link_session:
                        link_session.run(
                            "MATCH (us:UserStory {id: $us_id}) "
                            "MATCH (f:FUNCTION {function_id: $unit_id})-[:HAS_BUSINESS_LOGIC]->(bl:BusinessLogic) "
                            "WHERE bl.sequence IN $sequences "
                            "MERGE (us)-[:SOURCED_FROM]->(bl)",
                            us_id=us.id,
                            unit_id=source_uid,
                            sequences=source_bl,
                        )
                else:
                    # source_bl 없으면 해당 함수의 모든 BL에 연결 (fallback)
                    with ctx.client.session() as link_session:
                        link_session.run(
                            "MATCH (us:UserStory {id: $us_id}) "
                            "MATCH (f:FUNCTION {function_id: $unit_id})-[:HAS_BUSINESS_LOGIC]->(bl:BusinessLogic) "
                            "MERGE (us)-[:SOURCED_FROM]->(bl)",
                            us_id=us.id,
                            unit_id=source_uid,
                        )
            except Exception as e:
                print(f"[SOURCED_FROM] Error for US={us.id}: {e}")
        
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

    # Analyzer graph: 분석 단위별 개별 US 생성
    input_content = ctx.content
    _analyzer_processed = False
    should_chunk_result = False
    if ctx.source_type == "analyzer_graph":
        from api.features.ingestion.analyzer_graph.graph_context_builder import build_unit_contexts
        sb_contexts = build_unit_contexts()
        if sb_contexts:
            # BusinessLogic 단위별 개별 처리
            all_sb_stories: list = []
            for sb_idx, (sb_name, sb_unit_id, sb_context) in enumerate(sb_contexts):
                if getattr(ctx.session, "is_cancelled", False):
                    yield ProgressEvent(
                        phase=IngestionPhase.ERROR,
                        message="❌ 생성이 중단되었습니다",
                        progress=getattr(ctx.session, "progress", 0) or 0,
                        data={"error": "Cancelled by user", "cancelled": True},
                    )
                    return

                progress = PHASE_START + int((sb_idx / len(sb_contexts)) * (PHASE_END - PHASE_START - 4))
                yield ProgressEvent(
                    phase=IngestionPhase.EXTRACTING_USER_STORIES,
                    message=f"User Story 추출 중... ({sb_name} {sb_idx+1}/{len(sb_contexts)})",
                    progress=progress,
                )

                print(f"[ANALYZER US] Processing Session Bean {sb_idx+1}/{len(sb_contexts)}: {sb_name} ({estimate_tokens(sb_context)} tokens)")
                try:
                    from api.features.ingestion.analyzer_graph.graph_to_user_stories import extract_user_stories_from_analyzer_graph
                    sb_stories = await asyncio.to_thread(extract_user_stories_from_analyzer_graph, sb_context)
                    print(f"[ANALYZER US] {sb_name}: {len(sb_stories)} US generated")
                    # 출처 분석 단위(unit) 태깅 — 역추적용
                    for us in sb_stories:
                        us.source_unit_id = sb_unit_id
                    all_sb_stories.extend(sb_stories)
                except Exception as e:
                    SmartLogger.log(
                        "ERROR",
                        f"US extraction failed for {sb_name}",
                        category="ingestion.user_stories.session_bean.error",
                        params={"session_id": ctx.session.id, "sb_name": sb_name, "error": str(e)},
                    )

            # 정규화 + 중복 제거 + EJB 필터
            user_stories = normalize_and_dedup_user_stories(all_sb_stories, ctx.session.id, is_analyzer=True)

            # 순차 ID 재부여
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
                message=f"User Story 추출 완료 (총 {len(user_stories)}개, Session Bean {len(sb_contexts)}개 처리)",
                progress=PHASE_END - 2,
            )

            # Skip to Neo4j 저장 (아래 chunking/non-chunking 경로 건너뜀)
            # goto: Neo4j 저장 section (line after else block)
            # Python에는 goto가 없으므로, 플래그로 제어
            _analyzer_processed = True
        else:
            _analyzer_processed = False
    else:
        _analyzer_processed = False

    if not _analyzer_processed and not _figma_processed:
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

    if not _analyzer_processed and not _figma_processed and should_chunk_result:
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
        deduplicated_by_content = normalize_and_dedup_user_stories(all_stories, ctx.session.id, is_analyzer=ctx.source_type == "analyzer_graph")
        
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
    elif not _analyzer_processed and not _figma_processed:
        # 기존 로직 (청킹 불필요)
        print(f"[CHUNKING DEBUG] Entering non-chunking path - processing entire document at once")
        yield ProgressEvent(
            phase=IngestionPhase.EXTRACTING_USER_STORIES,
            message="User Story 추출 중...",
            progress=PHASE_START + 5
        )

        user_stories = await asyncio.to_thread(extract_user_stories_from_text, input_content)
        # 청킹 여부와 무관하게 항상 정규화 및 중복 제거 적용
        user_stories = normalize_and_dedup_user_stories(user_stories, ctx.session.id, is_analyzer=ctx.source_type == "analyzer_graph")
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

    # analyzer_graph: BL 캐시 로딩 (이후 Phase에서 US 텍스트에 BL을 합쳐 전달하기 위함)
    if ctx.source_type == "analyzer_graph":
        from api.features.ingestion.workflow.utils.user_story_format import load_bl_for_user_stories
        ctx.bl_by_user_story = load_bl_for_user_stories(ctx.client)
        if ctx.bl_by_user_story:
            print(f"[BL CACHE] Loaded BL for {len(ctx.bl_by_user_story)} user stories")

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


