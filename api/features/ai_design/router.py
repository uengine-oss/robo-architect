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


@router.post("/html-edit/{ui_node_id}")
async def html_edit(ui_node_id: str, req: Request) -> dict[str, Any]:
    """Generate or edit a UI node's HTML wireframe template via a prompt.

    Body: { instruction?: str, display_language?: "ko"|"en" }
      - instruction empty  → generate a fresh wireframe from the node's context.
      - instruction present → edit the EXISTING template per the instruction.

    Reads the UI node from Neo4j, invokes the shared LLM, normalizes the HTML
    fragment, persists `ui.template`, and returns the new template.
    """
    from fastapi import HTTPException

    from .html_template import TemplateGenerationError, UINodeNotFound, generate_html_template

    body: dict[str, Any] = {}
    try:
        body = await req.json()
    except Exception:
        pass
    instruction = (body.get("instruction") or "").strip()
    display_lang = body.get("display_language", "ko")

    # 생성기는 html_template 하나다 — 프로포절 Accept 뒤 일괄 생성(D-5 ⑰)도 같은 것을 쓴다.
    try:
        template = await generate_html_template(ui_node_id, instruction, display_lang)
    except UINodeNotFound as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except TemplateGenerationError as e:
        raise HTTPException(status_code=502, detail=str(e)) from e

    return {"ok": True, "template": template}


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
