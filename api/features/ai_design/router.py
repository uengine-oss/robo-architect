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
    from langchain_core.messages import HumanMessage, SystemMessage

    from api.platform.neo4j import get_session
    from api.platform.llm import get_llm
    from api.platform.ui_wireframe_template import normalize_ui_template

    body: dict[str, Any] = {}
    try:
        body = await req.json()
    except Exception:
        pass
    instruction = (body.get("instruction") or "").strip()
    display_lang = body.get("display_language", "ko")

    # Fetch UI node context.
    with get_session() as session:
        rec = session.run(
            """
            MATCH (ui:UI {id: $id})
            OPTIONAL MATCH (bc:BoundedContext)-[:HAS_UI]->(ui)
            RETURN ui.name AS name, ui.displayName AS displayName,
                   ui.description AS description,
                   ui.attachedToType AS attachedToType,
                   ui.attachedToName AS attachedToName,
                   ui.template AS template,
                   bc.name AS bcName
            """,
            id=ui_node_id,
        ).single()
    if not rec:
        raise HTTPException(status_code=404, detail=f"UI node {ui_node_id} not found")

    ui_name = rec.get("displayName") or rec.get("name") or "Wireframe"
    ui_desc = rec.get("description") or ""
    attached_type = rec.get("attachedToType") or ""
    attached_name = rec.get("attachedToName") or ""
    bc_name = rec.get("bcName") or ""
    existing_template = rec.get("template") or ""

    lang_instruction = (
        "All visible text MUST be written in Korean (한글)."
        if display_lang == "ko"
        else "All visible text MUST be written in English."
    )

    system_prompt = (
        "You generate a modern UI wireframe as an HTML fragment for a single "
        "screen (Ant Design / Material-like). Output rules (STRICT):\n"
        "- Output ONLY the HTML fragment. No markdown fences, no <html>/<head>/<body>.\n"
        "- Wrap everything in a single <div class=\"wf-root\">…</div>.\n"
        "- Use semantic class names (wf-appbar, wf-card, wf-table, wf-input, "
        "wf-btn, wf-btn--primary) and an inline <style> scoped under .wf-root.\n"
        "- No external resources (no <script>, no url(), no @import, no on* handlers).\n"
        f"- {lang_instruction}\n"
    )

    context = (
        f"Screen: {ui_name}\n"
        + (f"Bounded Context: {bc_name}\n" if bc_name else "")
        + (f"Attached to: {attached_type} {attached_name}\n" if attached_name else "")
        + (f"Description: {ui_desc}\n" if ui_desc else "")
    )

    if instruction and existing_template:
        user_prompt = (
            f"{context}\n"
            "Here is the CURRENT wireframe HTML:\n"
            f"```html\n{existing_template}\n```\n\n"
            f"Apply this change and return the FULL updated HTML fragment:\n{instruction}"
        )
    elif instruction:
        user_prompt = f"{context}\nCreate a wireframe with this requirement:\n{instruction}"
    else:
        user_prompt = (
            f"{context}\nCreate a clean, realistic wireframe for this screen. "
            "Use labels and placeholders that fit the domain, not generic ones."
        )

    try:
        llm = get_llm()
        resp = llm.invoke([SystemMessage(content=system_prompt), HumanMessage(content=user_prompt)])
        raw_html = resp if isinstance(resp, str) else getattr(resp, "content", str(resp))
        if not isinstance(raw_html, str):
            raw_html = str(raw_html)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"LLM 호출 실패: {e}") from e

    template, _report = normalize_ui_template(raw_html, ui_name=ui_name)

    with get_session() as session:
        session.run(
            "MATCH (ui:UI {id: $id}) SET ui.template = $tmpl, ui.updatedAt = datetime()",
            id=ui_node_id,
            tmpl=template,
        )

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
