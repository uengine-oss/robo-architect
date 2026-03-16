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
from api.features.ingestion.event_storming.nodes import PolicyList
from api.features.ingestion.event_storming.prompts import IDENTIFY_POLICIES_PROMPT, SYSTEM_PROMPT
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


async def _create_policy_with_links(
    pol: Any,
    pol_idx: int,
    total_policies: int,
    ctx: IngestionWorkflowContext,
) -> tuple[dict[str, Any] | None, str]:
    """
    Create a single policy with user story links.
    Returns (created_policy_dict, error_message)
    """
    trigger_event_id = None
    invoke_command_id = None
    target_bc_id = None

    # Find trigger event
    try:
        for events in ctx.events_by_agg.values():
            for evt in events:
                evt_name = evt.get("name") if isinstance(evt, dict) else getattr(evt, "name", "")
                if evt_name == pol.trigger_event:
                    trigger_event_id = evt.get("id") if isinstance(evt, dict) else getattr(evt, "id", None)
                    break
            if trigger_event_id:
                break
    except Exception as e:
        return None, f"Failed to find trigger event: {e}"

    # Find target BC and invoke command
    try:
        for bc in ctx.bounded_contexts:
            bc_name = bc.get("name") if isinstance(bc, dict) else getattr(bc, "name", "")
            bc_id = bc.get("id") if isinstance(bc, dict) else getattr(bc, "id", None)
            if bc_name == pol.target_bc or bc_id == pol.target_bc:
                target_bc_id = bc_id
                for agg in ctx.aggregates_by_bc.get(bc_id, []):
                    agg_id = agg.get("id") if isinstance(agg, dict) else getattr(agg, "id", None)
                    for cmd in ctx.commands_by_agg.get(agg_id, []):
                        cmd_name = cmd.get("name") if isinstance(cmd, dict) else getattr(cmd, "name", "")
                        if cmd_name == pol.invoke_command:
                            invoke_command_id = cmd.get("id") if isinstance(cmd, dict) else getattr(cmd, "id", None)
                            break
                    if invoke_command_id:
                        break
                if invoke_command_id:
                    break
    except Exception as e:
        return None, f"Failed to find target BC/command: {e}"

    if not trigger_event_id:
        return None, f"Trigger event '{pol.trigger_event}' not found"
    
    if not invoke_command_id:
        return None, f"Invoke command '{pol.invoke_command}' not found in target BC '{pol.target_bc}'"
    
    if not target_bc_id:
        return None, f"Target BC '{pol.target_bc}' not found"

    pol_display_name = getattr(pol, "displayName", None) or pol.name
    # Create policy
    try:
        created_pol = await asyncio.wait_for(
            asyncio.to_thread(
                ctx.client.create_policy,
                name=pol.name,
                bc_id=target_bc_id,
                trigger_event_id=trigger_event_id,
                invoke_command_id=invoke_command_id,
                description=pol.description,
                display_name=pol_display_name,
            ),
            timeout=8.0
        )
        
        # Overwrite LLM-proposed id with UUID from DB
        try:
            pol.id = created_pol.get("id")
            pol.invoke_command_id = invoke_command_id
        except Exception:
            pass

        # Link user stories (batch processing)
        us_ids = getattr(pol, "user_story_ids", []) or []
        if us_ids:
            link_tasks = []
            for us_id in us_ids:
                link_task = asyncio.wait_for(
                    asyncio.to_thread(
                        ctx.client.link_user_story_to_policy,
                        us_id,
                        created_pol.get("id")
                    ),
                    timeout=5.0
                )
                link_tasks.append(link_task)
            
            # Process in batches of 5
            BATCH_SIZE = 5
            for batch_start in range(0, len(link_tasks), BATCH_SIZE):
                batch = link_tasks[batch_start:batch_start + BATCH_SIZE]
                try:
                    await asyncio.gather(*batch, return_exceptions=True)
                except Exception:
                    pass  # Individual failures are ignored

        return {
            "policy": created_pol,
            "pol": pol,
            "target_bc_id": target_bc_id,
            "invoke_command_id": invoke_command_id,
        }, None
    except asyncio.TimeoutError:
        return None, "Policy creation timeout"
    except Exception as e:
        return None, f"Policy creation failed: {e}"


