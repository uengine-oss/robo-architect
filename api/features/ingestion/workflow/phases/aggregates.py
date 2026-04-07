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
from api.features.ingestion.event_storming.nodes import AggregateList
from api.features.ingestion.event_storming.prompts import EXTRACT_AGGREGATES_PROMPT, SYSTEM_PROMPT
from api.features.ingestion.workflow.ingestion_workflow_context import IngestionWorkflowContext
from api.platform.env import get_llm_provider_model
from api.platform.observability.request_logging import summarize_for_log
from api.platform.observability.smart_logger import SmartLogger


def _allowed_event_names_for_bc(ctx: IngestionWorkflowContext, us_ids: set[str]) -> set[str]:
    names: set[str] = set()
    for e in ctx.events_from_us or []:
        if not isinstance(e, dict):
            continue
        uid = e.get("userStoryId") or ""
        if uid not in us_ids:
            continue
        n = (e.get("name") or "").strip()
        if n:
            names.add(n)
    return names


def _bc_events_prompt_block(ctx: IngestionWorkflowContext, us_ids: set[str]) -> str:
    lines: list[str] = []
    for e in ctx.events_from_us or []:
        if not isinstance(e, dict):
            continue
        uid = e.get("userStoryId") or ""
        if uid not in us_ids:
            continue
        name = (e.get("name") or "").strip()
        if not name:
            continue
        desc = (e.get("description") or "").strip()
        tail = f" — {desc[:300]}" if desc else ""
        lines.append(f"- **{name}** (user_story_id={uid}){tail}")
    if not lines:
        return (
            "(No domain events extracted yet for user stories in this BC. "
            "Derive Aggregates from user story breakdowns only; set covered_event_names to [].)"
        )
    return "\n".join(lines)


def _user_story_breakdown_lines(ctx: IngestionWorkflowContext, us_ids: set[str]) -> str:
    lines: list[str] = []
    for us in ctx.user_stories or []:
        uid = getattr(us, "id", "") or ""
        if uid not in us_ids:
            continue
        role = getattr(us, "role", "") or ""
        action = getattr(us, "action", "") or ""
        benefit = getattr(us, "benefit", "") or ""
        lines.append(f"- [{uid}] As a {role}, I want to {action}, so that {benefit}")
    if not lines:
        return "User Stories: (none assigned)"
    return "\n".join(lines)


def _covered_event_names_from_agg(agg: Any) -> list[str]:
    raw = getattr(agg, "covered_event_names", None)
    if raw is None and isinstance(agg, dict):
        raw = agg.get("covered_event_names")
    if not raw:
        return []
    return [str(x).strip() for x in raw if str(x).strip()]


