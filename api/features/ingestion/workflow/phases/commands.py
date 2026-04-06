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
from api.features.ingestion.event_storming.nodes import CommandList
from api.features.ingestion.event_storming.prompts import EXTRACT_COMMANDS_PROMPT, SYSTEM_PROMPT
from api.features.ingestion.workflow.ingestion_workflow_context import IngestionWorkflowContext
from api.features.ingestion.workflow.utils.chunking import (
    should_chunk,
    split_text_with_overlap,
    merge_chunk_results,
)
from api.platform.env import get_llm_provider_model
from api.platform.observability.request_logging import summarize_for_log
from api.platform.observability.smart_logger import SmartLogger


async def _create_command_with_links(
    cmd: Any,
    cmd_idx: int,
    total_cmds: int,
    agg: Any,
    ctx: IngestionWorkflowContext,
) -> tuple[dict[str, Any] | None, str]:
    """
    Create a single command with user story links.
    Returns (created_command_dict, error_message)
    """
    # Handle both dict and object formats
    cmd_name = cmd.get("name") if isinstance(cmd, dict) else getattr(cmd, "name", "")
    cmd_display_name = cmd.get("displayName") if isinstance(cmd, dict) else getattr(cmd, "displayName", None)
    if not cmd_display_name:
        cmd_display_name = cmd_name
    cmd_actor = cmd.get("actor") if isinstance(cmd, dict) else getattr(cmd, "actor", "user")
    category = cmd.get("category") if isinstance(cmd, dict) else getattr(cmd, "category", None)
    input_schema = cmd.get("inputSchema") if isinstance(cmd, dict) else getattr(cmd, "inputSchema", None)
    description = cmd.get("description") if isinstance(cmd, dict) else getattr(cmd, "description", None)
    agg_id = agg.get("id") if isinstance(agg, dict) else getattr(agg, "id", None)
    
    try:
        created_cmd = await asyncio.wait_for(
            asyncio.to_thread(
                ctx.client.create_command,
                name=cmd_name,
                aggregate_id=agg_id,
                actor=cmd_actor,
                category=category,
                input_schema=input_schema,
                display_name=cmd_display_name,
                description=description,
            ),
            timeout=10.0
        )
        
        # Overwrite LLM-proposed id with UUID from DB (only if cmd is an object, not dict)
        try:
            if not isinstance(cmd, dict):
                cmd.id = created_cmd.get("id")
                cmd.key = created_cmd.get("key")
        except Exception:
            pass

        # Link user stories (batch processing)
        us_ids = getattr(cmd, "user_story_ids", []) or []
        if us_ids:
            link_tasks = []
            for us_id in us_ids:
                link_task = asyncio.wait_for(
                    asyncio.to_thread(
                        ctx.client.link_user_story_to_command,
                        us_id,
                        created_cmd.get("id")
                    ),
                    timeout=5.0
                )
                link_tasks.append(link_task)
            
            # Process in batches of 10
            BATCH_SIZE = 10
            for batch_start in range(0, len(link_tasks), BATCH_SIZE):
                batch = link_tasks[batch_start:batch_start + BATCH_SIZE]
                try:
                    await asyncio.gather(*batch, return_exceptions=True)
                except Exception:
                    pass  # Individual failures are ignored

        # Link to existing Events via emits_event_names (EMITS relationship)
        emits_names = getattr(cmd, "emits_event_names", []) or []
        if isinstance(cmd, dict):
            emits_names = cmd.get("emits_event_names", []) or []
        for evt_name in emits_names:
            evt_name = (evt_name or "").strip()
            if not evt_name:
                continue
            try:
                await asyncio.wait_for(
                    asyncio.to_thread(
                        ctx.client.link_command_to_event_by_name,
                        command_id=created_cmd.get("id"),
                        event_name=evt_name,
                    ),
                    timeout=5.0,
                )
            except Exception:
                pass

        return {
            "command": created_cmd,
            "cmd": cmd,
            "agg": agg,
        }, None
    except asyncio.TimeoutError:
        return None, "Command creation timeout"
    except Exception as e:
        return None, f"Command creation failed: {e}"