async def identify_policies_phase(ctx: IngestionWorkflowContext) -> AsyncGenerator[ProgressEvent, None]:
    """
    Phase 7: identify policies using LLM and create them with TRIGGERS/INVOKES relationships.
    Supports chunking for large events/commands lists.
    """
    PHASE_START = 75
    PHASE_END = 85
    MERGE_RATIO = 0.1
    
    # Check cancellation at phase start
    if getattr(ctx.session, "is_cancelled", False):
        yield ProgressEvent(
            phase=IngestionPhase.ERROR,
            message="❌ 생성이 중단되었습니다",
            progress=getattr(ctx.session, "progress", 0) or 0,
            data={"error": "Cancelled by user", "cancelled": True},
        )
        return
    
    # Phase 시작
    yield ProgressEvent(
        phase=IngestionPhase.IDENTIFYING_POLICIES,
        message="Policy 식별 시작...",
        progress=PHASE_START
    )
    
    try:
        # Build user stories text for LLM context
        user_stories_text = "\n".join(
            [f"[{us.id}] As a {us.role}, I want to {us.action}" for us in ctx.user_stories]
        )

        # Build events list with BC info and user_story_ids for cross-BC policy identification
        all_events_list: list[str] = []
        for bc in ctx.bounded_contexts:
            bc_id = bc.get("id") if isinstance(bc, dict) else getattr(bc, "id", None)
            bc_name = bc.get("name") if isinstance(bc, dict) else getattr(bc, "name", "")
            for agg in ctx.aggregates_by_bc.get(bc_id, []):
                agg_id = agg.get("id") if isinstance(agg, dict) else getattr(agg, "id", None)
                for evt in ctx.events_by_agg.get(agg_id, []):
                    evt_name = evt.get("name") if isinstance(evt, dict) else getattr(evt, "name", "")
                    evt_desc = evt.get("description") if isinstance(evt, dict) else getattr(evt, "description", "")
                    us_ids = evt.get("user_story_ids", []) if isinstance(evt, dict) else getattr(evt, "user_story_ids", []) or []
                    us_ids_str = ", ".join(us_ids) if us_ids else "none"
                    all_events_list.append(
                        f"- {evt_name} (from {bc_name}, user_stories: [{us_ids_str}]): {evt_desc}"
                    )
        events_text = "\n".join(all_events_list)

        commands_by_bc: dict[str, str] = {}
        for bc in ctx.bounded_contexts:
            bc_id = bc.get("id") if isinstance(bc, dict) else getattr(bc, "id", None)
            bc_name = bc.get("name") if isinstance(bc, dict) else getattr(bc, "name", "")
            bc_cmds: list[str] = []
            for agg in ctx.aggregates_by_bc.get(bc_id, []):
                agg_id = agg.get("id") if isinstance(agg, dict) else getattr(agg, "id", None)
                for cmd in ctx.commands_by_agg.get(agg_id, []):
                    cmd_name = cmd.get("name") if isinstance(cmd, dict) else getattr(cmd, "name", "")
                    bc_cmds.append(f"- {cmd_name}")
            commands_by_bc[bc_name] = "\n".join(bc_cmds) if bc_cmds else "No commands"

        commands_text = "\n".join([f"{bc_name}:\n{cmds}" for bc_name, cmds in commands_by_bc.items()])
        bc_text = "\n".join([
            f"- {bc.get('name') if isinstance(bc, dict) else getattr(bc, 'name', '')}: {bc.get('description') if isinstance(bc, dict) else getattr(bc, 'description', '')}"
            for bc in ctx.bounded_contexts
        ])

        display_lang = getattr(ctx, "display_language", "ko") or "ko"
        display_name_tail = (
            "\n\nFor each Policy output displayName: a short UI label in Korean (e.g. '주문 취소 시 환불')."
            if display_lang == "ko"
            else "\n\nFor each Policy output displayName: a short UI label in English (e.g. 'Refund on Order Cancelled')."
        )
        # 전체 프롬프트 텍스트 구성 (청킹 판단용)
        full_prompt_text = IDENTIFY_POLICIES_PROMPT.format(
            user_stories=user_stories_text,
            events=events_text,
            commands_by_bc=commands_text,
            bounded_contexts=bc_text,
        ) + display_name_tail
        _report_context_tail = ""
        if ctx.source_report:
            from api.features.ingestion.workflow.utils.report_context import get_policies_context
            _report_context_tail = "\n\n" + get_policies_context(ctx.source_report)
        full_prompt_text += _report_context_tail

        # 청킹 필요 여부 판단
        if should_chunk(full_prompt_text):
            yield ProgressEvent(
                phase=IngestionPhase.IDENTIFYING_POLICIES,
                message="대용량 Events/Commands 스캐닝 중...",
                progress=PHASE_START + 1
            )
            
            # 프롬프트를 청크로 분할 (events_text가 가장 클 가능성이 높음)
            chunks = split_text_with_overlap(events_text)
            total_chunks = len(chunks)
            
            yield ProgressEvent(
                phase=IngestionPhase.IDENTIFYING_POLICIES,
                message=f"Events를 {total_chunks}개 청크로 분할 완료",
                progress=PHASE_START + 2
            )
            
            chunk_results = []
            
            for i, (chunk_events_text, start_char, end_char) in enumerate(chunks):
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
                    phase=IngestionPhase.IDENTIFYING_POLICIES,
                    message=f"청크 {i+1}/{total_chunks} 처리 중... ({start_char:,}~{end_char:,} 문자)",
                    progress=chunk_progress
                )
                
                # 청크별 프롬프트 구성
                chunk_prompt = IDENTIFY_POLICIES_PROMPT.format(
                    user_stories=user_stories_text,
                    events=chunk_events_text,
                    commands_by_bc=commands_text,
                    bounded_contexts=bc_text,
                ) + display_name_tail + _report_context_tail

                structured_llm = ctx.llm.with_structured_output(PolicyList)
                
                provider, model = get_llm_provider_model()
                
                # LLM 호출 전 진행 상황 업데이트
                llm_start_progress = calculate_chunk_progress(
                    PHASE_START + 2,
                    PHASE_END - int((PHASE_END - PHASE_START) * MERGE_RATIO),
                    i,
                    total_chunks,
                    merge_progress_ratio=0.3  # LLM 호출 시작 시점
                )
                yield ProgressEvent(
                    phase=IngestionPhase.IDENTIFYING_POLICIES,
                    message=f"청크 {i+1}/{total_chunks} LLM 분석 중...",
                    progress=llm_start_progress
                )
                
                t_llm0 = time.perf_counter()
                try:
                    # LLM 호출에 타임아웃 추가 (5분)
                    pol_response = await asyncio.wait_for(
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
                        f"Ingestion: identify policies (chunk {i+1}/{total_chunks}) - LLM invoke timeout (>{llm_ms}ms).",
                        category="ingestion.llm.identify_policies.timeout",
                        params={
                            "session_id": ctx.session.id,
                            "llm": {"provider": provider, "model": model},
                            "chunk_index": i + 1,
                            "total_chunks": total_chunks,
                            "llm_ms": llm_ms,
                        }
                    )
                    # Skip this chunk and continue with next
                    chunk_results.append([])
                    # 청크 처리 완료
                    chunk_complete_progress = calculate_chunk_progress(
                        PHASE_START + 2,
                        PHASE_END - int((PHASE_END - PHASE_START) * MERGE_RATIO),
                        i + 1,
                        total_chunks,
                        merge_progress_ratio=0
                    )
                    yield ProgressEvent(
                        phase=IngestionPhase.IDENTIFYING_POLICIES,
                        message=f"청크 {i+1}/{total_chunks} LLM 타임아웃, 다음 청크로 진행...",
                        progress=chunk_complete_progress
                    )
                    continue
                except Exception as llm_error:
                    llm_ms = int((time.perf_counter() - t_llm0) * 1000)
                    SmartLogger.log(
                        "ERROR",
                        f"Ingestion: identify policies (chunk {i+1}/{total_chunks}) - LLM invoke failed.",
                        category="ingestion.llm.identify_policies.error",
                        params={
                            "session_id": ctx.session.id,
                            "llm": {"provider": provider, "model": model},
                            "chunk_index": i + 1,
                            "total_chunks": total_chunks,
                            "llm_ms": llm_ms,
                            "error": str(llm_error),
                            "error_type": type(llm_error).__name__,
                        }
                    )
                    # Skip this chunk and continue with next
                    chunk_results.append([])
                    # 청크 처리 완료
                    chunk_complete_progress = calculate_chunk_progress(
                        PHASE_START + 2,
                        PHASE_END - int((PHASE_END - PHASE_START) * MERGE_RATIO),
                        i + 1,
                        total_chunks,
                        merge_progress_ratio=0
                    )
                    yield ProgressEvent(
                        phase=IngestionPhase.IDENTIFYING_POLICIES,
                        message=f"청크 {i+1}/{total_chunks} LLM 호출 실패, 다음 청크로 진행...",
                        progress=chunk_complete_progress
                    )
                    continue
                
                # LLM 호출 완료 후 진행 상황 업데이트
                llm_complete_progress = calculate_chunk_progress(
                    PHASE_START + 2,
                    PHASE_END - int((PHASE_END - PHASE_START) * MERGE_RATIO),
                    i,
                    total_chunks,
                    merge_progress_ratio=0.8  # LLM 호출 완료 시점
                )
                yield ProgressEvent(
                    phase=IngestionPhase.IDENTIFYING_POLICIES,
                    message=f"청크 {i+1}/{total_chunks} LLM 분석 완료, 결과 처리 중...",
                    progress=llm_complete_progress
                )
                
                # Check cancellation after chunk processing
                if getattr(ctx.session, "is_cancelled", False):
                    yield ProgressEvent(
                        phase=IngestionPhase.ERROR,
                        message="❌ 생성이 중단되었습니다",
                        progress=getattr(ctx.session, "progress", 0) or 0,
                        data={"error": "Cancelled by user", "cancelled": True},
                    )
                    return
                
                policies = getattr(pol_response, "policies", []) or []
                chunk_results.append(policies)
                
                # 청크 처리 완료
                chunk_complete_progress = calculate_chunk_progress(
                    PHASE_START + 2,
                    PHASE_END - int((PHASE_END - PHASE_START) * MERGE_RATIO),
                    i + 1,
                    total_chunks,
                    merge_progress_ratio=0
                )
                yield ProgressEvent(
                    phase=IngestionPhase.IDENTIFYING_POLICIES,
                    message=f"청크 {i+1}/{total_chunks} 완료 ({len(policies)}개 Policy 식별)",
                    progress=chunk_complete_progress
                )
            
            # 결과 병합 시작
            yield ProgressEvent(
                phase=IngestionPhase.IDENTIFYING_POLICIES,
                message=f"{total_chunks}개 청크 결과 병합 중...",
                progress=PHASE_END - 3
            )
            
            # 결과 병합 (중복 제거: key 우선, 없으면 name, 둘 다 없으면 id)
            policies = merge_chunk_results(
                chunk_results,
                dedupe_key=lambda p: (
                    getattr(p, "key", None) or 
                    getattr(p, "name", None) or 
                    getattr(p, "id", None) or 
                    f"__fallback_{id(p)}"  # 최후의 수단: 객체 ID
                )
            )
            ctx.policies = policies
            
            # 결과 병합 완료
            yield ProgressEvent(
                phase=IngestionPhase.IDENTIFYING_POLICIES,
                message=f"Policy 식별 완료 (총 {len(policies)}개)",
                progress=PHASE_END - 2
            )
        else:
            # 기존 로직 (청킹 불필요)
            yield ProgressEvent(
                phase=IngestionPhase.IDENTIFYING_POLICIES,
                message="Policy 식별 준비 중...",
                progress=PHASE_START + 3
            )
            
            prompt = full_prompt_text
            structured_llm = ctx.llm.with_structured_output(PolicyList)

            try:
                provider, model = get_llm_provider_model()

                # LLM 호출 전 진행 상황 업데이트
                yield ProgressEvent(
                    phase=IngestionPhase.IDENTIFYING_POLICIES,
                    message="LLM 분석 중... (이 작업은 시간이 걸릴 수 있습니다)",
                    progress=PHASE_START + 5
                )

                t_llm0 = time.perf_counter()
                try:
                    # LLM 호출에 타임아웃 추가 (5분)
                    pol_response = await asyncio.wait_for(
                        asyncio.to_thread(
                            structured_llm.invoke,
                            [SystemMessage(content=SYSTEM_PROMPT), HumanMessage(content=prompt)]
                        ),
                        timeout=300.0  # 5분 타임아웃
                    )
                    llm_ms = int((time.perf_counter() - t_llm0) * 1000)
                except asyncio.TimeoutError:
                    llm_ms = int((time.perf_counter() - t_llm0) * 1000)
                    SmartLogger.log(
                        "ERROR",
                        f"Ingestion: identify policies - LLM invoke timeout (>{llm_ms}ms).",
                        category="ingestion.llm.identify_policies.timeout",
                        params={
                            "session_id": ctx.session.id,
                            "llm": {"provider": provider, "model": model},
                            "llm_ms": llm_ms,
                        }
                    )
                    raise  # Re-raise to be caught by outer try-except
                except Exception as llm_error:
                    llm_ms = int((time.perf_counter() - t_llm0) * 1000)
                    SmartLogger.log(
                        "ERROR",
                        "Ingestion: identify policies - LLM invoke failed.",
                        category="ingestion.llm.identify_policies.error",
                        params={
                            "session_id": ctx.session.id,
                            "llm": {"provider": provider, "model": model},
                            "llm_ms": llm_ms,
                            "error": str(llm_error),
                            "error_type": type(llm_error).__name__,
                        }
                    )
                    raise  # Re-raise to be caught by outer try-except
                
                # LLM 호출 완료 후 진행 상황 업데이트
                yield ProgressEvent(
                    phase=IngestionPhase.IDENTIFYING_POLICIES,
                    message="LLM 분석 완료, 결과 처리 중...",
                    progress=PHASE_START + 7
                )
                policies = getattr(pol_response, "policies", []) or []
            except Exception as e:
                SmartLogger.log(
                    "ERROR",
                    "Policy identification failed (LLM)",
                    category="ingestion.workflow.policies",
                    params={"session_id": ctx.session.id, "error": str(e)},
                )
                policies = []

            ctx.policies = policies
            
            yield ProgressEvent(
                phase=IngestionPhase.IDENTIFYING_POLICIES,
                message=f"Policy 식별 완료 (총 {len(policies)}개)",
                progress=PHASE_END - 2
            )
        
        # policies는 위에서 ctx.policies에 저장됨
        policies = ctx.policies
        
        # Policy 생성 단계 시작 - 병렬 처리
        if policies:
            yield ProgressEvent(
                phase=IngestionPhase.IDENTIFYING_POLICIES,
                message=f"{len(policies)}개 Policy 생성 시작...",
                progress=PHASE_END - 1
            )
            
            # Check cancellation before parallel processing
            if getattr(ctx.session, "is_cancelled", False):
                yield ProgressEvent(
                    phase=IngestionPhase.ERROR,
                    message="❌ 생성이 중단되었습니다",
                    progress=getattr(ctx.session, "progress", 0) or 0,
                    data={"error": "Cancelled by user", "cancelled": True},
                )
                return
            
            # Process all policies in parallel
            tasks = []
            for pol_idx, pol in enumerate(policies):
                tasks.append(_create_policy_with_links(pol, pol_idx, len(policies), ctx))
            
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Process results and yield progress events
            created_count = 0
            for pol_idx, result in enumerate(results):
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
                        f"Policy creation exception: {result}",
                        category="ingestion.neo4j.policy.create.error",
                        params={"session_id": ctx.session.id, "policy_index": pol_idx + 1, "error": str(result)}
                    )
                    continue
                
                created_pol_data, error = result
                if error:
                    SmartLogger.log(
                        "ERROR",
                        f"Policy creation failed: {error}",
                        category="ingestion.workflow.policies.skip",
                        params={"session_id": ctx.session.id, "policy_index": pol_idx + 1, "error": error}
                    )
                    continue
                
                if created_pol_data:
                    created_count += 1
                    created_pol = created_pol_data["policy"]
                    pol = created_pol_data["pol"]
                    target_bc_id = created_pol_data["target_bc_id"]
                    invoke_command_id = created_pol_data["invoke_command_id"]
                    
                    yield ProgressEvent(
                        phase=IngestionPhase.IDENTIFYING_POLICIES,
                        message=f"Policy 생성 완료: {pol.name} ({created_count}/{len(policies)})",
                        progress=PHASE_END - 1 + int((85 - (PHASE_END - 1)) * created_count / max(len(policies), 1)),
                        data={
                            "type": "Policy",
                            "object": {
                                "id": created_pol.get("id"),
                                "name": pol.name,
                                "type": "Policy",
                                "parentId": target_bc_id,
                                "invokeCommandId": invoke_command_id,
                            },
                        },
                    )
        
        # Policy 생성 완료
        if policies:
            yield ProgressEvent(
                phase=IngestionPhase.IDENTIFYING_POLICIES,
                message=f"Policy 식별 및 생성 완료 (총 {len(policies)}개)",
                progress=PHASE_END
            )
        else:
            yield ProgressEvent(
                phase=IngestionPhase.IDENTIFYING_POLICIES,
                message="Policy 식별 완료 (생성된 Policy 없음)",
                progress=PHASE_END
            )
    
    except Exception as e:
        SmartLogger.log(
            "ERROR",
            f"Policy identification phase failed: {e}",
            category="ingestion.workflow.policies.phase_error",
            params={
                "session_id": ctx.session.id,
                "error": str(e),
                "error_type": type(e).__name__,
            },
        )
        yield ProgressEvent(
            phase=IngestionPhase.ERROR,
            message=f"❌ Policy 식별 중 오류 발생: {str(e)}",
            progress=getattr(ctx.session, "progress", 0) or PHASE_START,
            data={"error": str(e), "error_type": type(e).__name__},
        )


