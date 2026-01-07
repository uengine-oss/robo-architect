from __future__ import annotations

import asyncio
from typing import AsyncGenerator

from api.features.ingestion.ingestion_contracts import IngestionPhase, ProgressEvent
from api.features.ingestion.requirements_to_user_stories import (
    ensure_nonempty_ui_description,
    extract_user_stories_from_text,
)
from api.features.ingestion.workflow.ingestion_workflow_context import IngestionWorkflowContext
from api.platform.observability.smart_logger import SmartLogger


async def extract_user_stories_phase(ctx: IngestionWorkflowContext) -> AsyncGenerator[ProgressEvent, None]:
    """
    Phase 2: extract user stories and persist them to Neo4j.
    """
    yield ProgressEvent(phase=IngestionPhase.EXTRACTING_USER_STORIES, message="User Story 추출 중...", progress=10)

    user_stories = extract_user_stories_from_text(ctx.content)
    ctx.user_stories = user_stories

    SmartLogger.log(
        "INFO",
        "User stories extracted",
        category="ingestion.workflow.user_stories",
        params={"session_id": ctx.session.id, "user_stories": user_stories},
    )

    for i, us in enumerate(user_stories):
        ui_desc = ensure_nonempty_ui_description(
            getattr(us, "role", None),
            getattr(us, "action", None),
            getattr(us, "benefit", None),
            getattr(us, "ui_description", None),
        )
        try:
            ctx.client.create_user_story(
                id=us.id,
                role=us.role,
                action=us.action,
                benefit=us.benefit,
                priority=us.priority,
                status="draft",
                ui_description=ui_desc,
            )

            yield ProgressEvent(
                phase=IngestionPhase.EXTRACTING_USER_STORIES,
                message=f"User Story 생성: {us.id}",
                progress=10 + (10 * (i + 1) // max(len(user_stories), 1)),
                data={
                    "type": "UserStory",
                    "object": {
                        "id": us.id,
                        "name": f"{us.role}: {us.action[:30]}...",
                        "type": "UserStory",
                        "role": us.role,
                        "action": us.action,
                        "benefit": us.benefit,
                        "priority": us.priority,
                        "ui_description": ui_desc,
                    },
                },
            )
            await asyncio.sleep(0.15)
        except Exception as e:
            SmartLogger.log(
                "WARNING",
                "User story create skipped",
                category="ingestion.neo4j.user_story",
                params={"session_id": ctx.session.id, "id": us.id, "error": str(e)},
            )

    yield ProgressEvent(
        phase=IngestionPhase.EXTRACTING_USER_STORIES,
        message=f"{len(user_stories)}개 User Story 추출 완료",
        progress=20,
        data={
            "count": len(user_stories),
            "items": [{"id": us.id, "role": us.role, "action": us.action[:50]} for us in user_stories],
        },
    )


