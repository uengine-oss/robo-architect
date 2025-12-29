from __future__ import annotations

import asyncio
from typing import AsyncGenerator

from api.features.ingestion.ingestion_contracts import IngestionPhase, ProgressEvent
from api.features.ingestion.workflow.ingestion_workflow_context import IngestionWorkflowContext


async def parsing_phase(ctx: IngestionWorkflowContext) -> AsyncGenerator[ProgressEvent, None]:
    """
    Phase 1: parsing (UI feedback + basic validation in the future).
    """
    yield ProgressEvent(phase=IngestionPhase.PARSING, message="문서 파싱 중...", progress=5)
    await asyncio.sleep(0.3)


