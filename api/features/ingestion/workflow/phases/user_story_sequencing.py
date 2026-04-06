"""
Phase: User Story Sequencing

전체 UserStory 추출 완료 후, LLM에 비즈니스 흐름 순서를 한번에 할당 요청.
요약본(역할+행위)만 전달하여 토큰 절감.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any, AsyncGenerator

from langchain_core.messages import HumanMessage, SystemMessage

from api.features.ingestion.ingestion_contracts import IngestionPhase, ProgressEvent
from api.features.ingestion.workflow.ingestion_workflow_context import IngestionWorkflowContext
from api.platform.observability.smart_logger import SmartLogger


SEQUENCE_SYSTEM_PROMPT = """You are a business process analyst. Your task is to assign a time-based sequence order to user stories based on the natural business flow."""

SEQUENCE_PROMPT = """Assign a sequence number to each user story based on when it would occur in the overall business flow timeline.

Rules:
- Start from 1 (earliest in the business journey)
- User stories that happen at the same logical step share the same number
- Consider the natural user journey: onboarding → authentication → browsing → selection → order → payment → fulfillment → review → support
- Registration/signup comes before login
- Login comes before authenticated actions
- Browsing/search comes before purchase
- Order comes before payment
- Payment comes before delivery/fulfillment
- Main flow comes before exception handling (refund, complaint, etc.)

User Stories:
{user_stories_text}

Return ONLY a JSON object mapping user story IDs to sequence numbers.
Example: {{"US-001": 1, "US-002": 2, "US-003": 2, "US-004": 3}}"""


async def assign_user_story_sequences_phase(
    ctx: IngestionWorkflowContext,
) -> AsyncGenerator[ProgressEvent, None]:
    """
    Phase: UserStory 추출 후 비즈니스 흐름 순서 할당.
    """
    yield ProgressEvent(
        phase=IngestionPhase.EXTRACTING_USER_STORIES,
        message="User Story 순서 할당 중...",
        progress=22,
    )

    user_stories = ctx.user_stories or []
    if not user_stories:
        return

    # 요약본 구성 (ID + 역할 + 행위만)
    lines = []
    for us in user_stories:
        us_id = getattr(us, "id", "") or ""
        role = getattr(us, "role", "") or ""
        action = getattr(us, "action", "") or ""
        lines.append(f"- [{us_id}] As a {role}, I want to {action}")

    user_stories_text = "\n".join(lines)

    prompt = SEQUENCE_PROMPT.format(user_stories_text=user_stories_text)

    try:
        response = await asyncio.wait_for(
            asyncio.to_thread(
                ctx.llm.invoke,
                [
                    SystemMessage(content=SEQUENCE_SYSTEM_PROMPT),
                    HumanMessage(content=prompt),
                ],
            ),
            timeout=120.0,
        )

        content = response.content.strip()
        # Parse JSON (handle markdown code blocks)
        if content.startswith("```"):
            content = content.split("\n", 1)[1].rsplit("```", 1)[0].strip()

        mapping = json.loads(content)

        # Apply sequences to user stories and update Neo4j
        updated = 0
        for us in user_stories:
            us_id = getattr(us, "id", "")
            seq = mapping.get(us_id)
            if seq is not None:
                us.sequence = int(seq)
                # Update Neo4j
                try:
                    await asyncio.wait_for(
                        asyncio.to_thread(
                            _update_us_sequence, ctx, us_id, int(seq)
                        ),
                        timeout=5.0,
                    )
                    updated += 1
                except Exception:
                    pass

        SmartLogger.log(
            "INFO",
            f"User Story sequences assigned: {updated}/{len(user_stories)}",
            category="ingestion.workflow.us_sequencing.done",
            params={
                "session_id": ctx.session.id,
                "total": len(user_stories),
                "updated": updated,
                "max_sequence": max(mapping.values()) if mapping else 0,
            },
        )

        yield ProgressEvent(
            phase=IngestionPhase.EXTRACTING_USER_STORIES,
            message=f"User Story 순서 할당 완료: {updated}개",
            progress=24,
        )

    except asyncio.TimeoutError:
        SmartLogger.log(
            "ERROR",
            "User Story sequencing timed out",
            category="ingestion.workflow.us_sequencing.timeout",
            params={"session_id": ctx.session.id},
        )
    except Exception as e:
        SmartLogger.log(
            "ERROR",
            f"User Story sequencing failed: {e}",
            category="ingestion.workflow.us_sequencing.error",
            params={"session_id": ctx.session.id, "error": str(e)},
        )


def _update_us_sequence(ctx: IngestionWorkflowContext, us_id: str, sequence: int) -> None:
    """Update sequence on UserStory node in Neo4j."""
    with ctx.client.session() as session:
        session.run(
            "MATCH (us:UserStory {id: $id}) SET us.sequence = $seq, us.updatedAt = datetime()",
            id=us_id,
            seq=sequence,
        )