async def _create_aggregate_with_links(
    agg: Any,
    agg_idx: int,
    bc: Any,
    bc_idx: int,
    total_bcs: int,
    ctx: IngestionWorkflowContext,
    allowed_event_names: set[str],
) -> tuple[dict[str, Any] | None, str]:
    """
    Create a single aggregate with user story links.
    Returns (created_aggregate_dict, error_message)
    """
    # Handle both dict and object formats
    agg_name = (agg.get("name") if isinstance(agg, dict) else getattr(agg, "name", None) or "").strip()
    agg_display_name = agg.get("displayName") if isinstance(agg, dict) else getattr(agg, "displayName", None)
    if not agg_display_name:
        agg_display_name = agg_name
    bc_id = bc.get("id") if isinstance(bc, dict) else getattr(bc, "id", None)
    
    # Convert enumerations and value_objects to dict format for Neo4j
    enum_list = []
    try:
        if hasattr(agg, "enumerations") and agg.enumerations:
            for e in agg.enumerations:
                if isinstance(e, dict):
                    enum_name = e.get("name")
                    if enum_name:  # Only add if name exists
                        enum_list.append({
                            "name": str(enum_name),
                            "displayName": e.get("displayName"),
                            "alias": e.get("alias"),
                            "items": e.get("items", [])
                        })
                else:
                    # Handle Pydantic model
                    enum_name = getattr(e, "name", None)
                    if enum_name:  # Only add if name exists
                        enum_list.append({
                            "name": str(enum_name),
                            "displayName": getattr(e, "displayName", None) or (e.get("displayName") if isinstance(e, dict) else None),
                            "alias": getattr(e, "alias", None),
                            "items": getattr(e, "items", []) or []
                        })
    except Exception as e:
        pass
    
    vo_list = []
    try:
        if hasattr(agg, "value_objects") and agg.value_objects:
            for vo in agg.value_objects:
                if isinstance(vo, dict):
                    vo_name = vo.get("name")
                    if vo_name:  # Only add if name exists
                        # Convert fields to dict format
                        fields_list = vo.get("fields", [])
                        fields_dicts = []
                        for field in fields_list:
                            if isinstance(field, dict):
                                fields_dicts.append(field)
                            else:
                                # Handle Pydantic ValueObjectField model
                                fields_dicts.append({
                                    "name": getattr(field, "name", ""),
                                    "type": getattr(field, "type", "")
                                })
                        vo_list.append({
                            "name": str(vo_name),
                            "displayName": vo.get("displayName"),
                            "alias": vo.get("alias"),
                            "referenced_aggregate_name": vo.get("referenced_aggregate_name"),
                            "referenced_aggregate_field": vo.get("referenced_aggregate_field"),
                            "fields": fields_dicts
                        })
                else:
                    # Handle Pydantic model
                    vo_name = getattr(vo, "name", None)
                    if vo_name:  # Only add if name exists
                        # Convert fields to dict format
                        fields_list = getattr(vo, "fields", []) or []
                        fields_dicts = []
                        for field in fields_list:
                            if isinstance(field, dict):
                                fields_dicts.append(field)
                            else:
                                # Handle Pydantic ValueObjectField model
                                fields_dicts.append({
                                    "name": getattr(field, "name", ""),
                                    "type": getattr(field, "type", "")
                                })
                        vo_list.append({
                            "name": str(vo_name),
                            "displayName": getattr(vo, "displayName", None),
                            "alias": getattr(vo, "alias", None),
                            "referenced_aggregate_name": getattr(vo, "referenced_aggregate_name", None),
                            "referenced_aggregate_field": getattr(vo, "referenced_aggregate_field", None),
                            "fields": fields_dicts
                        })
    except Exception as e:
        pass
    
    try:
        root_entity = getattr(agg, "root_entity", None) or agg_name
        invariants = getattr(agg, "invariants", None) or []
        
        created_agg = await asyncio.wait_for(
            asyncio.to_thread(
                ctx.client.create_aggregate,
                name=agg_name,
                bc_id=bc_id,
                root_entity=root_entity,
                invariants=invariants,
                enumerations=enum_list if enum_list else None,
                value_objects=vo_list if vo_list else None,
                display_name=agg_display_name,
            ),
            timeout=10.0
        )
        
        # Overwrite LLM-proposed id with UUID from DB
        try:
            agg.id = created_agg.get("id")
            agg.key = created_agg.get("key")
        except Exception:
            pass

        # Link user stories (batch processing)
        us_ids = getattr(agg, "user_story_ids", []) or []
        if us_ids:
            link_tasks = []
            for us_id in us_ids:
                link_task = asyncio.wait_for(
                    asyncio.to_thread(
                        ctx.client.link_user_story_to_aggregate,
                        us_id,
                        created_agg.get("id")
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

        linked_event_count = 0
        covered_names = _covered_event_names_from_agg(agg)
        if allowed_event_names:
            for ename in covered_names:
                if ename not in allowed_event_names:
                    continue
                try:
                    await asyncio.wait_for(
                        asyncio.to_thread(
                            ctx.client.link_aggregate_to_event_by_name,
                            created_agg.get("id"),
                            ename,
                        ),
                        timeout=5.0,
                    )
                    linked_event_count += 1
                except Exception:
                    pass

        # ── SCOPE_EVENT 0건 경고 ──────────────────────────────────
        if covered_names and linked_event_count == 0:
            SmartLogger.log(
                "WARN",
                f"Aggregate '{agg_name}' has {len(covered_names)} covered_event_names "
                f"but 0 SCOPE_EVENT links were created (name mismatch?). "
                f"Attempted: {covered_names[:5]}",
                category="ingestion.workflow.aggregates.scope_event_zero",
                params={
                    "session_id": ctx.session.id,
                    "aggregate_id": created_agg.get("id"),
                    "aggregate_name": agg_name,
                    "bc_id": bc_id,
                    "covered_names": covered_names[:10],
                },
            )

        return {
            "aggregate": created_agg,
            "agg": agg,
            "bc": bc,
            "bc_idx": bc_idx,
            "total_bcs": total_bcs,
            "linked_event_count": linked_event_count,
        }, None
    except asyncio.TimeoutError:
        return None, "Aggregate creation timeout"
    except Exception as e:
        return None, f"Aggregate creation failed: {e}"


async def extract_aggregates_phase(ctx: IngestionWorkflowContext) -> AsyncGenerator[ProgressEvent, None]:
    """
    Phase 4: extract aggregates per BC and persist them.
    """
    yield ProgressEvent(phase=IngestionPhase.EXTRACTING_AGGREGATES, message="Aggregate 추출 중...", progress=45)

    all_aggregates: dict[str, Any] = {}
    progress_per_bc = 10 // max(len(ctx.bounded_contexts), 1)

    for bc_idx, bc in enumerate(ctx.bounded_contexts):
        # Handle both dict and object formats
        bc_id = bc.get("id") if isinstance(bc, dict) else getattr(bc, "id", None)
        bc_name = bc.get("name") if isinstance(bc, dict) else getattr(bc, "name", "")
        bc_description = bc.get("description") if isinstance(bc, dict) else getattr(bc, "description", "")
        bc_id_short = bc_name.strip()
        
        # BC 객체에서 user_story_ids를 안전하게 읽어오기
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
        
        if not isinstance(us_ids, list):
            us_ids = []
        us_ids = [us_id for us_id in us_ids if us_id]  # None이나 빈 문자열 제거
        us_id_set = set(us_ids)

        breakdowns_text = _user_story_breakdown_lines(ctx, us_id_set)
        bc_events_text = _bc_events_prompt_block(ctx, us_id_set)

        # BC의 UserStory들에서 source_unit_id 수집 → 테이블 스키마 역추적
        schema_context = ""
        if ctx.source_type == "analyzer_graph":
            unit_ids = []
            for us in (ctx.user_stories or []):
                uid = getattr(us, "id", "") or ""
                if uid in us_id_set:
                    src = getattr(us, "source_unit_id", None)
                    if src:
                        unit_ids.append(src)
            if unit_ids:
                try:
                    from api.features.ingestion.analyzer_graph.graph_to_report import fetch_table_schemas_for_units
                    schema_context = fetch_table_schemas_for_units(unit_ids)
                except Exception:
                    pass

        # Collect existing aggregates from previously processed BCs for reference validation
        existing_aggregates_text = ""
        all_existing_aggregate_names = set()
        for prev_bc_idx in range(bc_idx):
            prev_bc = ctx.bounded_contexts[prev_bc_idx]
            prev_bc_id = prev_bc.get("id") if isinstance(prev_bc, dict) else getattr(prev_bc, "id", None)
            prev_bc_name = prev_bc.get("name") if isinstance(prev_bc, dict) else getattr(prev_bc, "name", "")
            prev_aggregates = all_aggregates.get(prev_bc_id, [])
            if prev_aggregates:
                agg_names = [agg.get("name") if isinstance(agg, dict) else getattr(agg, "name", "") for agg in prev_aggregates if (agg.get("name") if isinstance(agg, dict) else getattr(agg, "name", None))]
                if agg_names:
                    existing_aggregates_text += f"  - {prev_bc_name}: {', '.join(agg_names)}\n"
                    all_existing_aggregate_names.update(agg_names)
        
        if not existing_aggregates_text:
            existing_aggregates_text = "  (No aggregates have been extracted from other Bounded Contexts yet.)"
        else:
            existing_aggregates_text = (
                "The following Aggregates already exist in other Bounded Contexts and can be referenced:\n"
                + existing_aggregates_text
                + "\nCRITICAL — CROSS-BC DEDUPLICATION:\n"
                "Do NOT create an Aggregate that represents the SAME domain concept as one listed above.\n"
                "If this BC has User Stories related to a domain concept already covered by an existing Aggregate "
                "in another BC, do NOT duplicate it. Instead, those User Stories should be handled via "
                "cross-BC Policies or references (Value Objects with foreign keys).\n"
                "Example: If 'Delinquency' already exists in another BC, do NOT create 'DelinquencyCase' "
                "or 'DelinquencyRecord' here — they are the same domain concept."
            )

        prompt = EXTRACT_AGGREGATES_PROMPT.format(
            bc_name=bc_name,
            bc_id=bc_id,
            bc_id_short=bc_id_short,
            bc_description=bc_description,
            breakdowns=breakdowns_text,
            bc_events=bc_events_text,
            existing_aggregates=existing_aggregates_text,
        )
        # 테이블 스키마 컨텍스트 삽입
        if schema_context:
            prompt += (
                f"\n\n{schema_context}\n"
                "위 테이블 스키마가 있으면 Aggregate의 속성을 실제 컬럼 타입과 맞추세요.\n"
                "FK 관계를 참고하여 Aggregate 경계를 결정하세요."
            )

        display_lang = getattr(ctx, "display_language", "ko") or "ko"
        prompt += (
            "\n\nFor each Aggregate output displayName: a short UI label in Korean (e.g. '장바구니', '주문')."
            if display_lang == "ko"
            else "\n\nFor each Aggregate output displayName: a short UI label in English (e.g. 'Cart', 'Order')."
        )
        prompt += (
            "\n\nFor each Enumeration and each Value Object also output displayName: a short UI label in Korean (e.g. '주문 상태', '배송 주소')."
            if display_lang == "ko"
            else "\n\nFor each Enumeration and each Value Object also output displayName: a short UI label in English (e.g. 'Order Status', 'Shipping Address')."
        )


        structured_llm = ctx.llm.with_structured_output(AggregateList)

        try:
            agg_response = await asyncio.wait_for(
                asyncio.to_thread(
                    structured_llm.invoke,
                    [SystemMessage(content=SYSTEM_PROMPT), HumanMessage(content=prompt)]
                ),
                timeout=300.0,
            )
            aggregates = agg_response.aggregates
        except asyncio.TimeoutError:
            SmartLogger.log(
                "ERROR",
                "Aggregate extraction timed out (300s)",
                category="ingestion.workflow.aggregates.timeout",
                params={"session_id": ctx.session.id, "bc_id": bc_id},
            )
            aggregates = []
        except Exception as e:
            SmartLogger.log(
                "ERROR",
                "Aggregate extraction failed (LLM)",
                category="ingestion.workflow.aggregates",
                params={"session_id": ctx.session.id, "bc_id": bc_id, "error": str(e)},
            )
            aggregates = []
        
        # Validate and fix Value Object references
        # Collect all existing aggregate names (from previously processed BCs and current BC)
        all_existing_aggregate_names_for_validation = set(all_existing_aggregate_names)
        for agg in aggregates or []:
            agg_name = getattr(agg, "name", None)
            if agg_name:
                all_existing_aggregate_names_for_validation.add(agg_name)
        
        # Validate and remove invalid references
        validation_warnings = []
        for agg in aggregates or []:
            if hasattr(agg, "value_objects") and agg.value_objects:
                for vo in agg.value_objects:
                    ref_name = getattr(vo, "referenced_aggregate_name", None)
                    if ref_name and ref_name not in all_existing_aggregate_names_for_validation:
                        # Remove invalid reference
                        agg_name_for_warning = agg.get("name") if isinstance(agg, dict) else getattr(agg, "name", "unknown")
                        validation_warnings.append(
                            f"Removed invalid reference: {agg_name_for_warning}.{getattr(vo, 'name', 'unknown')} → {ref_name} (Aggregate does not exist)"
                        )
                        try:
                            vo.referenced_aggregate_name = None
                        except Exception:
                            pass
        
        all_aggregates[bc_id] = aggregates

        # Process all aggregates in parallel
        if aggregates:
            # Check cancellation before parallel processing
            if getattr(ctx.session, "is_cancelled", False):
                yield ProgressEvent(
                    phase=IngestionPhase.ERROR,
                    message="❌ 생성이 중단되었습니다",
                    progress=getattr(ctx.session, "progress", 0) or 0,
                    data={"error": "Cancelled by user", "cancelled": True},
                )
                return
            
            # Filter out aggregates without name
            valid_aggregates = []
            for agg in aggregates:
                agg_name = getattr(agg, "name", None)
                if not agg_name:
                    continue
                valid_aggregates.append(agg)
            
            total_bcs = len(ctx.bounded_contexts)
            allowed_names = _allowed_event_names_for_bc(ctx, us_id_set)
            tasks = []
            for agg_idx, agg in enumerate(valid_aggregates):
                tasks.append(
                    _create_aggregate_with_links(
                        agg, agg_idx, bc, bc_idx, total_bcs, ctx, allowed_names
                    )
                )
            
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Process results and yield progress events
            created_count = 0
            progress_per_bc = 10 // max(total_bcs, 1)
            for agg_idx, result in enumerate(results):
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
                        f"Aggregate creation exception: {result}",
                        category="ingestion.neo4j.aggregate.create.error",
                        params={"session_id": ctx.session.id, "aggregate_index": agg_idx + 1, "error": str(result)}
                    )
                    continue
                
                created_agg_data, error = result
                if error:
                    SmartLogger.log(
                        "ERROR",
                        f"Aggregate creation failed: {error}",
                        category="ingestion.workflow.aggregates.skip",
                        params={"session_id": ctx.session.id, "aggregate_index": agg_idx + 1, "error": error}
                    )
                    continue
                
                if created_agg_data:
                    created_count += 1
                    created_agg = created_agg_data["aggregate"]
                    agg = created_agg_data["agg"]
                    
                    # Handle both dict and object formats
                    agg_name = agg.get("name") if isinstance(agg, dict) else getattr(agg, "name", "")
                    yield ProgressEvent(
                        phase=IngestionPhase.EXTRACTING_AGGREGATES,
                        message=f"Aggregate 생성: {agg_name} ({created_count}/{len(valid_aggregates)})",
                        progress=45 + progress_per_bc * bc_idx,
                        data={
                            "type": "Aggregate",
                            "object": {"id": created_agg.get("id"), "name": agg_name, "type": "Aggregate", "parentId": bc_id},
                        },
                    )

    # ── Cross-BC Aggregate 중복 병합 (Hard Defense) ─────────────────────
    # 동일 이름의 Aggregate가 여러 BC에 존재하면,
    # US가 더 많이 연결된 BC의 것을 유지하고, 나머지의 US를 유지 쪽으로 이관.
    # 이관 후 중복 Aggregate와 하위 노드를 Neo4j에서 삭제.
    agg_name_to_bcs: dict[str, list[tuple[str, dict]]] = {}  # agg_name → [(bc_id, agg_dict)]
    for bc_id, aggs in all_aggregates.items():
        for agg in aggs:
            agg_name = agg.get("name") if isinstance(agg, dict) else getattr(agg, "name", "")
            if agg_name:
                if agg_name not in agg_name_to_bcs:
                    agg_name_to_bcs[agg_name] = []
                agg_name_to_bcs[agg_name].append((bc_id, agg))

    merged_aggs: list[str] = []
    for agg_name, bc_entries in agg_name_to_bcs.items():
        if len(bc_entries) <= 1:
            continue
        # US 수 기준 정렬: 가장 많은 US를 가진 BC의 Aggregate를 유지
        def _agg_us_count(entry: tuple[str, dict]) -> int:
            _bc_id, agg = entry
            us_ids = agg.get("user_story_ids") if isinstance(agg, dict) else getattr(agg, "user_story_ids", None)
            return len(us_ids) if us_ids else 0

        sorted_entries = sorted(bc_entries, key=_agg_us_count, reverse=True)
        keep_bc_id, keep_agg = sorted_entries[0]
        keep_agg_id = keep_agg.get("id") if isinstance(keep_agg, dict) else getattr(keep_agg, "id", None)

        for bc_id, agg in sorted_entries[1:]:
            agg_id = agg.get("id") if isinstance(agg, dict) else getattr(agg, "id", None)
            if not agg_id:
                continue

            # 1) 흡수 대상의 US를 유지 Aggregate로 이관 (Neo4j)
            try:
                with ctx.client.session() as merge_session:
                    # 흡수 Aggregate에 연결된 US → 유지 Aggregate로 관계 이동
                    merge_session.run(
                        """
                        MATCH (us:UserStory)-[r:IMPLEMENTS]->(old_agg:Aggregate {id: $old_id})
                        MATCH (new_agg:Aggregate {id: $new_id})
                        MERGE (us)-[:IMPLEMENTS]->(new_agg)
                        DELETE r
                        """,
                        old_id=agg_id,
                        new_id=keep_agg_id,
                    )
                    # 흡수 Aggregate + 하위 Command/Event/Property 삭제
                    merge_session.run(
                        """
                        MATCH (agg:Aggregate {id: $id})
                        OPTIONAL MATCH (agg)-[:HAS_COMMAND]->(cmd:Command)
                        OPTIONAL MATCH (cmd)-[:EMITS]->(evt:Event)
                        OPTIONAL MATCH (cmd)-[:HAS_PROPERTY]->(cmd_prop:Property)
                        OPTIONAL MATCH (evt)-[:HAS_PROPERTY]->(evt_prop:Property)
                        OPTIONAL MATCH (agg)-[:HAS_PROPERTY]->(agg_prop:Property)
                        DETACH DELETE evt_prop, cmd_prop, agg_prop, evt, cmd, agg
                        """,
                        id=agg_id,
                    )
            except Exception as e:
                SmartLogger.log(
                    "WARN",
                    f"Failed to merge duplicate Aggregate {agg_name} (id={agg_id}): {e}",
                    category="ingestion.workflow.aggregates.dedup_merge_error",
                    params={"session_id": ctx.session.id, "agg_name": agg_name, "agg_id": agg_id, "error": str(e)},
                )
                continue

            # 2) ctx에서도 흡수 대상의 US를 유지 쪽에 합산
            absorbed_us_ids = agg.get("user_story_ids") if isinstance(agg, dict) else getattr(agg, "user_story_ids", None)
            if absorbed_us_ids and keep_agg:
                keep_us_ids = keep_agg.get("user_story_ids") if isinstance(keep_agg, dict) else getattr(keep_agg, "user_story_ids", None)
                if keep_us_ids is not None:
                    merged_ids = list(set(keep_us_ids) | set(absorbed_us_ids))
                    if isinstance(keep_agg, dict):
                        keep_agg["user_story_ids"] = merged_ids
                    else:
                        try:
                            setattr(keep_agg, "user_story_ids", merged_ids)
                        except Exception:
                            pass

            # 3) ctx에서 흡수 Aggregate 제거
            if bc_id in all_aggregates:
                all_aggregates[bc_id] = [
                    a for a in all_aggregates[bc_id]
                    if (a.get("id") if isinstance(a, dict) else getattr(a, "id", None)) != agg_id
                ]
            merged_aggs.append(f"{agg_name}(bc={bc_id} → bc={keep_bc_id})")

            SmartLogger.log(
                "INFO",
                f"Merged duplicate Aggregate: {agg_name} from bc={bc_id} into bc={keep_bc_id} "
                f"(US transferred: {len(absorbed_us_ids) if absorbed_us_ids else 0})",
                category="ingestion.workflow.aggregates.cross_bc_merge",
                params={
                    "session_id": ctx.session.id,
                    "agg_name": agg_name,
                    "absorbed_bc_id": bc_id,
                    "kept_bc_id": keep_bc_id,
                    "transferred_us_count": len(absorbed_us_ids) if absorbed_us_ids else 0,
                },
            )

    if merged_aggs:
        SmartLogger.log(
            "INFO",
            f"Cross-BC Aggregate merge: merged {len(merged_aggs)} duplicates",
            category="ingestion.workflow.aggregates.cross_bc_merge_summary",
            params={"session_id": ctx.session.id, "merged": merged_aggs},
        )
    # ── End Cross-BC Aggregate 중복 병합 ──────────────────────────────

    ctx.aggregates_by_bc = all_aggregates


