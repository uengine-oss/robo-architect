"""
Phase: Extract Events from User Stories (Event Modeling 방식)

기존 Command 기반이 아닌, UserStory 기반으로 Event를 추출.
각 UserStory에서 발생할 수 있는 비즈니스 이벤트들을 도출.
Event는 Command 없이 독립적으로 생성되며, 이후 Command가 역도출됨.

analyzer_graph 소스: 같은 source_unit_id(프로시저)의 US를 배치로 묶어 처리.
rfp/figma 소스: US 1개씩 처리 (기존 동작 유지).
"""

from __future__ import annotations

import asyncio
from collections import defaultdict
from typing import Any, AsyncGenerator

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from api.features.ingestion.ingestion_contracts import IngestionPhase, ProgressEvent
from api.features.ingestion.workflow.ingestion_workflow_context import IngestionWorkflowContext
from api.features.ingestion.workflow.utils.chunking import estimate_tokens
from api.features.ingestion.workflow.utils.user_story_format import load_bl_for_user_stories
from api.platform.observability.smart_logger import SmartLogger

# Token budget for accumulated previous events injected into each prompt.
_PREV_EVENTS_BUDGET_TOKENS = 4000
_PREV_EVENTS_RECENT_COUNT = 30

# Batch config for analyzer_graph
_BATCH_MAX_US = 10  # Max US per batch
_BATCH_MAX_TOKENS = 60000  # Soft token limit for batch prompt


# ── LLM 출력 스키마 ──────────────────────────────────────────────

class EventFromUS(BaseModel):
    """UserStory에서 도출된 Event."""
    name: str = Field(..., description="Event name in PascalCase past tense (e.g., OrderPlaced, PaymentConfirmed)")
    displayName: str = Field(default="", description="UI label in chosen language")
    description: str = Field(..., description="What business fact occurred")
    order: int = Field(default=1, description="Chronological order within this user story (1=first, 2=second, ...)")


class EventFromUSList(BaseModel):
    events: list[EventFromUS] = Field(default_factory=list)


class EventFromBatch(BaseModel):
    """배치에서 도출된 Event (어떤 US에서 나왔는지 추적)."""
    name: str = Field(..., description="Event name in PascalCase past tense")
    displayName: str = Field(default="", description="UI label in chosen language")
    description: str = Field(..., description="What business fact occurred")
    order: int = Field(default=1, description="Chronological order (1=first)")
    user_story_id: str = Field(default="", description="ID of the primary User Story that generates this event")


class EventFromBatchList(BaseModel):
    events: list[EventFromBatch] = Field(default_factory=list)


# ── 프롬프트 ──────────────────────────────────────────────────────

SYSTEM_PROMPT = "You are a Domain-Driven Design expert identifying business events from user stories for Event Modeling."

# 단건 프롬프트 (rfp/figma용 — 기존)
EXTRACT_EVENTS_FROM_US_PROMPT = """Identify all business Events that would occur when the following User Story is fulfilled.

<user_story>
ID: {us_id}
Role: {role}
Action: {action}
Benefit: {benefit}
</user_story>
{business_rules_section}
<previously_generated_events>
{previous_events}
</previously_generated_events>

<rules>
1. Events represent **immutable business facts** that happened (past tense).
2. **name** field: MUST be English PascalCase, Noun + PastParticiple (e.g., OrderPlaced, PaymentProcessed, AccountRegistered).
   - NEVER use Korean, spaces, or special characters in the name field.
   - Even if the user story is written in Korean, the event name MUST be in English.
3. **displayName** field: A short localized UI label (language specified separately).
4. Include both **success** and **failure** events when appropriate.
   - Failure event name = success name stem + "Failed" (e.g., OrderPlaced → OrderPlacementFailed).
5. Focus on **business-significant state changes**, not technical details.
   - Internal validations, type checks, null checks, format conversions are NOT separate events.
   - Group related validations into ONE event (e.g., InputValidated / InputValidationFailed).
6. Do NOT duplicate events from the previously generated list. If a prior event covers this story, skip it.
7. Typically 1~3 events per user story. Keep focused. Even if business rules list many branches, consolidate into high-level business outcomes.
8. **order**: Assign chronological order within this user story. If this story involves multiple steps (e.g., place order → then payment), the first event gets order=1, the next order=2. Failure events share the same order as their success counterpart.
</rules>

Return the events for this user story."""

