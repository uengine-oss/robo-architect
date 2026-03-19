"""
Regenerate UI wireframe from a screenshot using a vision-capable LLM.

- Accepts image upload + ui_id.
- Loads UI node from Neo4j, invokes vision LLM to produce wireframe HTML.
- Normalizes and applies template update, returns new template.
"""

from __future__ import annotations

import base64
import asyncio
import uuid
from typing import Any

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from langchain_core.messages import HumanMessage, SystemMessage

from api.features.model_modifier.model_change_application import apply_confirmed_changes_atomic
from api.platform.neo4j import get_session
from api.platform.llm import get_llm
from api.platform.env import env_str
from api.platform.ui_wireframe_template import normalize_ui_template
from api.platform.observability.smart_logger import SmartLogger

router = APIRouter()

# Reuse same output rules as ingestion wireframe phase
_UI_WIREFRAME_SYSTEM_PROMPT = """You generate a modern UI wireframe HTML fragment for a single screen based on a provided screenshot.

Output rules (STRICT):
- Output ONLY raw HTML fragment. Do NOT use markdown or code fences.
- Do NOT output <!doctype>, <html>, <head>, <body>.
- Do NOT include <script> tags.
- Do NOT include inline event handlers like onclick=, onload=, etc.
- Do NOT use javascript: URLs.
- You MAY include a <style> block, but:
  - Every selector MUST be scoped under `.wf-root`
  - MUST NOT use @import or url(...)

Root container (MUST):
- The fragment MUST start with a root container like:
  <div class="wf-root wf-theme-ant" data-wf-root="1"> ... </div>
  or
  <div class="wf-root wf-theme-material" data-wf-root="1"> ... </div>

Visual fidelity requirements (IMPORTANT — faithfully reproduce the screenshot):
- LAYOUT: Reproduce the exact arrangement — sidebar, top bar, content area, card grid, split pane, etc. Match the number of sections, columns, rows, and their relative sizes.
- COLOR SCHEME: Extract the primary, secondary, accent, and background colors from the screenshot and apply them via a scoped <style> block. Match header/navbar background color, button colors, card backgrounds, border colors, text colors, and any accent/highlight colors as closely as possible.
- TYPOGRAPHY HIERARCHY: Preserve heading sizes, font weights, and text contrast as seen in the image.
- SPACING & PROPORTIONS: Match padding, margins, gaps, and the relative sizing of elements (e.g. sidebar width vs main content).
- COMPONENT TYPES: Use the same kind of components visible in the image (tables, cards, forms, tabs, modals, chips, badges, avatars, icons, progress bars, etc.).
- STATES: If the image shows hover states, selected tabs, active menu items, disabled buttons, or empty states, reproduce them.

Modern UI quality requirements:
- For table/list screens: include a table toolbar (search/filter/actions), column headers, row actions, and pagination area.
- For form screens: use a 2-column grid layout, labels + help/validation placeholders, primary/secondary button group.
- No JS behavior; structure only. Prefer accessible attributes (aria-*, role).

Prefer these classes for structure (supplement with inline styles or scoped CSS for colors):
- wf-appbar, wf-title, wf-subtitle, wf-card, wf-card__header, wf-card__title, wf-card__body,
  wf-actions, wf-btn, wf-btn--primary, wf-input, wf-label, wf-grid, wf-col-6, wf-col-12,
  wf-table, wf-table__toolbar, wf-pagination, wf-chip, wf-badge, wf-state, wf-state--error, wf-empty
"""

# Optional vision model override (e.g. gpt-4o, claude-3-5-sonnet) for image understanding
LLM_VISION_MODEL = env_str("LLM_VISION_MODEL", default=None)

ALLOWED_IMAGE_CONTENT_TYPES = {"image/png", "image/jpeg", "image/jpg", "image/webp"}
# Keep under 4MB to avoid vision API context/token limits (image is sent as base64 to LLM).
MAX_IMAGE_SIZE_BYTES = 4 * 1024 * 1024  # 4 MB


