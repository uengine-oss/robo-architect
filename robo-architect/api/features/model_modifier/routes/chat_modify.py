from __future__ import annotations

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from starlette.requests import Request

from api.features.model_modifier.chat_contracts import ModifyRequest
from api.features.model_modifier.chat_runtime_settings import AI_AUDIT_LOG_ENABLED, OPENAI_MODEL
from api.features.model_modifier.react_streaming import stream_react_response
from api.platform.observability.request_logging import http_context, sha256_text, summarize_for_log
from api.platform.observability.smart_logger import SmartLogger

router = APIRouter()


@router.post("/modify")
async def modify_nodes(request: ModifyRequest, http_request: Request):
    if not request.selectedNodes:
        raise HTTPException(status_code=400, detail="No nodes selected")
    if not request.prompt.strip():
        raise HTTPException(status_code=400, detail="Prompt is required")

    if AI_AUDIT_LOG_ENABLED:
        SmartLogger.log(
            "INFO",
            "Chat modify requested.",
            category="api.chat.modify.request",
            params={
                **http_context(http_request),
                "inputs": {
                    "model": OPENAI_MODEL,
                    "selected_nodes_count": len(request.selectedNodes),
                    "conversation_history_count": len(request.conversationHistory or []),
                    "prompt": request.prompt,
                    "prompt_sha256": sha256_text(request.prompt),
                    "prompt_len": len(request.prompt),
                    "selectedNodes": summarize_for_log(request.selectedNodes),
                    "conversationHistory": summarize_for_log(request.conversationHistory),
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


