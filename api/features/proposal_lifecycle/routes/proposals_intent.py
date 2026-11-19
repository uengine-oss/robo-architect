from __future__ import annotations

import json

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from starlette.requests import Request

from api.features.proposal_lifecycle.services import detached_runs
from api.features.proposal_lifecycle.services.intent_runner import stream_intent
from api.platform.observability.smart_logger import SmartLogger

router = APIRouter()


_intent_key = detached_runs.intent_key


def _sse(event_type: str, data: dict) -> str:
    return f"event: {event_type}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


@router.get("/stream/{proposal_id}/intent")
async def stream_intent_sse(proposal_id: str, request: Request, attach: bool = False):
    """인텐트 분해 + Impact Map 진행 상황을 SSE로 스트리밍한다.

    분해는 연결과 떨어져 돈다(`detached_runs`) — 화면이 끊겨도 계속 돌고, 다시 붙으면 처음부터
    다시 받는다. 같은 proposal 의 분해가 돌고 있으면 새로 시작하지 않고 거기에 붙는다.

    `attach=true` 는 **시작하지 않는다** — 돌고 있거나 막 끝난 분해에만 붙고, 없으면 `idle` 하나를
    보내고 닫는다(돌아온 화면이 진행을 되찾을 때 쓴다).
    """
    key = _intent_key(proposal_id)
    if attach:
        run = detached_runs.get_run(key)
        if run is None:
            async def idle_stream():
                yield _sse("idle", {"proposalId": proposal_id})
            return StreamingResponse(idle_stream(), media_type="text/event-stream")
    else:
        run = detached_runs.start_or_join(key, lambda: stream_intent(proposal_id))

    async def event_stream():
        async for event_type, data in run.follow():
            yield _sse(event_type, data)

    SmartLogger.log("INFO", f"SSE intent stream {'attached' if attach else 'started'}: {proposal_id}",
                    category="proposal_lifecycle.intent.stream_start",
                    params={"proposalId": proposal_id, "attach": attach})

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.get("/stream/{proposal_id}/intent/status")
async def intent_run_status(proposal_id: str):
    """분해가 돌고 있는지 — 화면이 돌아왔을 때 다시 붙을지 정한다."""
    run = detached_runs.get_run(_intent_key(proposal_id))
    if run is None:
        return {"running": False, "finished": False, "cancelled": False, "events": 0, "lastEvent": None}
    return run.status()


@router.delete("/stream/{proposal_id}/intent")
async def cancel_intent(proposal_id: str):
    """「분석 중지」 — 연결을 끊어도 분해가 멈추지 않으므로 따로 멈춘다."""
    return {"cancelled": detached_runs.cancel(_intent_key(proposal_id))}
