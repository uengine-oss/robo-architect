from __future__ import annotations

import asyncio
from typing import AsyncGenerator

from api.features.ingestion.ingestion_contracts import IngestionPhase, ProgressEvent
from api.features.ingestion.workflow.ingestion_workflow_context import IngestionWorkflowContext


async def parsing_phase(ctx: IngestionWorkflowContext) -> AsyncGenerator[ProgressEvent, None]:
    """
    Phase 1: parsing (UI feedback + basic validation in the future).
    """
    if ctx.source_type == "figma":
        yield ProgressEvent(phase=IngestionPhase.PARSING, message="Figma UI 요소 파싱 중...", progress=5)
    elif ctx.source_type == "hybrid":
        yield ProgressEvent(
            phase=IngestionPhase.PARSING,
            message="BPM 스냅샷 로드 중 (Phase 5 — Event Storming 승격)...",
            progress=5,
        )
    else:
        yield ProgressEvent(phase=IngestionPhase.PARSING, message="문서 파싱 중...", progress=5)
    await asyncio.sleep(0.3)