# 배치 프롬프트 (analyzer_graph용 — 여러 US를 한꺼번에)
EXTRACT_EVENTS_BATCH_PROMPT = """Identify business Events for the following group of related User Stories.
These User Stories come from the SAME or closely related legacy code modules and should be analyzed TOGETHER as a cohesive business capability.

<user_stories>
{user_stories_block}
</user_stories>

<previously_generated_events>
{previous_events}
</previously_generated_events>

<rules>
1. Events represent **immutable business facts** that happened (past tense).
2. **name** field: MUST be English PascalCase, Noun + PastParticiple.
   - NEVER use Korean, spaces, or special characters in the name field.
3. **displayName** field: A short localized UI label (language specified separately).
4. **CONSOLIDATE aggressively**: These user stories come from legacy code where one procedure may have dozens of branches.
   - Multiple validation checks → ONE "Validated" + ONE "ValidationFailed" event
   - Multiple error branches → ONE "Failed" event per business operation (not per error code)
   - Similar operations (create/update/delete on same entity) → separate events, but share naming root
5. Include both **success** and **failure** events when appropriate.
   - Failure event name = success name stem + "Failed"
6. Do NOT duplicate events from the previously generated list.
7. **user_story_id**: Set to the MOST relevant User Story ID for each event. If an event covers multiple stories, pick the primary one.
8. Target: 2~5 events per batch (NOT per user story). Think of the batch as ONE business capability.
9. **order**: Assign chronological order across the batch (1=first step in the business flow).
</rules>

Return the consolidated events for this group."""


# ── 헬퍼 ──────────────────────────────────────────────────────────

def _format_previous_events(accumulated: list[str]) -> str:
    """Format previously generated event names with token budget."""
    if not accumulated:
        return "(none)"

    total = len(accumulated)

    if total <= _PREV_EVENTS_RECENT_COUNT:
        full = "\n".join(f"- {e}" for e in accumulated)
        if estimate_tokens(full) <= _PREV_EVENTS_BUDGET_TOKENS:
            return full

    recent = accumulated[-_PREV_EVENTS_RECENT_COUNT:]
    older_count = total - len(recent)

    lines: list[str] = []
    if older_count > 0:
        lines.append(f"({older_count} earlier events omitted — names already taken, do NOT reuse)")
    lines.extend(f"- {e}" for e in recent)

    text = "\n".join(lines)

    if estimate_tokens(text) > _PREV_EVENTS_BUDGET_TOKENS:
        half = _PREV_EVENTS_RECENT_COUNT // 2
        recent = accumulated[-half:]
        older_count = total - len(recent)
        lines = [f"({older_count} earlier events omitted — names already taken, do NOT reuse)"]
        lines.extend(f"- {e}" for e in recent)
        text = "\n".join(lines)

    return text


def _build_batch_us_block(
    batch: list[Any],
    bl_map: dict[str, list[dict]],
) -> str:
    """Build the <user_stories> block for a batch of US."""
    blocks = []
    for us in batch:
        us_id = getattr(us, "id", "")
        role = getattr(us, "role", "")
        action = getattr(us, "action", "")
        benefit = getattr(us, "benefit", "")

        block = f"[{us_id}] As a {role}, I want to {action}"
        if benefit:
            block += f", so that {benefit}"

        # BL 컨텍스트 추가
        bls = bl_map.get(us_id) if bl_map else None
        if bls:
            bl_lines = []
            for bl in bls:
                seq = bl.get("seq", "?")
                title = bl.get("title", "")
                domain = bl.get("coupled_domain")
                domain_mark = f" [→ {domain}]" if domain else ""
                given = bl.get("given", "")
                when = bl.get("when", "")
                then = bl.get("then", "")
                bl_lines.append(f"    BL[{seq}]{domain_mark}: {title}")
                if given:
                    bl_lines.append(f"      Given: {given}")
                if when:
                    bl_lines.append(f"      When: {when}")
                if then:
                    bl_lines.append(f"      Then: {then}")
            block += "\n  [Business Rules]\n" + "\n".join(bl_lines)

        blocks.append(block)

    return "\n\n".join(blocks)


def _group_us_into_batches(
    user_stories: list[Any],
    bl_map: dict[str, list[dict]],
) -> list[list[Any]]:
    """Group user stories by source_unit_id, then split into token-bounded batches."""
    # Group by source_unit_id
    by_unit: dict[str, list[Any]] = defaultdict(list)
    no_unit: list[Any] = []
    for us in user_stories:
        unit_id = getattr(us, "source_unit_id", None)
        if unit_id:
            by_unit[unit_id].append(us)
        else:
            no_unit.append(us)

    batches: list[list[Any]] = []

    # Process each unit group
    for unit_id, group in by_unit.items():
        # If group fits in one batch, use it
        if len(group) <= _BATCH_MAX_US:
            batches.append(group)
        else:
            # Split large groups into sub-batches
            for i in range(0, len(group), _BATCH_MAX_US):
                batches.append(group[i:i + _BATCH_MAX_US])

    # US without source_unit_id: batch by sequence proximity
    for i in range(0, len(no_unit), _BATCH_MAX_US):
        batches.append(no_unit[i:i + _BATCH_MAX_US])

    return batches


