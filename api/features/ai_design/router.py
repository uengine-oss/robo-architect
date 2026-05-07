"""FastAPI router for /api/ai-design/* endpoints.

Two surfaces:
  - Bootstrap: GET /info → tells the frontend how to wire open-pencil.
  - OpenAI-compat: POST /v1/chat/completions → streams an OpenAI Chat Completions
    response, internally backed by api/platform/llm.py.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from . import service, wireframe_agent


router = APIRouter(prefix="/api/ai-design", tags=["ai-design"])


@router.get("/health")
async def get_health() -> dict[str, Any]:
    """Ops/debug only — frontend bootstrap does NOT call this."""
    return service.get_health()


@router.post("/wireframe/{ui_node_id}")
async def generate_wireframe(ui_node_id: str) -> StreamingResponse:
    """Backend-driven wireframe generation for a single UI node.

    Streams SSE events while the LLM agent runs (bind_tools: render, calc),
    then persists the resulting sceneGraph to the UI node in Neo4j.
    Body is unused for Phase 1 — the only mode is HTML (save sceneGraph).
    Figma-mode push lands in Phase 2 alongside spec 016 US3.
    """
    return StreamingResponse(
        wireframe_agent.stream_generate_wireframe(ui_node_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/v1/chat/completions")
async def chat_completions(req: Request) -> StreamingResponse:
    """OpenAI-compatible Chat Completions endpoint (streaming-first).

    Note: we accept the request body via `req.json()` so we can be lenient
    about Pydantic schema drift between OpenAI versions. If `stream=false`
    is requested we still stream — open-pencil's `@ai-sdk/vue` always uses
    streaming, and rewriting non-streaming would be wasted code today.
    """
    payload = await req.json()
    return StreamingResponse(
        service.stream_chat_completion(payload),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "X-Accel-Buffering": "no",
        },
    )
