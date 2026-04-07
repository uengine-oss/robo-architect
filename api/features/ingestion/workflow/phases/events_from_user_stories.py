"""
Phase: Extract Events from User Stories (Event Modeling 방식)

기존 Command 기반이 아닌, UserStory 기반으로 Event를 추출.
각 UserStory에서 발생할 수 있는 비즈니스 이벤트들을 도출.
Event는 Command 없이 독립적으로 생성되며, 이후 Command가 역도출됨.
"""

from __future__ import annotations

import asyncio
import time
from typing import Any, AsyncGenerator

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from api.features.ingestion.ingestion_contracts import IngestionPhase, ProgressEvent
from api.features.ingestion.workflow.ingestion_workflow_context import IngestionWorkflowContext
from api.platform.env import get_llm_provider_model
from api.platform.observability.smart_logger import SmartLogger


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
6. Do NOT duplicate events from the previously generated list. If a prior event covers this story, skip it.
7. Typically 1~3 events per user story. Keep focused.
8. **order**: Assign chronological order within this user story. If this story involves multiple steps (e.g., place order → then payment), the first event gets order=1, the next order=2. Failure events share the same order as their success counterpart.
</rules>

Return the events for this user story."""


# ── 페이즈 실행 ──────────────────────────────────────────────────

async def extract_events_from_user_stories_phase(
    ctx: IngestionWorkflowContext,
) -> AsyncGenerator[ProgressEvent, None]:
    """
    Phase: UserStory 단위로 Event 추출.
    UserStory.sequence 순서대로 처리하여 이전 이벤트를 누적 전달.
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

    # 누적 이벤트 목록 (이전 US에서 생성된 것)
    accumulated_events: list[str] = []
    all_created_events: list[dict[str, Any]] = []
    # 타임라인 열: US 순서대로 처리하며 이벤트마다 1씩 증가 (캔버스 X축 고유 열)
    timeline_seq = 0

    structured_llm = ctx.llm.with_structured_output(EventFromUSList)
    display_lang = getattr(ctx, "display_language", "ko") or "ko"

    total_us = len(user_stories)
    progress_base = 26
    progress_range = 20  # 26% ~ 46%

    for us_idx, us in enumerate(user_stories):
        # Cancellation check
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

        # 이전 이벤트 목록 텍스트
        prev_text = "\n".join(f"- {e}" for e in accumulated_events) if accumulated_events else "(none)"

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

        # US 내 시간순 정렬 후 저장
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

    # Store in context for later phases
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
            # Link to UserStory
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