# ── 페이즈 실행 ──────────────────────────────────────────────────

async def extract_events_from_user_stories_phase(
    ctx: IngestionWorkflowContext,
) -> AsyncGenerator[ProgressEvent, None]:
    """
    Phase: UserStory 기반 Event 추출.
    analyzer_graph: 배치 처리 (source_unit_id 기준 그룹핑)
    rfp/figma: 기존 1개씩 처리
    """
    yield ProgressEvent(
        phase=IngestionPhase.EXTRACTING_EVENTS,
        message="Event 추출 중 (User Story 기반)...",
        progress=26,
    )

    user_stories = sorted(
        ctx.user_stories or [],
        key=lambda us: getattr(us, "sequence", 999) or 999,
    )

    if not user_stories:
        return

    # BL 컨텍스트 로드
    bl_map: dict[str, list[dict]] = {}
    if getattr(ctx, "source_type", "") == "analyzer_graph":
        bl_map = getattr(ctx, "bl_by_user_story", None) or {}
        if not bl_map:
            bl_map = load_bl_for_user_stories(ctx.client)

    # analyzer_graph: 배치 처리 / 나머지: 개별 처리
    is_analyzer = getattr(ctx, "source_type", "") == "analyzer_graph"

    if is_analyzer and len(user_stories) > _BATCH_MAX_US:
        async for ev in _extract_events_batched(ctx, user_stories, bl_map):
            yield ev
    else:
        async for ev in _extract_events_single(ctx, user_stories, bl_map):
            yield ev


async def _extract_events_batched(
    ctx: IngestionWorkflowContext,
    user_stories: list[Any],
    bl_map: dict[str, list[dict]],
) -> AsyncGenerator[ProgressEvent, None]:
    """analyzer_graph 배치 처리: source_unit_id 기준 그룹핑."""
    batches = _group_us_into_batches(user_stories, bl_map)
    total_batches = len(batches)

    SmartLogger.log(
        "INFO",
        f"Event extraction: batched mode — {len(user_stories)} US → {total_batches} batches",
        category="ingestion.workflow.events_from_us.batched",
        params={
            "session_id": ctx.session.id,
            "total_us": len(user_stories),
            "total_batches": total_batches,
        },
    )

    accumulated_events: list[str] = []
    all_created_events: list[dict[str, Any]] = []
    timeline_seq = 0

    structured_llm = ctx.llm.with_structured_output(EventFromBatchList)
    display_lang = getattr(ctx, "display_language", "ko") or "ko"

    progress_base = 26
    progress_range = 20

    for batch_idx, batch in enumerate(batches):
        if getattr(ctx.session, "is_cancelled", False):
            yield ProgressEvent(
                phase=IngestionPhase.ERROR,
                message="❌ 생성이 중단되었습니다",
                progress=0,
                data={"error": "Cancelled by user", "cancelled": True},
            )
            return

        prev_text = _format_previous_events(accumulated_events)
        us_block = _build_batch_us_block(batch, bl_map)

        prompt = EXTRACT_EVENTS_BATCH_PROMPT.format(
            user_stories_block=us_block,
            previous_events=prev_text,
        )

        if display_lang == "ko":
            prompt += "\n\nFor each Event, output displayName as a short Korean label (e.g. '주문 접수됨')."
        else:
            prompt += "\n\nFor each Event, output displayName as a short English label (e.g. 'Order Placed')."

        try:
            response = await asyncio.wait_for(
                asyncio.to_thread(
                    structured_llm.invoke,
                    [SystemMessage(content=SYSTEM_PROMPT), HumanMessage(content=prompt)],
                ),
                timeout=120.0,
            )
            events = response.events or []
        except Exception as e:
            batch_ids = [getattr(us, "id", "") for us in batch]
            SmartLogger.log(
                "ERROR",
                f"Event extraction failed for batch {batch_idx + 1}/{total_batches}: {e}",
                category="ingestion.workflow.events_from_us.batch_error",
                params={
                    "session_id": ctx.session.id,
                    "batch_index": batch_idx,
                    "batch_us_ids": batch_ids[:5],
                    "error": str(e),
                },
            )
            events = []

        # 이벤트 생성 및 US 연결
        events_sorted = sorted(events, key=lambda e: getattr(e, "order", 1) or 1)
        batch_us_ids = {getattr(us, "id", "") for us in batch}
        # 기본 US ID: 배치에서 LLM이 지정한 것, 없으면 첫 번째 US
        fallback_us_id = getattr(batch[0], "id", "") if batch else ""

        for evt in events_sorted:
            evt_name = (getattr(evt, "name", "") or "").strip()
            if not evt_name or evt_name in accumulated_events:
                continue

            evt_display = getattr(evt, "displayName", "") or evt_name
            evt_desc = getattr(evt, "description", "") or ""
            evt_us_id = getattr(evt, "user_story_id", "") or ""

            # user_story_id 검증: 배치 내 US여야 함
            if evt_us_id not in batch_us_ids:
                evt_us_id = fallback_us_id

            timeline_seq += 1

            try:
                created = await asyncio.wait_for(
                    asyncio.to_thread(
                        _create_standalone_event,
                        ctx,
                        name=evt_name,
                        display_name=evt_display,
                        description=evt_desc,
                        user_story_id=evt_us_id,
                        sequence=timeline_seq,
                    ),
                    timeout=10.0,
                )

                if created:
                    accumulated_events.append(evt_name)
                    all_created_events.append(created)

                    yield ProgressEvent(
                        phase=IngestionPhase.EXTRACTING_EVENTS,
                        message=f"Event: {evt_name}",
                        progress=progress_base + int(progress_range * (batch_idx + 1) / total_batches),
                        data={
                            "type": "Event",
                            "object": {
                                "id": created.get("id"),
                                "name": evt_name,
                                "type": "Event",
                                "userStoryId": evt_us_id,
                                "sequence": timeline_seq,
                            },
                        },
                    )

            except Exception as e:
                SmartLogger.log(
                    "WARN",
                    f"Event creation failed: {evt_name} - {e}",
                    category="ingestion.workflow.events_from_us.create_error",
                    params={"session_id": ctx.session.id, "event_name": evt_name, "error": str(e)},
                )

    ctx.events_from_us = all_created_events

    SmartLogger.log(
        "INFO",
        f"Events from User Stories (batched): {len(all_created_events)} events from {total_batches} batches",
        category="ingestion.workflow.events_from_us.done",
        params={
            "session_id": ctx.session.id,
            "total_events": len(all_created_events),
            "total_batches": total_batches,
            "total_user_stories": len(user_stories),
        },
    )


