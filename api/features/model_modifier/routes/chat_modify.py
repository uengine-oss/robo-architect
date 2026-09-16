from __future__ import annotations

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from starlette.requests import Request

from api.features.collab.guard import ensure_not_locked_by_other
from api.features.model_modifier.chat_contracts import ModifyRequest
from api.features.model_modifier.react_streaming import stream_react_response
from api.platform.env import AI_AUDIT_LOG_ENABLED
from api.platform.observability.request_logging import http_context, summarize_for_log
from api.platform.observability.smart_logger import SmartLogger

router = APIRouter()


@router.post("/modify")
async def modify_nodes(request: ModifyRequest, http_request: Request):
    # Require node selection even during ingestion pause (to avoid context size issues)
    # Users should select nodes from explorer or drag-drop to chat
    if not request.selectedNodes:
        raise HTTPException(status_code=400, detail="No nodes selected. Please select nodes from explorer or canvas before making modification requests.")
    if not request.prompt.strip():
        raise HTTPException(status_code=400, detail="Prompt is required")

    # 고르는 순간 막는다 — 초안을 다 만든 뒤 `/confirm` 에서 튕기면 늦다.
    # 사람은 LLM 을 한 번 돌리고 나서야 못 쓴다는 것을 알게 되고, 그동안
    # 남이 고치고 있던 내용 위에 쓸 초안을 붙들고 있다.
    #
    # 여기는 읽기 전용(초안만 낸다)이라 "덮어쓰기"는 아니지만, **쓸 수 없는
    # 것을 고치라고 시키는 길**을 열어 두는 것 자체가 문제다. 잡은 사람과
    # 아무도 안 잡은 경우는 그대로 통과한다 — `collab/guard.py` 참고.
    ensure_not_locked_by_other(
        http_request,
        [str(n.get("id") or "") for n in (request.selectedNodes or []) if isinstance(n, dict)],
    )

    if AI_AUDIT_LOG_ENABLED:
        SmartLogger.log(
            "INFO",
            "Chat modify requested.",
            category="api.chat.modify.request",
            params={
                **http_context(http_request),
                "inputs": {
                    "prompt": request.prompt,
                    "selectedNodes": summarize_for_log(
                        request.selectedNodes, max_list=5000, max_dict_items=5000
                    ),
                    "conversationHistory": summarize_for_log(
                        request.conversationHistory, max_list=5000, max_dict_items=5000
                    ),
                },
            },
        )

    async def generate():
        async for event in stream_react_response(request.prompt, request.selectedNodes, request.conversationHistory):
            yield event
        yield "data: [DONE]\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


