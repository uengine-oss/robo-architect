"""Impact report routes (026 — requirements-tab).

Non-blocking: requirement mutations register a report and return its id
immediately; the frontend polls (or streams) here for the result.
"""

from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter, HTTPException
from starlette.requests import Request
from starlette.responses import StreamingResponse

from api.features.requirements.impact_hook import get_report
from api.features.requirements.requirements_contracts import ImpactReportDTO
from api.platform.observability.request_logging import http_context
from api.platform.observability.smart_logger import SmartLogger

router = APIRouter()


@router.get("/impact-report/{report_id}", response_model=ImpactReportDTO)
async def get_impact_report(report_id: str, request: Request) -> ImpactReportDTO:
    """Fetch an impact report by id (poll until status is done/failed)."""
    report = get_report(report_id)
    if report is None:
        raise HTTPException(status_code=404, detail=f"Impact report {report_id} not found")
    SmartLogger.log(
        "INFO",
        "Impact report fetched.",
        category="requirements.impact.fetch",
        params={**http_context(request), "report_id": report_id, "status": report.status},
    )
    return report


@router.get("/impact-report/{report_id}/stream")
async def stream_impact_report(report_id: str) -> StreamingResponse:
    """Stream an impact report via SSE until it reaches a terminal state."""
    if get_report(report_id) is None:
        raise HTTPException(status_code=404, detail=f"Impact report {report_id} not found")

    async def _gen():
        for _ in range(120):  # ~60s cap
            report = get_report(report_id)
            if report is None:
                break
            yield f"data: {json.dumps(report.model_dump())}\n\n"
            if report.status in ("done", "failed"):
                break
            await asyncio.sleep(0.5)

    return StreamingResponse(_gen(), media_type="text/event-stream")