async def _extract_events_single(
    ctx: IngestionWorkflowContext,
    user_stories: list[Any],
    bl_map: dict[str, list[dict]],
) -> AsyncGenerator[ProgressEvent, None]:
    """rfp/figma 개별 처리: US 1개씩 (기존 동작)."""
    accumulated_events: list[str] = []
    all_created_events: list[dict[str, Any]] = []
    timeline_seq = 0

    structured_llm = ctx.llm.with_structured_output(EventFromUSList)
    display_lang = getattr(ctx, "display_language", "ko") or "ko"

    total_us = len(user_stories)
    progress_base = 26
    progress_range = 20

    for us_idx, us in enumerate(user_stories):
        if getattr(ctx.session, "is_cancelled", False):
            yield ProgressEvent(
                phase=IngestionPhase.ERROR,
                message="❌ 생성이 중단되었습니다",
                progress=0,
                data={"error": "Cancelled by user", "cancelled": True},
            )
            return

        us_id = getattr(us, "id", "")
        role = getattr(us, "role", "")
        action = getattr(us, "action", "")
        benefit = getattr(us, "benefit", "")

        prev_text = _format_previous_events(accumulated_events)

        # BL 컨텍스트 섹션 (analyzer_graph인 경우에만)
        business_rules_section = ""
        bls = bl_map.get(us_id) if bl_map else None
        if bls:
            bl_lines = []
            for bl in bls:
                seq = bl.get("seq", "?")
                title = bl.get("title", "")
                given = bl.get("given", "")
                when = bl.get("when", "")
                then = bl.get("then", "")
                domain = bl.get("coupled_domain")
                domain_mark = f" [→ {domain}]" if domain else ""
                bl_lines.append(f"  - BL[{seq}]{domain_mark}: {title}")
                if given:
                    bl_lines.append(f"    Given: {given}")
                if when:
                    bl_lines.append(f"    When: {when}")
                if then:
                    bl_lines.append(f"    Then: {then}")
            business_rules_section = (
                "\n<business_rules>\n"
                "The following business rules are derived from legacy code analysis.\n"
                "Use these to understand the BUSINESS OUTCOMES, but do NOT create "
                "one event per rule. Consolidate related rules into high-level events.\n"
                + "\n".join(bl_lines)
                + "\n</business_rules>\n"
            )

        prompt = EXTRACT_EVENTS_FROM_US_PROMPT.format(
            us_id=us_id,
            role=role,
            action=action,
            benefit=benefit,
            business_rules_section=business_rules_section,
            previous_events=prev_text,
        )

        if display_lang == "ko":
            prompt += "\n\nFor each Event, output displayName as a short Korean label (e.g. '주문 접수됨')."
        else:
            prompt += "\n\nFor each Event, output displayName as a short English label (e.g. 'Order Placed')."

        try:
            response = await asyncio.wait_for(
                asyncio.to_thread(
                    structured_llm.invoke,
                    [SystemMessage(content=SYSTEM_PROMPT), HumanMessage(content=prompt)],
                ),
                timeout=60.0,
            )
            events = response.events or []
        except Exception as e:
            SmartLogger.log(
                "ERROR",
                f"Event extraction failed for US {us_id}: {e}",
                category="ingestion.workflow.events_from_us.error",
                params={"session_id": ctx.session.id, "us_id": us_id, "error": str(e)},
            )
            events = []

        events_sorted = sorted(events, key=lambda e: getattr(e, "order", 1) or 1)
        for evt in events_sorted:
            evt_name = (getattr(evt, "name", "") or "").strip()
            if not evt_name or evt_name in accumulated_events:
                continue

            evt_display = getattr(evt, "displayName", "") or evt_name
            evt_desc = getattr(evt, "description", "") or ""
            timeline_seq += 1

            try:
                created = await asyncio.wait_for(
                    asyncio.to_thread(
                        _create_standalone_event,
                        ctx,
                        name=evt_name,
                        display_name=evt_display,
                        description=evt_desc,
                        user_story_id=us_id,
                        sequence=timeline_seq,
                    ),
                    timeout=10.0,
                )

                if created:
                    accumulated_events.append(evt_name)
                    all_created_events.append(created)

                    yield ProgressEvent(
                        phase=IngestionPhase.EXTRACTING_EVENTS,
                        message=f"Event: {evt_name}",
                        progress=progress_base + int(progress_range * (us_idx + 1) / total_us),
                        data={
                            "type": "Event",
                            "object": {
                                "id": created.get("id"),
                                "name": evt_name,
                                "type": "Event",
                                "userStoryId": us_id,
                                "sequence": timeline_seq,
                            },
                        },
                    )

            except Exception as e:
                SmartLogger.log(
                    "WARN",
                    f"Event creation failed: {evt_name} - {e}",
                    category="ingestion.workflow.events_from_us.create_error",
                    params={"session_id": ctx.session.id, "event_name": evt_name, "error": str(e)},
                )

    ctx.events_from_us = all_created_events

    SmartLogger.log(
        "INFO",
        f"Events from User Stories: {len(all_created_events)} events created",
        category="ingestion.workflow.events_from_us.done",
        params={
            "session_id": ctx.session.id,
            "total_events": len(all_created_events),
            "total_user_stories": total_us,
        },
    )


