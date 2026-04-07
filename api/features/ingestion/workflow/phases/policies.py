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


def _fuzzy_match(query: str, candidates: list[tuple[str, str, Any]]) -> str | None:
    """
    query를 candidates [(name, displayName, obj)] 중에서 매칭.
    1순위: name 정확 일치
    2순위: displayName 정확 일치
    3순위: name/displayName 대소문자 무시 일치
    4순위: name/displayName에 query가 포함되거나 query에 name이 포함
    Returns: 매칭된 obj의 id 또는 None
    """
    q = query.strip()
    q_lower = q.lower()

    # 1순위: name 정확 일치
    for name, display_name, obj in candidates:
        if name == q:
            return obj.get("id") if isinstance(obj, dict) else getattr(obj, "id", None)

    # 2순위: displayName 정확 일치
    for name, display_name, obj in candidates:
        if display_name and display_name == q:
            return obj.get("id") if isinstance(obj, dict) else getattr(obj, "id", None)

    # 3순위: 대소문자 무시
    for name, display_name, obj in candidates:
        if name.lower() == q_lower or (display_name and display_name.lower() == q_lower):
            return obj.get("id") if isinstance(obj, dict) else getattr(obj, "id", None)

    # 4순위: 포함 관계 (한글↔영문 혼용 대응)
    for name, display_name, obj in candidates:
        if q_lower in name.lower() or name.lower() in q_lower:
            return obj.get("id") if isinstance(obj, dict) else getattr(obj, "id", None)
        if display_name and (q_lower in display_name.lower() or display_name.lower() in q_lower):
            return obj.get("id") if isinstance(obj, dict) else getattr(obj, "id", None)

    return None


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

    # Build event candidates for fuzzy matching — Neo4j에서 전체 Event 조회
    event_candidates: list[tuple[str, str, Any]] = []
    try:
        with ctx.client.session() as _s:
            for rec in _s.run("MATCH (evt:Event) RETURN evt {.id, .name, .displayName} AS e"):
                e = dict(rec["e"])
                event_candidates.append((e.get("name", ""), e.get("displayName", ""), e))
    except Exception as e:
        # fallback: events_by_agg 사용
        for events in ctx.events_by_agg.values():
            for evt in events:
                name = evt.get("name") if isinstance(evt, dict) else getattr(evt, "name", "")
                display = evt.get("displayName") if isinstance(evt, dict) else getattr(evt, "displayName", "")
                event_candidates.append((name, display or "", evt))

    trigger_event_id = _fuzzy_match(pol.trigger_event, event_candidates)

    # Find target BC and invoke command (with fuzzy matching)
    try:
        # BC matching: exact name, then case-insensitive
        for bc in ctx.bounded_contexts:
            bc_name = bc.get("name") if isinstance(bc, dict) else getattr(bc, "name", "")
            bc_display = bc.get("displayName") if isinstance(bc, dict) else getattr(bc, "displayName", "")
            bc_id = bc.get("id") if isinstance(bc, dict) else getattr(bc, "id", None)
            target_name = pol.target_bc.strip()
            if bc_name == target_name or bc_id == target_name or bc_name.lower() == target_name.lower() or (bc_display and bc_display == target_name):
                target_bc_id = bc_id
                # Build command candidates for this BC
                cmd_candidates: list[tuple[str, str, Any]] = []
                for agg in ctx.aggregates_by_bc.get(bc_id, []):
                    agg_id = agg.get("id") if isinstance(agg, dict) else getattr(agg, "id", None)
                    for cmd in ctx.commands_by_agg.get(agg_id, []):
                        cmd_name = cmd.get("name") if isinstance(cmd, dict) else getattr(cmd, "name", "")
                        cmd_display = cmd.get("displayName") if isinstance(cmd, dict) else getattr(cmd, "displayName", "")
                        cmd_candidates.append((cmd_name, cmd_display or "", cmd))

                invoke_command_id = _fuzzy_match(pol.invoke_command, cmd_candidates)
                if invoke_command_id:
                    break

        # BC not found by exact match — try fuzzy on all BCs
        if not target_bc_id:
            bc_candidates = [(
                bc.get("name") if isinstance(bc, dict) else getattr(bc, "name", ""),
                bc.get("displayName") if isinstance(bc, dict) else getattr(bc, "displayName", ""),
                bc,
            ) for bc in ctx.bounded_contexts]
            matched_bc_id = _fuzzy_match(pol.target_bc, bc_candidates)
            if matched_bc_id:
                target_bc_id = matched_bc_id
                cmd_candidates = []
                for agg in ctx.aggregates_by_bc.get(target_bc_id, []):
                    agg_id = agg.get("id") if isinstance(agg, dict) else getattr(agg, "id", None)
                    for cmd in ctx.commands_by_agg.get(agg_id, []):
                        cmd_name = cmd.get("name") if isinstance(cmd, dict) else getattr(cmd, "name", "")
                        cmd_display = cmd.get("displayName") if isinstance(cmd, dict) else getattr(cmd, "displayName", "")
                        cmd_candidates.append((cmd_name, cmd_display or "", cmd))
                invoke_command_id = _fuzzy_match(pol.invoke_command, cmd_candidates)

        # Neo4j fallback: commands_by_agg에 없으면 Neo4j에서 해당 BC의 Command 직접 조회
        if target_bc_id and not invoke_command_id:
            try:
                with ctx.client.session() as _cmd_s:
                    _cmd_q = """
                    MATCH (bc:BoundedContext {id: $bc_id})-[:HAS_AGGREGATE]->(agg:Aggregate)-[:HAS_COMMAND]->(cmd:Command)
                    RETURN cmd {.id, .name, .displayName} AS c
                    """
                    neo4j_cmd_candidates = []
                    for rec in _cmd_s.run(_cmd_q, bc_id=target_bc_id):
                        c = dict(rec["c"])
                        neo4j_cmd_candidates.append((c.get("name", ""), c.get("displayName", ""), c))
                    if neo4j_cmd_candidates:
                        invoke_command_id = _fuzzy_match(pol.invoke_command, neo4j_cmd_candidates)
            except Exception:
                pass  # 기존 로직으로 진행
    except Exception as e:
        return None, f"Failed to find target BC/command: {e}"

    if not trigger_event_id:
        return None, f"Trigger event '{pol.trigger_event}' not found (fuzzy match failed)"

    if not invoke_command_id:
        return None, f"Invoke command '{pol.invoke_command}' not found in target BC '{pol.target_bc}'"

    if not target_bc_id:
        return None, f"Target BC '{pol.target_bc}' not found"

    # ── Same-BC Policy 정보 로그 (차단하지 않음) ──
    # 이벤트 모델링에서 same-BC 내 Event→Command 반응형 흐름도
    # 연결선으로 표현되어야 하므로 same-BC Policy도 허용.
    try:
        with ctx.client.session() as _sbc_sess:
            _sbc_rec = _sbc_sess.run(
                "MATCH (bc:BoundedContext)-[:HAS_EVENT]->(evt:Event {id: $evt_id}) "
                "RETURN bc.id AS bcId, bc.name AS bcName LIMIT 1",
                evt_id=trigger_event_id,
            ).single()
            if _sbc_rec and _sbc_rec["bcId"] == target_bc_id:
                SmartLogger.log(
                    "INFO",
                    f"Same-BC Policy: '{pol.name}' — trigger event "
                    f"'{pol.trigger_event}' and invoke command in same BC "
                    f"'{_sbc_rec['bcName']}'. Intra-BC reactive flow.",
                    category="ingestion.workflow.policies.same_bc_info",
                    params={
                        "session_id": ctx.session.id,
                        "policy_name": pol.name,
                        "bc_name": _sbc_rec["bcName"],
                    },
                )
    except Exception:
        pass

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

        # Build events list — Neo4j에서 BC별 모든 Event 직접 조회 (events_by_agg EMITS 의존 제거)
        all_events_list: list[str] = []
        _all_events_for_matching: list[dict] = []  # fuzzy match용
        try:
            with ctx.client.session() as _evt_session:
                _evt_query = """
                MATCH (bc:BoundedContext)-[:HAS_EVENT]->(evt:Event)
                RETURN bc.name AS bcName, evt.id AS evtId, evt.name AS evtName,
                       evt.displayName AS evtDisplayName, evt.description AS evtDesc
                ORDER BY bc.name, evt.name
                """
                for rec in _evt_session.run(_evt_query):
                    bc_name = rec["bcName"] or ""
                    evt_name = rec["evtName"] or ""
                    evt_display = rec["evtDisplayName"] or ""
                    evt_desc = rec["evtDesc"] or ""
                    label = evt_display or evt_name
                    all_events_list.append(f"- {label} (from {bc_name}): {evt_desc}")
                    _all_events_for_matching.append({
                        "id": rec["evtId"], "name": evt_name, "displayName": evt_display,
                    })
        except Exception as e:
            SmartLogger.log("ERROR", f"Failed to fetch events for policy phase: {e}",
                           category="ingestion.workflow.policies.event_fetch_error",
                           params={"session_id": ctx.session.id, "error": str(e)})

        # events_by_agg 기반 이벤트도 보충 (fallback 1)
        seen_evt_names = {line.split("(from")[0].strip("- ").strip() for line in all_events_list}
        for bc in ctx.bounded_contexts:
            bc_id = bc.get("id") if isinstance(bc, dict) else getattr(bc, "id", None)
            bc_name = bc.get("name") if isinstance(bc, dict) else getattr(bc, "name", "")
            for agg in ctx.aggregates_by_bc.get(bc_id, []):
                agg_id = agg.get("id") if isinstance(agg, dict) else getattr(agg, "id", None)
                for evt in ctx.events_by_agg.get(agg_id, []):
                    evt_name = evt.get("name") if isinstance(evt, dict) else getattr(evt, "name", "")
                    evt_display = evt.get("displayName") if isinstance(evt, dict) else getattr(evt, "displayName", "")
                    label = evt_display or evt_name
                    if label not in seen_evt_names:
                        evt_desc = evt.get("description") if isinstance(evt, dict) else getattr(evt, "description", "")
                        all_events_list.append(f"- {label} (from {bc_name}): {evt_desc}")
                        seen_evt_names.add(label)
                        _all_events_for_matching.append({
                            "id": evt.get("id") if isinstance(evt, dict) else getattr(evt, "id", None),
                            "name": evt_name, "displayName": evt_display,
                        })

        # 최종 fallback 2: BC→HAS_EVENT, events_by_agg 모두 비어있으면 Neo4j에서 전체 Event 직접 조회
        if not all_events_list:
            SmartLogger.log("WARN", "Policy phase: primary & fallback-1 returned no events — trying direct Event query",
                           category="ingestion.workflow.policies.fallback_direct_event",
                           params={"session_id": ctx.session.id})
            try:
                with ctx.client.session() as _fallback_session:
                    _fallback_query = """
                    MATCH (evt:Event)
                    OPTIONAL MATCH (bc:BoundedContext)-[:HAS_EVENT]->(evt)
                    OPTIONAL MATCH (us:UserStory)-[:HAS_EVENT]->(evt)
                    OPTIONAL MATCH (us)-[:IMPLEMENTS]->(us_bc:BoundedContext)
                    RETURN evt.id AS evtId, evt.name AS evtName,
                           evt.displayName AS evtDisplayName, evt.description AS evtDesc,
                           COALESCE(bc.name, us_bc.name, 'Unknown') AS bcName
                    ORDER BY bcName, evt.name
                    """
                    for rec in _fallback_session.run(_fallback_query):
                        evt_name = rec["evtName"] or ""
                        evt_display = rec["evtDisplayName"] or ""
                        evt_desc = rec["evtDesc"] or ""
                        bc_name = rec["bcName"] or "Unknown"
                        label = evt_display or evt_name
                        if label not in seen_evt_names:
                            all_events_list.append(f"- {label} (from {bc_name}): {evt_desc}")
                            seen_evt_names.add(label)
                            _all_events_for_matching.append({
                                "id": rec["evtId"], "name": evt_name, "displayName": evt_display,
                            })
                SmartLogger.log("INFO", f"Policy phase fallback: found {len(all_events_list)} events via direct query",
                               category="ingestion.workflow.policies.fallback_direct_event",
                               params={"session_id": ctx.session.id, "events_count": len(all_events_list)})
            except Exception as e:
                SmartLogger.log("ERROR", f"Policy phase fallback event query failed: {e}",
                               category="ingestion.workflow.policies.fallback_direct_event_error",
                               params={"session_id": ctx.session.id, "error": str(e)})

        events_text = "\n".join(all_events_list)

        SmartLogger.log("INFO", f"Policy phase: {len(all_events_list)} events, {len(ctx.bounded_contexts)} BCs collected for prompt",
                       category="ingestion.workflow.policies.context",
                       params={"session_id": ctx.session.id, "events_count": len(all_events_list)})

        if not all_events_list:
            SmartLogger.log("WARN", "Policy phase: no events found — skipping LLM call",
                           category="ingestion.workflow.policies.no_events",
                           params={"session_id": ctx.session.id,
                                   "events_by_agg_count": sum(len(v) for v in ctx.events_by_agg.values()),
                                   "bounded_contexts": len(ctx.bounded_contexts)})
            yield ProgressEvent(
                phase=IngestionPhase.IDENTIFYING_POLICIES,
                message="Policy 식별 완료 (이벤트 없음 — 생성된 Policy 없음)",
                progress=PHASE_END
            )
            return

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
        # ── EMITS 없는 Command 목록 추가 (Policy invoke 후보 힌트) ──
        _no_emits_hint = ""
        try:
            with ctx.client.session() as _ne_sess:
                _ne_result = _ne_sess.run(
                    """
                    MATCH (bc:BoundedContext)-[:HAS_AGGREGATE]->(:Aggregate)-[:HAS_COMMAND]->(cmd:Command)
                    WHERE NOT (cmd)-[:EMITS]->(:Event)
                    RETURN cmd.name AS cmdName, bc.name AS bcName
                    ORDER BY bc.name, cmd.name
                    """
                )
                _no_emits_cmds = [(r["cmdName"], r["bcName"]) for r in _ne_result]
                if _no_emits_cmds:
                    _lines = [f"- {cn} (BC: {bn})" for cn, bn in _no_emits_cmds]
                    _no_emits_hint = (
                        "\n\n<commands_without_emits>\n"
                        "These Commands have no direct user-triggered Events yet. "
                        "They are strong candidates for Policy invoke targets — "
                        "i.e., Commands that should be triggered reactively by Events "
                        "from OTHER BCs rather than by direct user action:\n"
                        + "\n".join(_lines)
                        + "\nConsider creating Policies that invoke these Commands "
                        "when relevant Events occur in other BCs."
                        "\n</commands_without_emits>"
                    )
        except Exception:
            pass

        # 전체 프롬프트 텍스트 구성 (청킹 판단용)
        full_prompt_text = IDENTIFY_POLICIES_PROMPT.format(
            user_stories=user_stories_text,
            events=events_text,
            commands_by_bc=commands_text,
            bounded_contexts=bc_text,
        ) + display_name_tail + _no_emits_hint
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
            _accumulated_policy_names: list[str] = []

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
                ) + display_name_tail
                # 이전 청크에서 식별된 Policy 이름 전달 — 중복 생성 방지
                if _accumulated_policy_names:
                    from api.features.ingestion.workflow.utils.chunking import format_accumulated_names
                    chunk_prompt += (
                        "\n\n## ALREADY IDENTIFIED POLICIES (from previous chunks)\n"
                        "The following Policies have already been identified. "
                        "Do NOT create duplicate Policies with the same or very similar trigger_event → invoke_command mapping.\n"
                        "Already identified: " + format_accumulated_names(_accumulated_policy_names)
                    )

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

                # 이 청크에서 식별된 Policy 이름을 누적 (다음 청크 전달용)
                for pol in policies:
                    pol_name = getattr(pol, "name", "")
                    if pol_name and pol_name not in _accumulated_policy_names:
                        _accumulated_policy_names.append(pol_name)

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

        # ── Self-loop 검증: trigger_event와 invoke_command가 같은 Event를 발생시키는 Policy 제거 ──
        # Event→Command 매핑: 어떤 Command가 어떤 Event를 emit하는지 수집
        command_to_events: dict[str, set[str]] = {}
        for agg_id, events in (ctx.events_by_agg or {}).items():
            for evt in events:
                evt_name = evt.get("name") if isinstance(evt, dict) else getattr(evt, "name", "")
                emitting_cmd = evt.get("emittingCommandName") if isinstance(evt, dict) else getattr(evt, "emitting_command_name", None)
                if not emitting_cmd:
                    emitting_cmd = evt.get("emitting_command_name") if isinstance(evt, dict) else None
                if emitting_cmd and evt_name:
                    if emitting_cmd not in command_to_events:
                        command_to_events[emitting_cmd] = set()
                    command_to_events[emitting_cmd].add(evt_name)

        # 또한 Neo4j의 Command→EMITS→Event 관계에서도 수집
        for agg_id, cmds in (ctx.commands_by_agg or {}).items():
            for cmd in cmds:
                cmd_name = cmd.get("name") if isinstance(cmd, dict) else getattr(cmd, "name", "")
                cmd_events = cmd.get("events") if isinstance(cmd, dict) else getattr(cmd, "events", None)
                if cmd_events and cmd_name:
                    if cmd_name not in command_to_events:
                        command_to_events[cmd_name] = set()
                    for e in cmd_events:
                        e_name = e.get("name") if isinstance(e, dict) else getattr(e, "name", "") if hasattr(e, "name") else str(e)
                        if e_name:
                            command_to_events[cmd_name].add(e_name)

        valid_policies = []
        removed_self_loops = []
        for pol in policies:
            trigger_event = getattr(pol, "trigger_event", "") or ""
            invoke_command = getattr(pol, "invoke_command", "") or ""
            # invoke_command가 emit하는 Event 목록에 trigger_event가 포함되면 self-loop
            emitted = command_to_events.get(invoke_command, set())
            if trigger_event and trigger_event in emitted:
                removed_self_loops.append(getattr(pol, "name", "unknown"))
                SmartLogger.log(
                    "WARN",
                    f"Policy self-loop removed: {getattr(pol, 'name', '?')} "
                    f"({trigger_event} → {invoke_command} → emits {trigger_event})",
                    category="ingestion.workflow.policy.self_loop_removed",
                    params={
                        "session_id": ctx.session.id,
                        "policy_name": getattr(pol, "name", "unknown"),
                        "trigger_event": trigger_event,
                        "invoke_command": invoke_command,
                        "emitted_events": list(emitted),
                    },
                )
            else:
                valid_policies.append(pol)

        if removed_self_loops:
            SmartLogger.log(
                "INFO",
                f"Removed {len(removed_self_loops)} self-loop Policies: {', '.join(removed_self_loops)}",
                category="ingestion.workflow.policy.self_loop_summary",
                params={"session_id": ctx.session.id, "removed": removed_self_loops},
            )
            policies = valid_policies
            ctx.policies = policies

        # ── Indirect cycle detection (2-hop) ─────────────────────────────
        # Event→Policy→Command→Event 그래프를 구축하고 2-hop 순환을 탐지.
        # A→B→A 순환에서 B 쪽 Policy를 제거 (A 쪽을 유지하여 한 방향만 남김).
        # 먼저 Policy별 trigger→result event 매핑 구축
        pol_trigger_to_results: dict[str, tuple[str, set[str]]] = {}  # pol_name → (trigger_event, {result_events})
        for pol in policies:
            pol_name = getattr(pol, "name", "")
            trigger = getattr(pol, "trigger_event", "") or ""
            invoke_cmd = getattr(pol, "invoke_command", "") or ""
            result_events = command_to_events.get(invoke_cmd, set())
            if trigger and pol_name:
                pol_trigger_to_results[pol_name] = (trigger, result_events)

        # 2-hop 순환 탐지: E1 → P1 → C1 → E2 → P2 → C2 → E1
        cycle_policies_to_remove: set[str] = set()
        for pol1_name, (trigger1, results1) in pol_trigger_to_results.items():
            for mid_event in results1:
                # mid_event를 trigger로 하는 다른 Policy 찾기
                for pol2_name, (trigger2, results2) in pol_trigger_to_results.items():
                    if pol2_name == pol1_name:
                        continue
                    if trigger2 == mid_event and trigger1 in results2:
                        # 순환 발견: trigger1 → pol1 → mid_event → pol2 → trigger1
                        # pol2를 제거 (역방향 Policy)
                        cycle_policies_to_remove.add(pol2_name)
                        SmartLogger.log(
                            "WARN",
                            f"Policy indirect cycle: {trigger1} → {pol1_name} → {mid_event} → {pol2_name} → {trigger1}. Removing {pol2_name}",
                            category="ingestion.workflow.policy.indirect_cycle",
                            params={
                                "session_id": ctx.session.id,
                                "pol1": pol1_name, "pol2": pol2_name,
                                "event1": trigger1, "mid_event": mid_event,
                            },
                        )

        if cycle_policies_to_remove:
            policies = [p for p in policies if getattr(p, "name", "") not in cycle_policies_to_remove]
            ctx.policies = policies
            SmartLogger.log(
                "INFO",
                f"Removed {len(cycle_policies_to_remove)} indirect-cycle Policies: {', '.join(cycle_policies_to_remove)}",
                category="ingestion.workflow.policy.indirect_cycle_summary",
                params={"session_id": ctx.session.id, "removed": list(cycle_policies_to_remove)},
            )

        # ── Duplicate Policy 제거 (동일 trigger→command 매핑) ────────────
        seen_mappings: dict[tuple[str, str], str] = {}  # (trigger, invoke_cmd) → first policy name
        dup_policy_names: list[str] = []
        for pol in policies:
            trigger = getattr(pol, "trigger_event", "") or ""
            invoke_cmd = getattr(pol, "invoke_command", "") or ""
            mapping_key = (trigger, invoke_cmd)
            if mapping_key in seen_mappings:
                dup_policy_names.append(getattr(pol, "name", ""))
                SmartLogger.log(
                    "WARN",
                    f"Duplicate Policy removed: {getattr(pol, 'name', '?')} "
                    f"(same mapping as {seen_mappings[mapping_key]}: {trigger} → {invoke_cmd})",
                    category="ingestion.workflow.policy.duplicate_removed",
                    params={"session_id": ctx.session.id, "removed": getattr(pol, "name", ""), "kept": seen_mappings[mapping_key]},
                )
            else:
                seen_mappings[mapping_key] = getattr(pol, "name", "")

        if dup_policy_names:
            policies = [p for p in policies if getattr(p, "name", "") not in dup_policy_names]
            ctx.policies = policies
            SmartLogger.log(
                "INFO",
                f"Removed {len(dup_policy_names)} duplicate Policies: {', '.join(dup_policy_names)}",
                category="ingestion.workflow.policy.duplicate_summary",
                params={"session_id": ctx.session.id, "removed": dup_policy_names},
            )
        # ── End Policy 후처리 검증 ────────────────────────────────────────

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
        
        # ── Policy invoke Command의 BC 소속 보장 ────────────────────
        # Policy가 INVOKES하는 Command가 어떤 BC의 Aggregate에도 HAS_COMMAND로
        # 연결되지 않은 경우, target_bc의 첫 번째 Aggregate에 자동 연결.
        try:
            with ctx.client.session() as _bc_fix_sess:
                _orphan_cmds = _bc_fix_sess.run(
                    """
                    MATCH (pol:Policy)-[:INVOKES]->(cmd:Command)
                    WHERE NOT (:Aggregate)-[:HAS_COMMAND]->(cmd)
                    MATCH (bc:BoundedContext)-[:HAS_POLICY]->(pol)
                    OPTIONAL MATCH (bc)-[:HAS_AGGREGATE]->(agg:Aggregate)
                    RETURN cmd.id AS cmdId, cmd.name AS cmdName,
                           bc.id AS bcId, bc.name AS bcName,
                           collect(agg.id)[0] AS firstAggId
                    """
                )
                fixed_count = 0
                for rec in _orphan_cmds:
                    agg_id = rec["firstAggId"]
                    if agg_id:
                        _bc_fix_sess.run(
                            "MATCH (agg:Aggregate {id: $agg_id}), (cmd:Command {id: $cmd_id}) "
                            "MERGE (agg)-[:HAS_COMMAND]->(cmd)",
                            agg_id=agg_id, cmd_id=rec["cmdId"],
                        )
                        fixed_count += 1
                        SmartLogger.log(
                            "INFO",
                            f"Auto-linked orphan Command '{rec['cmdName']}' to Aggregate in BC '{rec['bcName']}'",
                            category="ingestion.workflow.policies.cmd_bc_fix",
                            params={
                                "session_id": ctx.session.id,
                                "command_id": rec["cmdId"],
                                "command_name": rec["cmdName"],
                                "bc_name": rec["bcName"],
                                "aggregate_id": agg_id,
                            },
                        )
                    else:
                        SmartLogger.log(
                            "WARN",
                            f"Policy invoke Command '{rec['cmdName']}' has no BC ownership "
                            f"and BC '{rec['bcName']}' has no Aggregates to link to.",
                            category="ingestion.workflow.policies.cmd_bc_orphan",
                            params={
                                "session_id": ctx.session.id,
                                "command_id": rec["cmdId"],
                                "command_name": rec["cmdName"],
                                "bc_name": rec["bcName"],
                            },
                        )
                if fixed_count:
                    SmartLogger.log(
                        "INFO",
                        f"Fixed {fixed_count} orphan Policy-invoke Commands (linked to BC Aggregates)",
                        category="ingestion.workflow.policies.cmd_bc_fix_summary",
                        params={"session_id": ctx.session.id, "fixed_count": fixed_count},
                    )
        except Exception as e:
            SmartLogger.log(
                "WARN",
                f"Policy invoke Command BC fix failed: {e}",
                category="ingestion.workflow.policies.cmd_bc_fix_error",
                params={"session_id": ctx.session.id, "error": str(e)},
            )

        # ── BC 고립 경고: outgoing Policy 없는 비조회 BC 탐지 ──────────
        try:
            with ctx.client.session() as _iso_sess:
                _isolated = _iso_sess.run(
                    """
                    MATCH (bc:BoundedContext)
                    WHERE NOT EXISTS {
                        MATCH (bc)-[:HAS_EVENT]->(e:Event)-[:TRIGGERS]->(:Policy)
                    }
                    AND EXISTS {
                        MATCH (bc)-[:HAS_AGGREGATE]->(:Aggregate)-[:HAS_COMMAND]->(:Command)
                    }
                    RETURN bc.name AS bcName, bc.id AS bcId
                    """
                )
                isolated_bcs = [(r["bcName"], r["bcId"]) for r in _isolated]
                if isolated_bcs:
                    SmartLogger.log(
                        "WARN",
                        f"{len(isolated_bcs)} BCs have Commands but no outgoing Policies "
                        f"(their Events do not trigger any cross-BC flow): "
                        f"{[name for name, _ in isolated_bcs]}",
                        category="ingestion.workflow.policies.bc_isolated",
                        params={
                            "session_id": ctx.session.id,
                            "isolated_bcs": [{"name": n, "id": i} for n, i in isolated_bcs],
                        },
                    )
        except Exception:
            pass

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