def _get_ui_node(ui_id: str) -> dict[str, Any] | None:
    with get_session() as session:
        result = session.run(
            """
            MATCH (ui:UI {id: $id})
            RETURN ui.id as id, ui.name as name, ui.description as description,
                   ui.attachedToName as attachedToName, ui.attachedToId as attachedToId,
                   ui.attachedToType as attachedToType, ui.template as template
            """,
            id=ui_id,
        )
        rec = result.single()
        if not rec:
            return None
        return {
            "id": rec.get("id"),
            "name": rec.get("name") or "UI",
            "description": rec.get("description") or "",
            "attachedToName": rec.get("attachedToName"),
            "attachedToId": rec.get("attachedToId"),
            "attachedToType": rec.get("attachedToType"),
            "template": rec.get("template"),
        }


def _get_domain_context_for_ui(attached_to_id: str | None, attached_to_type: str | None) -> str:
    """Load aggregate (for Command) or read model info (for ReadModel) to suggest domain-appropriate labels."""
    if not attached_to_id or not attached_to_type:
        return ""
    with get_session() as session:
        if attached_to_type == "Command":
            result = session.run(
                """
                MATCH (cmd:Command {id: $id})<-[:HAS_COMMAND]-(agg:Aggregate)
                RETURN agg.name as aggName, agg.rootEntity as rootEntity
                """,
                id=attached_to_id,
            )
            rec = result.single()
            if not rec or not rec.get("aggName"):
                return ""
            agg_name = rec.get("aggName") or ""
            root = (rec.get("rootEntity") or "").strip()
            parts = [f"Aggregate: {agg_name}"]
            if root:
                parts.append(f" (root entity: {root})")
            parts.append(". Use labels/placeholders that fit this domain (e.g. field names that match the aggregate), not generic 'Label' or 'Input'.")
            return "".join(parts)
        if attached_to_type == "ReadModel":
            result = session.run(
                """
                MATCH (rm:ReadModel {id: $id})
                OPTIONAL MATCH (rm)-[:HAS_PROPERTY]->(p:Property)
                WITH rm, collect(p.name) as propNames
                RETURN rm.name as rmName, rm.description as rmDesc,
                       [n IN propNames WHERE n IS NOT NULL | n] as fields
                """,
                id=attached_to_id,
            )
            rec = result.single()
            if not rec:
                return ""
            rm_name = rec.get("rmName") or ""
            desc = (rec.get("rmDesc") or "").strip()
            fields = rec.get("fields") or []
            parts = [f"ReadModel: {rm_name}"]
            if desc:
                parts.append(f". Description: {desc[:200]}")
            if fields:
                parts.append(f". Example fields/columns: {', '.join(fields[:15])}")
            parts.append(". Use labels/placeholders that fit this read model (e.g. column names that match the data), not generic 'Label' or 'Column 1'.")
            return "".join(parts)
    return ""


async def _invoke_vision_llm(image_base64: str, mime_type: str, prompt: str) -> str:
    """
    Call vision-capable LLM with image + text. Returns raw HTML string.

    Image is passed as a data URL (base64) only to the LLM client; the API itself
    receives the upload as binary (multipart/form-data). Base64 increases size
    by ~4/3; we limit upload size (MAX_IMAGE_SIZE_BYTES) to avoid context/token limits.
    """
    data_url = f"data:{mime_type};base64,{image_base64}"
    content = [
        {"type": "text", "text": prompt},
        {"type": "image_url", "image_url": {"url": data_url}},
    ]
    model_kwargs = {}
    if LLM_VISION_MODEL:
        model_kwargs["model"] = LLM_VISION_MODEL
    llm = get_llm(**model_kwargs)
    resp = await asyncio.wait_for(
        asyncio.to_thread(
            llm.invoke,
            [
                SystemMessage(content=_UI_WIREFRAME_SYSTEM_PROMPT),
                HumanMessage(content=content),
            ],
        ),
        timeout=120.0,
    )
    if isinstance(resp, str):
        return resp
    text = getattr(resp, "content", None)
    return text if isinstance(text, str) else str(resp)


