from __future__ import annotations

import json

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from starlette.requests import Request

from api.features.proposal_lifecycle.services.tasks_runner import stream_tasks, load_tasks
from api.platform.observability.smart_logger import SmartLogger

router = APIRouter()


@router.get("/stream/{proposal_id}/tasks")
async def stream_tasks_sse(proposal_id: str, request: Request):
    """
    구현 작업 분해 진행을 SSE로 스트리밍한다 (인텐트 분해와 동일 방식).
    셸이 아니라 proposal 쪽에서 헤드리스 서브프로세스로 작업을 미리 뽑아 보여준다.
    """

    async def event_stream():
        async for event_type, data in stream_tasks(proposal_id):
            payload = json.dumps(data, ensure_ascii=False)
            yield f"event: {event_type}\ndata: {payload}\n\n"

    SmartLogger.log("INFO", f"SSE tasks stream started: {proposal_id}",
                    category="proposal_lifecycle.tasks.stream_start",
                    params={"proposalId": proposal_id})

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.get("/{proposal_id}/tasks")
async def get_tasks(proposal_id: str):
    """저장된 작업 목록 + 렌더된 speckit 마크다운을 반환한다(재방문 시 재표시용)."""
    result = load_tasks(proposal_id)
    result["proposalId"] = proposal_id
    return result