async def extract_commands_phase(ctx: IngestionWorkflowContext) -> AsyncGenerator[ProgressEvent, None]:
    """
    Phase 5: extract commands per aggregate and persist them.
    """
    yield ProgressEvent(phase=IngestionPhase.EXTRACTING_COMMANDS, message="Command 추출 중...", progress=60)

    all_commands: dict[str, Any] = {}
    # Track already-created command names to prevent cross-aggregate duplication
    _existing_command_names: list[str] = []

    for bc in ctx.bounded_contexts:
        # Handle both dict and object formats
        bc_id = bc.get("id") if isinstance(bc, dict) else getattr(bc, "id", None)
        bc_name = bc.get("name") if isinstance(bc, dict) else getattr(bc, "name", "")
        bc_id_short = bc_name.strip()
        bc_aggregates = ctx.aggregates_by_bc.get(bc_id, [])

        for agg in bc_aggregates:
            # Handle both dict and object formats
            agg_id = agg.get("id") if isinstance(agg, dict) else getattr(agg, "id", None)
            agg_name = agg.get("name") if isinstance(agg, dict) else getattr(agg, "name", "")
            
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
            
            stories_context = "\n".join(
                [f"[{us.id}] As a {us.role}, I want to {us.action}" for us in ctx.user_stories if us.id in bc_us_ids]
            )

            # Aggregate에 속한 Event 목록 (SCOPE_EVENT 또는 BC의 HAS_EVENT)
            agg_event_names = []
            try:
                with ctx.client.session() as _sess:
                    _evt_result = _sess.run(
                        """
                        MATCH (agg:Aggregate {id: $agg_id})-[:SCOPE_EVENT]->(evt:Event)
                        RETURN evt.name AS name
                        UNION
                        MATCH (bc:BoundedContext {id: $bc_id})-[:HAS_EVENT]->(evt:Event)
                        RETURN evt.name AS name
                        """,
                        agg_id=agg_id, bc_id=bc_id,
                    )
                    agg_event_names = list({r["name"] for r in _evt_result if r["name"]})
            except Exception:
                pass
            events_text = "\n".join(f"- {n}" for n in sorted(agg_event_names)) if agg_event_names else "(no events)"

            display_lang = getattr(ctx, "display_language", "ko") or "ko"
            display_name_tail = (
                "\n\nFor each Command output displayName: a short UI label in Korean (e.g. '주문하기', '취소')."
                if display_lang == "ko"
                else "\n\nFor each Command output displayName: a short UI label in English (e.g. 'Place Order', 'Cancel')."
            )
            # 전체 프롬프트 텍스트 구성 (청킹 판단용)
            full_prompt_text = EXTRACT_COMMANDS_PROMPT.format(
                aggregate_name=agg_name,
                aggregate_id=agg_id,
                bc_name=bc_name,
                bc_short=bc_id_short,
                user_story_context=stories_context,
                available_events=events_text,
            ) + display_name_tail
            # Inject already-created commands to prevent cross-aggregate duplication
            if _existing_command_names:
                from api.features.ingestion.workflow.utils.chunking import format_accumulated_names
                full_prompt_text += (
                    "\n\n<already_created_commands>\n"
                    "The following Commands have already been created in OTHER Aggregates. "
                    "Do NOT create Commands with the same or very similar names/intent:\n"
                    + format_accumulated_names(_existing_command_names)
                    + "\n</already_created_commands>"
                )

            # 청킹 필요 여부 판단
            if should_chunk(full_prompt_text):
                # user_story_context를 청킹
                chunks = split_text_with_overlap(stories_context)
                total_chunks = len(chunks)
                
                chunk_results = []
                
                for i, (chunk_stories_context, start_char, end_char) in enumerate(chunks):
                    # Check cancellation before processing chunk
                    if getattr(ctx.session, "is_cancelled", False):
                        yield ProgressEvent(
                            phase=IngestionPhase.ERROR,
                            message="❌ 생성이 중단되었습니다",
                            progress=getattr(ctx.session, "progress", 0) or 0,
                            data={"error": "Cancelled by user", "cancelled": True},
                        )
                        return
                    
                    chunk_prompt = EXTRACT_COMMANDS_PROMPT.format(
                        aggregate_name=agg_name,
                        aggregate_id=agg_id,
                        bc_name=bc_name,
                        bc_short=bc_id_short,
                        user_story_context=chunk_stories_context,
                    ) + display_name_tail
                    structured_llm = ctx.llm.with_structured_output(CommandList)
                    
                    t_llm0 = time.perf_counter()
                    try:
                        cmd_response = await asyncio.wait_for(
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
                            f"Command extraction LLM timeout for chunk {i+1}/{total_chunks} (aggregate: {agg_name})",
                            category="ingestion.llm.extract_commands.timeout",
                            params={
                                "session_id": ctx.session.id,
                                "bc_id": bc_id,
                                "agg_id": agg_id,
                                "agg_name": agg_name,
                                "chunk_index": i + 1,
                                "total_chunks": total_chunks,
                                "elapsed_ms": llm_ms,
                            },
                        )
                        chunk_commands = []
                        chunk_results.append(chunk_commands)
                        continue
                    except Exception as llm_error:
                        llm_ms = int((time.perf_counter() - t_llm0) * 1000)
                        SmartLogger.log(
                            "ERROR",
                            f"Command extraction LLM error for chunk {i+1}/{total_chunks} (aggregate: {agg_name})",
                            category="ingestion.llm.extract_commands.error",
                            params={
                                "session_id": ctx.session.id,
                                "bc_id": bc_id,
                                "agg_id": agg_id,
                                "agg_name": agg_name,
                                "chunk_index": i + 1,
                                "total_chunks": total_chunks,
                                "error": str(llm_error),
                                "error_type": type(llm_error).__name__,
                                "elapsed_ms": llm_ms,
                            },
                        )
                        chunk_commands = []
                        chunk_results.append(chunk_commands)
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
                    
                    chunk_commands = getattr(cmd_response, "commands", []) or []
                    chunk_results.append(chunk_commands)
                
                # 결과 병합 (중복 제거: name 우선)
                commands = merge_chunk_results(
                    chunk_results,
                    dedupe_key=lambda cmd: getattr(cmd, "name", None) or getattr(cmd, "id", None) or f"__fallback_{id(cmd)}"
                )
            else:
                # 청킹 불필요한 경우
                prompt = full_prompt_text

                structured_llm = ctx.llm.with_structured_output(CommandList)

                try:
                    t_llm0 = time.perf_counter()
                    try:
                        cmd_response = await asyncio.wait_for(
                            asyncio.to_thread(
                                structured_llm.invoke,
                                [SystemMessage(content=SYSTEM_PROMPT), HumanMessage(content=prompt)]
                            ),
                            timeout=300.0  # 5분 타임아웃
                        )
                        llm_ms = int((time.perf_counter() - t_llm0) * 1000)
                        commands = getattr(cmd_response, "commands", []) or []
                    except asyncio.TimeoutError:
                        llm_ms = int((time.perf_counter() - t_llm0) * 1000)
                        SmartLogger.log(
                            "ERROR",
                            f"Command extraction LLM timeout (aggregate: {agg_name})",
                            category="ingestion.llm.extract_commands.timeout",
                            params={
                                "session_id": ctx.session.id,
                                "bc_id": bc_id,
                                "agg_id": agg_id,
                                "agg_name": agg_name,
                                "elapsed_ms": llm_ms,
                            },
                        )
                        commands = []
                    except Exception as llm_error:
                        llm_ms = int((time.perf_counter() - t_llm0) * 1000)
                        SmartLogger.log(
                            "ERROR",
                            f"Command extraction LLM error (aggregate: {agg_name})",
                            category="ingestion.llm.extract_commands.error",
                            params={
                                "session_id": ctx.session.id,
                                "bc_id": bc_id,
                                "agg_id": agg_id,
                                "agg_name": agg_name,
                                "error": str(llm_error),
                                "error_type": type(llm_error).__name__,
                                "elapsed_ms": llm_ms,
                            },
                        )
                        commands = []
                except Exception as e:
                    SmartLogger.log(
                        "ERROR",
                        "Command extraction failed (LLM)",
                        category="ingestion.workflow.commands",
                        params={"session_id": ctx.session.id, "bc_id": bc_id, "agg_id": agg_id, "error": str(e)},
                    )
                    commands = []

            all_commands[agg_id] = commands
            # Collect command names for cross-aggregate dedup
            for cmd in commands:
                cmd_n = cmd.get("name") if isinstance(cmd, dict) else getattr(cmd, "name", "")
                if cmd_n:
                    _existing_command_names.append(cmd_n)

            # Process all commands in parallel
            if commands:
                # Check cancellation before parallel processing
                if getattr(ctx.session, "is_cancelled", False):
                    yield ProgressEvent(
                        phase=IngestionPhase.ERROR,
                        message="❌ 생성이 중단되었습니다",
                        progress=getattr(ctx.session, "progress", 0) or 0,
                        data={"error": "Cancelled by user", "cancelled": True},
                    )
                    return
                
                total_cmds = len(commands)
                tasks = []
                for cmd_idx, cmd in enumerate(commands):
                    tasks.append(_create_command_with_links(cmd, cmd_idx, total_cmds, agg, ctx))
                
                results = await asyncio.gather(*tasks, return_exceptions=True)
                
                # Process results and yield progress events
                created_count = 0
                for cmd_idx, result in enumerate(results):
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
                            f"Command creation exception: {result}",
                            category="ingestion.neo4j.command.create.error",
                            params={"session_id": ctx.session.id, "command_index": cmd_idx + 1, "error": str(result)}
                        )
                        continue
                    
                    created_cmd_data, error = result
                    if error:
                        SmartLogger.log(
                            "ERROR",
                            f"Command creation failed: {error}",
                            category="ingestion.workflow.commands.skip",
                            params={"session_id": ctx.session.id, "command_index": cmd_idx + 1, "error": error}
                        )
                        continue
                    
                    if created_cmd_data:
                        created_count += 1
                        created_cmd = created_cmd_data["command"]
                        cmd = created_cmd_data["cmd"]

                        # Handle both dict and object formats
                        cmd_name = cmd.get("name") if isinstance(cmd, dict) else getattr(cmd, "name", "")
                        cmd_actor = cmd.get("actor") if isinstance(cmd, dict) else getattr(cmd, "actor", "user")
                        cmd_emits = cmd.get("emits_event_names") if isinstance(cmd, dict) else getattr(cmd, "emits_event_names", [])
                        cmd_display = cmd.get("displayName") if isinstance(cmd, dict) else getattr(cmd, "displayName", cmd_name)

                        # EMITS된 Event의 sequence를 가져와서 Command 배치에 사용
                        cmd_sequence = None
                        if cmd_emits:
                            try:
                                with ctx.client.session() as _s:
                                    _r = _s.run(
                                        "MATCH (evt:Event {name: $name}) RETURN evt.sequence AS seq LIMIT 1",
                                        name=cmd_emits[0],
                                    ).single()
                                    if _r and _r["seq"] is not None:
                                        cmd_sequence = int(_r["seq"])
                            except Exception:
                                pass

                        yield ProgressEvent(
                            phase=IngestionPhase.EXTRACTING_COMMANDS,
                            message=f"Command 생성: {cmd_name} ({created_count}/{total_cmds})",
                            progress=65,
                            data={
                                "type": "Command",
                                "object": {
                                    "id": created_cmd.get("id"),
                                    "name": cmd_name,
                                    "displayName": cmd_display,
                                    "type": "Command",
                                    "parentId": agg_id,
                                    "bcId": bc_id,
                                    "actor": cmd_actor,
                                    "sequence": cmd_sequence,
                                    "emitsEventNames": cmd_emits or [],
                                },
                            },
                        )

    # ── Cross-Aggregate Command 중복 병합 (Hard Defense) ────────────────
    # 동일 이름의 Command가 여러 Aggregate에 존재하면,
    # US가 더 많이 연결된 쪽을 유지하고, 나머지의 US를 유지 쪽으로 이관 후 삭제.
    cmd_name_to_aggs: dict[str, list[tuple[str, dict]]] = {}  # cmd_name → [(agg_id, cmd_dict)]
    for agg_id, cmds in all_commands.items():
        for cmd in cmds:
            cmd_name = cmd.get("name") if isinstance(cmd, dict) else getattr(cmd, "name", "")
            if cmd_name:
                if cmd_name not in cmd_name_to_aggs:
                    cmd_name_to_aggs[cmd_name] = []
                cmd_name_to_aggs[cmd_name].append((agg_id, cmd))

    merged_cmds: list[str] = []
    for cmd_name, agg_entries in cmd_name_to_aggs.items():
        if len(agg_entries) <= 1:
            continue
        def _us_count(entry: tuple[str, dict]) -> int:
            _agg_id, cmd = entry
            us_ids = cmd.get("user_story_ids") if isinstance(cmd, dict) else getattr(cmd, "user_story_ids", None)
            return len(us_ids) if us_ids else 0

        sorted_entries = sorted(agg_entries, key=_us_count, reverse=True)
        keep_agg_id, keep_cmd = sorted_entries[0]
        keep_cmd_id = keep_cmd.get("id") if isinstance(keep_cmd, dict) else getattr(keep_cmd, "id", None)

        for agg_id, cmd in sorted_entries[1:]:
            cmd_id = cmd.get("id") if isinstance(cmd, dict) else getattr(cmd, "id", None)
            if not cmd_id:
                continue
            # 1) 흡수 Command의 US를 유지 Command로 이관 (Neo4j)
            try:
                with ctx.client.session() as merge_session:
                    merge_session.run(
                        """
                        MATCH (us:UserStory)-[r:IMPLEMENTS]->(old_cmd:Command {id: $old_id})
                        MATCH (new_cmd:Command {id: $new_id})
                        MERGE (us)-[:IMPLEMENTS]->(new_cmd)
                        DELETE r
                        """,
                        old_id=cmd_id,
                        new_id=keep_cmd_id,
                    )
                    # 흡수 Command + 하위 Event/Property 삭제
                    merge_session.run(
                        """
                        MATCH (cmd:Command {id: $id})
                        OPTIONAL MATCH (cmd)-[:EMITS]->(evt:Event)
                        OPTIONAL MATCH (cmd)-[:HAS_PROPERTY]->(cmd_prop:Property)
                        OPTIONAL MATCH (evt)-[:HAS_PROPERTY]->(evt_prop:Property)
                        DETACH DELETE evt_prop, cmd_prop, evt, cmd
                        """,
                        id=cmd_id,
                    )
            except Exception as e:
                SmartLogger.log(
                    "WARN",
                    f"Failed to merge duplicate Command {cmd_name} (id={cmd_id}): {e}",
                    category="ingestion.workflow.commands.dedup_merge_error",
                    params={"session_id": ctx.session.id, "cmd_name": cmd_name, "cmd_id": cmd_id, "error": str(e)},
                )
                continue

            # 2) ctx에서 제거
            if agg_id in all_commands:
                all_commands[agg_id] = [
                    c for c in all_commands[agg_id]
                    if (c.get("id") if isinstance(c, dict) else getattr(c, "id", None)) != cmd_id
                ]
            merged_cmds.append(f"{cmd_name}(agg={agg_id} → agg={keep_agg_id})")

            SmartLogger.log(
                "INFO",
                f"Merged duplicate Command: {cmd_name} from agg={agg_id} into agg={keep_agg_id}",
                category="ingestion.workflow.commands.cross_agg_merge",
                params={
                    "session_id": ctx.session.id,
                    "cmd_name": cmd_name,
                    "absorbed_agg_id": agg_id,
                    "kept_agg_id": keep_agg_id,
                },
            )

    if merged_cmds:
        SmartLogger.log(
            "INFO",
            f"Cross-aggregate Command merge: merged {len(merged_cmds)} duplicates",
            category="ingestion.workflow.commands.cross_agg_merge_summary",
            params={"session_id": ctx.session.id, "merged": merged_cmds},
        )
    # ── End Cross-Aggregate Command 중복 병합 ─────────────────────────

    ctx.commands_by_agg = all_commands