def _create_standalone_event(
    ctx: IngestionWorkflowContext,
    *,
    name: str,
    display_name: str,
    description: str,
    user_story_id: str,
    sequence: int,
) -> dict[str, Any] | None:
    """Create Event node without Command link (standalone for Event Modeling)."""
    with ctx.client.session() as session:
        query = """
        MERGE (evt:Event {name: $name})
        ON CREATE SET evt.id = randomUUID(),
                      evt.createdAt = datetime()
        SET evt.name = $name,
            evt.displayName = $display_name,
            evt.description = $description,
            evt.userStoryId = $user_story_id,
            evt.sequence = $sequence,
            evt.version = '1.0.0',
            evt.isBreaking = false,
            evt.updatedAt = datetime()
        RETURN evt {.id, .name, .displayName, .description, .userStoryId, .sequence} as event
        """
        result = session.run(
            query,
            name=name,
            display_name=display_name,
            description=description,
            user_story_id=user_story_id,
            sequence=sequence,
        )
        record = result.single()
        if record:
            evt_id = record["event"]["id"]
            session.run(
                """
                MATCH (evt:Event {id: $evt_id})
                MATCH (us:UserStory {id: $us_id})
                MERGE (us)-[:HAS_EVENT]->(evt)
                """,
                evt_id=evt_id,
                us_id=user_story_id,
            )
            return dict(record["event"])
        return None
