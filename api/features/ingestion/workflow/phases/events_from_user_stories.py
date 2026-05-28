"""
Phase: Extract Events from User Stories (Event Modeling 방식)

기존 Command 기반이 아닌, UserStory 기반으로 Event를 추출.
각 UserStory에서 발생할 수 있는 비즈니스 이벤트들을 도출.
Event는 Command 없이 독립적으로 생성되며, 이후 Command가 역도출됨.
"""

from __future__ import annotations

import asyncio
import re
from typing import Any, AsyncGenerator

from langchain_core.messages import HumanMessage
from api.platform.llm_messages import build_system_message
from pydantic import BaseModel, Field

from api.features.ingestion.ingestion_contracts import IngestionPhase, ProgressEvent
from api.features.ingestion.workflow.ingestion_workflow_context import IngestionWorkflowContext
from api.features.ingestion.workflow.utils.chunking import estimate_tokens
from api.platform.observability.smart_logger import SmartLogger


def _event_key(name: str) -> str:
    """Stable lowercase slug from Event.name for properties-phase mapping.

    properties.py builds parent_id_by_key[("Event", ek)] = eid where `ek` reads
    `evt.key`. Without this, all Events fall out of the mapping and end up
    with zero HAS_PROPERTY edges, leaving GWT.thenFieldValues empty.
    """
    return re.sub(r"[^a-zA-Z0-9]+", "_", name or "").strip("_").lower() or "event"

# Token budget for accumulated previous events injected into each prompt.
_PREV_EVENTS_BUDGET_TOKENS = 4000
_PREV_EVENTS_RECENT_COUNT = 30


# ── LLM 출력 스키마 ──────────────────────────────────────────────

class EventFromUS(BaseModel):
    """UserStory에서 도출된 Event."""
    name: str = Field(..., description="Event name in PascalCase past tense (e.g., OrderPlaced, PaymentConfirmed)")
    displayName: str = Field(default="", description="UI label in chosen language")
    description: str = Field(..., description="What business fact occurred")
    order: int = Field(default=1, description="Chronological order within this user story (1=first, 2=second, ...)")


class EventFromUSList(BaseModel):
    events: list[EventFromUS] = Field(default_factory=list)


# ── 프롬프트 ──────────────────────────────────────────────────────

SYSTEM_PROMPT = "You are a Domain-Driven Design expert identifying business events from user stories for Event Modeling."

EXTRACT_EVENTS_FROM_US_PROMPT = """Identify all business Events that would occur when the following User Story is fulfilled.

<user_story>
ID: {us_id}
Role: {role}
Action: {action}
Benefit: {benefit}
</user_story>

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
7. Typically 1~3 events per user story. Keep focused.
8. **order**: Assign chronological order within this user story. If this story involves multiple steps (e.g., place order → then payment), the first event gets order=1, the next order=2. Failure events share the same order as their success counterpart.
</rules>

Return the events for this user story."""


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


# ── 페이즈 실행 ──────────────────────────────────────────────────

async def extract_events_from_user_stories_phase(
    ctx: IngestionWorkflowContext,
) -> AsyncGenerator[ProgressEvent, None]:
    """Phase: UserStory 기반 Event 추출 (US 1개씩 처리)."""
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

        prompt = EXTRACT_EVENTS_FROM_US_PROMPT.format(
            us_id=us_id,
            role=role,
            action=action,
            benefit=benefit,
            previous_events=prev_text,
        )

        if display_lang == "ko":
            prompt += "\n\nFor each Event, output displayName as a short Korean label (e.g. '주문 접수됨')."
        else:
            prompt += "\n\nFor each Event, output displayName as a short English label (e.g. 'Order Placed')."

        # ─── Hybrid input boost — append BL info per US to LLM input ────────
        # Each Rule's writes.op (INSERT/UPDATE/DELETE) directly drives the
        # Event's PastParticiple choice (Recorded/Updated/Removed). The
        # canonical Example GWT becomes the Event's acceptance test seed.
        # See Phase5_EventStorming_Promotion_PRD §12 (v3 input boost).
        if getattr(ctx, "source_type", "") == "hybrid" and getattr(ctx, "hybrid_us_rules", None):
            try:
                from api.features.ingestion.hybrid.bpm_context_builder import (
                    render_hybrid_bl_block,
                )
                _bl_block = render_hybrid_bl_block(ctx.hybrid_us_rules, {us_id})
                if _bl_block:
                    prompt += _bl_block
                    prompt += (
                        "\n\nINSTRUCTION: BL.writes.op 를 보고 Event 이름을 결정하세요. "
                        "INSERT → ...Recorded/Created, UPDATE → ...Updated/Adjusted, "
                        "DELETE → ...Removed/Cancelled. 각 Rule 의 statement 가 한 Event 의 "
                        "도메인 의도, AFFECTS_TABLE 의 table 명이 Aggregate 이름의 근거입니다."
                    )
            except Exception:
                pass  # fall back to US-text-only prompt

        try:
            response = await asyncio.wait_for(
                asyncio.to_thread(
                    structured_llm.invoke,
                    [build_system_message(SYSTEM_PROMPT), HumanMessage(content=prompt)],
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
    """Create Event node without Command link (standalone for Event Modeling).

    `evt.key` is set so the downstream properties phase (properties.py)
    can map (parentType=Event, parentKey=ek) → eid for HAS_PROPERTY
    creation. Aggregate/Command set their key elsewhere; Events were
    missing it — see hand-off doc §3.8 for the GWT thenFieldValues fix.
    """
    event_key = _event_key(name)
    with ctx.client.session() as session:
        query = """
        MERGE (evt:Event {name: $name})
        ON CREATE SET evt.id = randomUUID(),
                      evt.createdAt = datetime()
        SET evt.name = $name,
            evt.key = $key,
            evt.displayName = $display_name,
            evt.description = $description,
            evt.userStoryId = $user_story_id,
            evt.sequence = $sequence,
            evt.version = '1.0.0',
            evt.isBreaking = false,
            evt.updatedAt = datetime()
        RETURN evt {.id, .name, .key, .displayName, .description, .userStoryId, .sequence} as event
        """
        result = session.run(
            query,
            name=name,
            key=event_key,
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
