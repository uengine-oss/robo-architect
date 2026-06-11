from __future__ import annotations

import json

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from starlette.requests import Request

from api.features.proposal_lifecycle.services.intent_runner import stream_intent
from api.platform.observability.smart_logger import SmartLogger

router = APIRouter()


@router.get("/stream/{proposal_id}/intent")
async def stream_intent_sse(proposal_id: str, request: Request):
    """인텐트 분해 + Impact Map 진행 상황을 SSE로 스트리밍한다."""

    async def event_stream():
        async for event_type, data in stream_intent(proposal_id):
            payload = json.dumps(data, ensure_ascii=False)
            yield f"event: {event_type}\ndata: {payload}\n\n"

    SmartLogger.log("INFO", f"SSE intent stream started: {proposal_id}",
                    category="proposal_lifecycle.intent.stream_start",
                    params={"proposalId": proposal_id})

    return StreamingResponse(event_stream(), media_type="text/event-stream")