@router.post("/ui-wireframe-from-image")
async def ui_wireframe_from_image(
    ui_id: str = Form(..., description="UI node id to update"),
    file: UploadFile = File(..., description="Screenshot image (PNG/JPEG/WebP)"),
    display_language: str = Form("ko", description="Display language for wireframe text (ko or en)"),
) -> dict[str, Any]:
    """
    Regenerate wireframe template for a UI node from an uploaded screenshot.
    Uses a vision-capable LLM to interpret the image and produce wireframe HTML.

    Image flow: client sends binary via multipart/form-data; server converts to
    base64 only when calling the vision LLM (OpenAI/Anthropic/Google expect
    data URL). Upload size is capped to avoid vision context/token limits.
    """
    if not file.content_type or file.content_type.lower() not in ALLOWED_IMAGE_CONTENT_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid file type. Allowed: {', '.join(ALLOWED_IMAGE_CONTENT_TYPES)}",
        )

    body = await file.read()
    if len(body) > MAX_IMAGE_SIZE_BYTES:
        raise HTTPException(
            status_code=400,
            detail=f"Image too large (max {MAX_IMAGE_SIZE_BYTES // (1024*1024)} MB)",
        )

    ui = _get_ui_node(ui_id)
    if not ui:
        raise HTTPException(status_code=404, detail=f"UI node not found: {ui_id}")

    ui_name = ui.get("name") or "UI"
    attached = ui.get("attachedToName") or ""
    domain_context = _get_domain_context_for_ui(ui.get("attachedToId"), ui.get("attachedToType"))
    display_lang = (display_language or "ko").strip().lower()
    if display_lang not in ("ko", "en"):
        display_lang = "ko"
    lang_instruction = (
        "\n\nIMPORTANT: All visible text in the wireframe (labels, placeholders, button text, column headers, titles, tooltips, help text, validation messages) MUST be written in Korean (한글). Do NOT use English for any user-facing text."
        if display_lang == "ko"
        else "\n\nAll visible text in the wireframe (labels, placeholders, button text, column headers, titles) should be in English."
    )
    prompt = f"""The attached image is a screenshot of a UI screen. Reproduce it as faithfully as possible as a wireframe HTML fragment.

UI Name: {ui_name}
Attached to: {attached or "—"}
{domain_context if domain_context else ""}

What to do:
- FAITHFULLY REPRODUCE the screenshot: match the layout, structure, color scheme, spacing, and visual hierarchy as closely as possible.
- Extract colors from the image (backgrounds, buttons, headers, borders, text) and apply them via scoped <style> or inline styles.
- Preserve the overall composition: sidebar + main area, top navigation bar, card grid, split pane, etc.
- Match the number and arrangement of sections, headers, form fields, tables, lists, buttons, and navigation areas.
- Do NOT copy exact text, brand names, logos, or product names from the image.
- For labels and placeholders: use names that fit the domain context above (e.g. field/column names that match the aggregate or read model). If no domain context is given, use neutral placeholders.
- Output the wireframe HTML fragment using the required .wf-root and wf-* classes, plus a scoped <style> block for colors. No markdown, no explanation.{lang_instruction}"""

    try:
        image_b64 = base64.b64encode(body).decode("utf-8")
        mime = file.content_type or "image/png"
        raw_html = await _invoke_vision_llm(image_b64, mime, prompt)
    except asyncio.TimeoutError:
        SmartLogger.log(
            "ERROR",
            "UI wireframe from image: LLM timeout",
            category="api.chat.ui_wireframe_from_image.timeout",
            params={"ui_id": ui_id},
        )
        raise HTTPException(status_code=504, detail="Wireframe generation timed out")
    except Exception as e:
        SmartLogger.log(
            "ERROR",
            "UI wireframe from image: LLM error",
            category="api.chat.ui_wireframe_from_image.error",
            params={"ui_id": ui_id, "error": str(e)},
        )
        raise HTTPException(status_code=500, detail=str(e))

    final_template, _ = normalize_ui_template(
        raw_html,
        ui_name=ui_name,
        theme_hint=ui_name,
    )

    change = {
        "changeId": str(uuid.uuid4()),
        "action": "update",
        "targetId": ui_id,
        "targetType": "UI",
        "updates": {"template": final_template},
    }
    applied, errors = apply_confirmed_changes_atomic([change])
    if errors:
        SmartLogger.log(
            "WARNING",
            "UI wireframe from image: apply failed",
            category="api.chat.ui_wireframe_from_image.apply_failed",
            params={"ui_id": ui_id, "errors": errors},
        )
        raise HTTPException(status_code=500, detail="; ".join(errors))

    return {"template": final_template, "success": True}
