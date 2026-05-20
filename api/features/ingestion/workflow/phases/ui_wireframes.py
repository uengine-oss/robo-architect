from __future__ import annotations

import asyncio
import time
from functools import partial
from typing import AsyncGenerator

from langchain_core.messages import HumanMessage, SystemMessage

from api.features.ingestion.figma_to_user_stories import _fuzzy_match_screen_name
from api.features.ingestion.ingestion_contracts import IngestionPhase, ProgressEvent
from api.features.ingestion.workflow.ingestion_workflow_context import IngestionWorkflowContext
from api.platform.env import get_llm_provider_model
from api.platform.keys import ui_key as build_ui_key
from api.platform.observability.smart_logger import SmartLogger
from api.platform.ui_wireframe_template import normalize_ui_template
from api.platform import open_pencil_client


def _resolve_figma_screen_ref(
    ctx: IngestionWorkflowContext,
    source_screen: str,
    target_type: str,
    target_id: str,
) -> str:
    """
    Resolve a Figma screen reference for UI prompt injection.
    Uses fuzzy matching as fallback if exact match fails. Logs warnings on failures.
    Returns the prompt injection string, or empty string if not found.
    """
    if not source_screen or not hasattr(ctx, "figma_screens") or not ctx.figma_screens:
        return ""

    screen_data = ctx.figma_screens.get(source_screen, "")
    resolved_name = source_screen

    if not screen_data:
        # Try fuzzy matching
        matched = _fuzzy_match_screen_name(source_screen, set(ctx.figma_screens.keys()))
        if matched:
            screen_data = ctx.figma_screens.get(matched, "")
            resolved_name = matched
            SmartLogger.log(
                "INFO",
                f"Figma screen fuzzy matched for UI: '{source_screen}' → '{matched}'",
                category="ingestion.ui_wireframe.figma.fuzzy_match",
                params={"session_id": ctx.session.id, "original": source_screen, "matched": matched, "target_type": target_type, "target_id": target_id},
            )
        else:
            SmartLogger.log(
                "WARN",
                f"Figma screen '{source_screen}' not found in figma_screens (no fuzzy match). "
                f"UI for {target_type} '{target_id}' will be generated without Figma reference.",
                category="ingestion.ui_wireframe.figma.screen_not_found",
                params={
                    "session_id": ctx.session.id,
                    "source_screen": source_screen,
                    "target_type": target_type,
                    "target_id": target_id,
                    "available_screens": list(ctx.figma_screens.keys())[:20],
                },
            )
            return ""

    if screen_data:
        return (
            f"\n\n★ Figma 원본 화면 참조 ('{resolved_name}'):\n"
            f"이 {target_type}의 UI는 아래 Figma 화면 구조를 충실히 반영하여 생성하세요.\n"
            f"{screen_data}"
        )
    return ""


_UI_COMPONENT_SYSTEM_PROMPT_TEMPLATE = """You compose a mobile UI wireframe by selecting and arranging components from a design library.

Output rules (STRICT):
- Output ONLY valid JSON. No markdown fences, no explanatory text.
- The JSON must have a "components" array at the top level.
- Each element is an object with:
  - "component": the exact component name from the library (case-insensitive match is supported)
  - "overrides": (optional) object with text overrides. Keys are child node names (e.g. "title", "subtitle"), values are the replacement text strings.

Example output:
{{
  "components": [
    {{"component": "top-bar", "overrides": {{"title": "주문 관리"}}}},
    {{"component": "input-search-gray-2"}},
    {{"component": "com-card-product", "overrides": {{"title": "상품명"}}}},
    {{"component": "btn-main-task", "overrides": {{"title": "주문하기"}}}}
  ]
}}

Component selection guidelines:
- Pick components that best match the screen's purpose (form, list, detail, etc.)
- Use top-bar/navigation components at the top
- Use btn-main-task or similar for primary actions at the bottom
- Use card/list components for content areas
- Use input components for form fields
- Arrange components in a logical top-to-bottom flow (mobile layout)
- Override text to match the domain context (Korean preferred for Korean apps)

{component_catalog}
"""

_UI_WIREFRAME_SYSTEM_PROMPT = """You generate a modern UI wireframe HTML fragment for a single screen (Ant Design-like or Material-like).
\n\nOutput rules (STRICT):
- Output ONLY raw HTML fragment. Do NOT use markdown or code fences.
- Do NOT output <!doctype>, <html>, <head>, <body>.
- Do NOT include <script> tags.
- Do NOT include inline event handlers like onclick=, onload=, etc.
- Do NOT use javascript: URLs.
- You MAY include a <style> block, but:
  - Every selector MUST be scoped under `.wf-root`
  - MUST NOT use @import or url(...)\n\nRoot container (MUST):\n- The fragment MUST start with a root container like:\n  <div class=\"wf-root wf-theme-ant\" data-wf-root=\"1\"> ... </div>\n  or\n  <div class=\"wf-root wf-theme-material\" data-wf-root=\"1\"> ... </div>\n\nModern UI quality requirements:\n- Use an App Bar / Toolbar at the top (title + primary actions).\n- Use Card-based sections.\n- For table/list screens: include a table toolbar (search/filter/actions), column headers, row actions, and pagination area.\n- For form screens: use a 2-column grid layout, labels + help/validation placeholders, primary/secondary button group.\n- Optionally include tabs/segments, chips/badges, and empty/loading/error state placeholders.\n- No JS behavior; structure only. Prefer accessible attributes (aria-*, role).\n\nPrefer these classes to match the preview styling:\n- wf-appbar, wf-title, wf-subtitle, wf-card, wf-card__header, wf-card__title, wf-card__body,\n  wf-actions, wf-btn, wf-btn--primary, wf-input, wf-label, wf-grid, wf-col-6, wf-col-12,\n  wf-table, wf-table__toolbar, wf-pagination, wf-chip, wf-badge, wf-state, wf-state--error, wf-empty\n"""



def _fetch_command_events_best_effort(ctx: IngestionWorkflowContext, command_id: str) -> list[str]:
    """
    Best-effort enrichment: find events emitted by a command (for better wireframe prompts).
    """
    if not command_id:
        return []
    try:
        with ctx.client.session() as session:
            result = session.run(
                """
                MATCH (cmd:Command {id: $id})-[:EMITS]->(evt:Event)
                RETURN evt.name as name
                ORDER BY name
                """,
                id=command_id,
            )
            names = [r.get("name") for r in result if r and r.get("name")]
            return [str(n) for n in names if str(n).strip()]
    except Exception:
        return []


def _existing_ui_template_best_effort(ctx: IngestionWorkflowContext, ui_id: str) -> str | None:
    """
    If a UI already exists with a non-empty template, reuse it and avoid an extra LLM call.
    """
    if not ui_id:
        return None
    try:
        with ctx.client.session() as session:
            rec = session.run("MATCH (ui:UI {key: $key}) RETURN ui.template as template", key=ui_id).single()
            t = rec.get("template") if rec else None
            if isinstance(t, str) and t.strip():
                return t
    except Exception:
        return None
    return None


async def _llm_invoke_to_html(ctx: IngestionWorkflowContext, prompt: str) -> str:
    """
    Invoke the configured LLM and extract plain HTML text (async with timeout).
    """
    try:
        resp = await asyncio.wait_for(
            asyncio.to_thread(
                ctx.llm.invoke,
                [SystemMessage(content=_UI_WIREFRAME_SYSTEM_PROMPT), HumanMessage(content=prompt)]
            ),
            timeout=300.0  # 5분 타임아웃
        )
        if isinstance(resp, str):
            return resp
        content = getattr(resp, "content", None)
        if isinstance(content, str):
            return content
        return str(resp)
    except asyncio.TimeoutError:
        SmartLogger.log(
            "ERROR",
            "UI wireframe LLM invoke timeout",
            category="ingestion.llm.ui_wireframe.timeout",
            params={"session_id": ctx.session.id, "prompt_length": len(prompt)},
        )
        raise


# ------------------------------------------------------------------ #
#  Component-based wireframe generation (open-pencil)                  #
# ------------------------------------------------------------------ #

_component_catalog_prompt: str | None = None


def _get_component_catalog_prompt() -> str:
    """Lazy-load component catalog prompt from the wireframe service."""
    global _component_catalog_prompt
    if _component_catalog_prompt is not None:
        return _component_catalog_prompt
    _component_catalog_prompt = open_pencil_client.get_component_catalog_for_prompt()
    return _component_catalog_prompt


def _is_open_pencil_available() -> bool:
    """Check once if the open-pencil wireframe service is available."""
    return open_pencil_client.is_available()


# Spec 024: bound-figma-file component catalog (refreshed every call so a
# mid-run scan is picked up without restart).
def _get_figma_binding_catalog_prompt() -> str:
    try:
        from api.features.figma_binding.component_library import (  # noqa: PLC0415
            get_catalog_for_prompt,
        )
        return get_catalog_for_prompt() or ""
    except Exception as e:  # noqa: BLE001
        SmartLogger.log(
            "WARN",
            f"ingestion.ui_wireframe.figma_components.catalog_unavailable err={e}",
            category="ingestion.ui_wireframe.figma_components.catalog_unavailable",
            params={"error": str(e)},
        )
        return ""


async def _llm_invoke_to_component_json(
    ctx: IngestionWorkflowContext,
    prompt: str,
    *,
    catalog_override: str | None = None,
) -> str:
    """
    Invoke the LLM with the component-based system prompt.
    Returns the raw JSON text from the LLM.

    When ``catalog_override`` is provided (spec 024 figma-with-components
    mode), it is used in place of the local open-pencil catalog.
    """
    catalog = catalog_override if catalog_override is not None else _get_component_catalog_prompt()
    if not catalog:
        raise RuntimeError("Component catalog not available")

    system_prompt = _UI_COMPONENT_SYSTEM_PROMPT_TEMPLATE.format(component_catalog=catalog)

    resp = await asyncio.wait_for(
        asyncio.to_thread(
            ctx.llm.invoke,
            [SystemMessage(content=system_prompt), HumanMessage(content=prompt)],
        ),
        timeout=300.0,
    )
    if isinstance(resp, str):
        return resp
    content = getattr(resp, "content", None)
    if isinstance(content, str):
        return content
    return str(resp)


async def _generate_scene_graph(
    ctx: IngestionWorkflowContext,
    prompt: str,
    ui_name: str,
) -> dict | None:
    """
    Try to generate a wireframe as a SerializedSceneGraph via the component
    pipeline.  Returns the scene graph dict, or None if unavailable / failed.
    """
    if not _is_open_pencil_available():
        return None

    try:
        raw_json = await _llm_invoke_to_component_json(ctx, prompt)
        scene_graph = await asyncio.to_thread(
            open_pencil_client.parse_and_render_llm_output,
            raw_json,
            name=ui_name,
        )
        if scene_graph:
            SmartLogger.log(
                "INFO",
                f"Component-based wireframe generated: {ui_name}",
                category="ingestion.ui_wireframe.open_pencil.success",
                params={"session_id": ctx.session.id, "ui_name": ui_name},
            )
        return scene_graph
    except Exception as e:
        SmartLogger.log(
            "WARN",
            f"Component-based wireframe failed, falling back to HTML: {e}",
            category="ingestion.ui_wireframe.open_pencil.fallback",
            params={"session_id": ctx.session.id, "ui_name": ui_name, "error": str(e)},
        )
        return None


async def _generate_jsx_scene_graph_for_figma_mode(
    ctx: IngestionWorkflowContext,
    *,
    ui_display_name: str,
    description: str,
    bc_name: str,
) -> dict | None:
    """Figma-mode wireframe generation (no HTML, no figma-component picking).

    Uses the Phase 1 backend JSX agent (`api/features/ai_design/wireframe_agent.run_render_agent`).
    The result is a SerializedSceneGraph the caller embeds into the UI node it
    is about to create.  Returns None on failure — the caller should treat
    this as "no design yet" and leave the UI node without a sceneGraph.

    Retries once on transient failure: the agent gives up after the first
    failed render call (the LLM follows up the tool error with a summary
    instead of retrying), so when the wireframe service times out under load
    we end up with empty UI nodes. A second attempt with a fresh agent loop
    almost always succeeds once the concurrency burst has passed.
    """
    # Local import to avoid widening this phase module's startup graph.
    from api.features.ai_design.wireframe_agent import run_render_agent

    MAX_ATTEMPTS = 3
    last_summary: str | None = None
    for attempt in range(1, MAX_ATTEMPTS + 1):
        if attempt > 1:
            # Brief jitter so retries don't thunder into the wireframe service
            # at the same moment the rest of the batch is also retrying.
            await asyncio.sleep(0.5 * attempt)
        try:
            sg, summary = await run_render_agent(
                name=ui_display_name,
                description=description or "",
                bc_name=bc_name or "",
            )
        except Exception as e:
            SmartLogger.log(
                "WARN",
                f"figma-mode wireframe agent crashed for {ui_display_name} (attempt {attempt}/{MAX_ATTEMPTS}): {e}",
                category="ingestion.ui_wireframe.figma_mode.error",
                params={"session_id": ctx.session.id, "ui_name": ui_display_name, "error": str(e), "attempt": attempt},
            )
            sg, summary = None, None
        last_summary = summary or last_summary
        if sg:
            SmartLogger.log(
                "INFO",
                f"figma-mode wireframe generated: {ui_display_name} ({len(sg.get('nodes') or {})} nodes, attempt {attempt})",
                category="ingestion.ui_wireframe.figma_mode.success",
                params={
                    "session_id": ctx.session.id,
                    "ui_name": ui_display_name,
                    "node_count": len(sg.get("nodes") or {}),
                    "summary": summary,
                    "attempt": attempt,
                },
            )
            return sg
        if attempt < MAX_ATTEMPTS:
            SmartLogger.log(
                "WARN",
                f"figma-mode wireframe empty for {ui_display_name}, retrying (attempt {attempt}/{MAX_ATTEMPTS})",
                category="ingestion.ui_wireframe.figma_mode.retry",
                params={"session_id": ctx.session.id, "ui_name": ui_display_name, "attempt": attempt},
            )
    SmartLogger.log(
        "WARN",
        f"figma-mode wireframe agent returned no sceneGraph for {ui_display_name} after {MAX_ATTEMPTS} attempts",
        category="ingestion.ui_wireframe.figma_mode.empty",
        params={"session_id": ctx.session.id, "ui_name": ui_display_name, "summary": last_summary},
    )
    return None


def _is_figma_ui_mode(ctx: IngestionWorkflowContext) -> bool:
    mode = (getattr(ctx.session, "ui_generation_mode", "html") or "html").lower()
    return mode in ("figma", "figma-with-components")


def _is_figma_with_components_mode(ctx: IngestionWorkflowContext) -> bool:
    """Spec 024 — figma mode that should consult the bound file's component catalog first."""
    mode = (getattr(ctx.session, "ui_generation_mode", "html") or "html").lower()
    return mode == "figma-with-components"


async def _generate_figma_components_scene_graph(
    ctx: IngestionWorkflowContext,
    prompt: str,
    ui_name: str,
    *,
    bc_name: str = "",
) -> dict | None:
    """Spec 024 (revised): generate a sceneGraph that mixes user's Figma
    design-system components AND custom primitive layout, by reusing the
    open-pencil JSX agent.

    Flow:
      1. Build extra_context that lists the bound catalog and explains the
         `$INSTANCE:Name|k=v` marker convention.
      2. Call `run_render_agent` — open-pencil renders the LLM's JSX to a
         proper SerializedSceneGraph (Yoga auto-layout, padding, alignment).
      3. Post-process the sceneGraph: retype `$INSTANCE:Name` FRAME leaves
         to INSTANCE so the Figma plugin instantiates the real components.

    Returns the sceneGraph dict, or None when the catalog is empty / the
    agent failed. The caller should fall back to the generic figma JSX path.
    """
    # Local import to avoid widening this phase module's startup graph.
    from api.features.ai_design.wireframe_agent import run_render_agent  # noqa: PLC0415
    from api.features.figma_binding.component_library import (  # noqa: PLC0415
        build_jsx_agent_extra_context,
        build_name_to_node_index,
        retype_instance_markers,
    )

    catalog = _get_figma_binding_catalog_prompt()
    if not catalog:
        SmartLogger.log(
            "INFO",
            f"ingestion.ui_wireframe.figma_components.empty_catalog ui={ui_name}",
            category="ingestion.ui_wireframe.figma_components.empty_catalog",
            params={"session_id": ctx.session.id, "ui_name": ui_name},
        )
        return None

    extra_ctx = build_jsx_agent_extra_context(catalog)
    try:
        scene_graph, summary = await run_render_agent(
            name=ui_name or "Wireframe",
            description=prompt,
            bc_name=bc_name or "",
            bc_description="",
            extra_context=extra_ctx,
        )
    except Exception as e:
        SmartLogger.log(
            "WARN",
            f"ingestion.ui_wireframe.figma_components.agent_failed ui={ui_name} err={e}",
            category="ingestion.ui_wireframe.figma_components.agent_failed",
            params={"session_id": ctx.session.id, "ui_name": ui_name, "error": str(e)},
        )
        return None

    if not scene_graph:
        SmartLogger.log(
            "WARN",
            f"ingestion.ui_wireframe.figma_components.agent_empty ui={ui_name}",
            category="ingestion.ui_wireframe.figma_components.agent_empty",
            params={"session_id": ctx.session.id, "ui_name": ui_name, "summary": summary},
        )
        return None

    name_index = build_name_to_node_index()
    scene_graph, counts = retype_instance_markers(scene_graph, name_index)
    if counts["unresolved"]:
        SmartLogger.log(
            "WARN",
            f"ingestion.ui_wireframe.figma_components.unresolved_names ui={ui_name} names={counts['unresolved']}",
            category="ingestion.ui_wireframe.figma_components.unresolved_names",
            params={
                "session_id": ctx.session.id,
                "ui_name": ui_name,
                "unresolved": counts["unresolved"],
                "retyped": counts["retyped"],
            },
        )

    SmartLogger.log(
        "INFO",
        f"ingestion.ui_wireframe.figma_components.success ui={ui_name} instances={counts['retyped']} names={counts['instance_names']}",
        category="ingestion.ui_wireframe.figma_components.success",
        params={
            "session_id": ctx.session.id,
            "ui_name": ui_name,
            "instances": counts["retyped"],
            "instance_names": counts["instance_names"],
            "summary": summary,
        },
    )

    return scene_graph


# ─── 020 bridge: figma-mode generator for an existing :UI ──────────────────
#
# Module-public bridge for spec 020 figma_binding.full_sync. Constitution V
# forbids cross-feature internal imports — figma_binding calls this one named
# function, never reaching into the underscore-prefixed helpers below. Mirrors
# 016 v1.2's reverse bridge (bulk_sync.sync_batch imported from this module).


class _MinimalCtx:
    """Lightweight stand-in for IngestionWorkflowContext with just the fields
    `_generate_jsx_scene_graph_for_figma_mode` reads.
    """

    class _Session:
        def __init__(self, sid: str, mode: str) -> None:
            self.id = sid
            self.ui_generation_mode = mode

    def __init__(self, session_id: str) -> None:
        self.session = _MinimalCtx._Session(session_id, "figma")


async def generate_jsx_for_existing_ui(
    *, ui_id: str, actor: str, correlation_id: str | None = None
) -> dict | None:
    """Generate a figma-mode sceneGraph for a :UI that already exists in Neo4j.

    Used by spec 020 retroactive full-sync (see specs/020-figma-sync-recovery
    research D4). Reads the UI's display name + a description hint from the
    graph, calls the same figma-mode agent the bulk path uses, and returns
    the resulting sceneGraph dict (or None on failure).

    The caller is responsible for persisting the sceneGraph onto the :UI node
    if the call returns a non-None value.
    """
    from api.platform.neo4j import get_session

    with get_session() as session:
        rec = session.run(
            """
            MATCH (u:UI {id: $uid})
            OPTIONAL MATCH (u)<-[:HAS_UI]-(bc:BoundedContext)
            RETURN coalesce(u.displayName, u.name, '') AS displayName,
                   coalesce(u.description, '') AS description,
                   coalesce(bc.displayName, bc.name, '') AS bcName
            """,
            uid=ui_id,
        ).single()

    if not rec:
        SmartLogger.log(
            "WARN",
            f"figma_binding.bridge: UI not found id={ui_id}",
            category="ingestion.ui_wireframe.figma_mode.bridge_miss",
            params={"uiId": ui_id, "actor": actor, "correlationId": correlation_id},
        )
        return None

    display_name = rec["displayName"] or ui_id
    description = rec["description"] or ""
    bc_name = rec["bcName"] or ""

    # Fabricate a session id so the existing logger params have something
    # meaningful — actor is the real provenance.
    fake_session_id = correlation_id or f"figma-binding-bridge:{actor}:{ui_id}"
    ctx = _MinimalCtx(fake_session_id)

    return await _generate_jsx_scene_graph_for_figma_mode(
        ctx,  # type: ignore[arg-type]
        ui_display_name=display_name,
        description=description,
        bc_name=bc_name,
    )


async def _create_command_ui(
    ctx: IngestionWorkflowContext,
    bc,
    cmd,
    agg,
    chosen_us_id: str,
    chosen_ui_desc: str,
    user_story_ui: dict[str, str],
    policy_invoked_command_ids: set[str],
    policy_invoked_command_names: set[str],
) -> tuple[dict | None, ProgressEvent | None]:
    """Create a single Command UI asynchronously. Returns (ui_dict, progress_event) or (None, None) on skip/error."""
    # Handle both dict and object formats
    cmd_id = cmd.get("id") if isinstance(cmd, dict) else getattr(cmd, "id", None)
    cmd_name = cmd.get("name") if isinstance(cmd, dict) else getattr(cmd, "name", "")
    cmd_display_name = cmd.get("displayName") if isinstance(cmd, dict) else getattr(cmd, "displayName", None)
    bc_id = bc.get("id") if isinstance(bc, dict) else getattr(bc, "id", None)
    bc_name = bc.get("name") if isinstance(bc, dict) else getattr(bc, "name", "")
    agg_name = agg.get("name") if isinstance(agg, dict) else getattr(agg, "name", "") if agg else ""
    agg_root = (agg.get("rootEntity") if isinstance(agg, dict) else getattr(agg, "rootEntity", None)) or ""
    
    if cmd_id in policy_invoked_command_ids or cmd_name in policy_invoked_command_names:
        return None, None

    ui_id = build_ui_key("Command", cmd_id)
    ui_name = cmd_name
    ui_display_name = cmd_display_name or cmd_name

    try:
        existing_template = await asyncio.to_thread(_existing_ui_template_best_effort, ctx, ui_id)

        us_obj = next((u for u in (ctx.user_stories or []) if getattr(u, "id", None) == chosen_us_id), None)
        user_story_text = ""
        figma_screen_ref = ""
        if us_obj is not None:
            role = getattr(us_obj, "role", "") or ""
            action = getattr(us_obj, "action", "") or ""
            benefit = getattr(us_obj, "benefit", "") or ""
            user_story_text = f"[{chosen_us_id}] As a {role}, I want to {action}, so that {benefit}".strip()

            # Figma screen reference: look up original screen structure with fuzzy fallback
            source_screen = getattr(us_obj, "source_screen_name", None) or ""
            if source_screen:
                figma_screen_ref = _resolve_figma_screen_ref(ctx, source_screen, "Command", cmd_id)

        events = await asyncio.to_thread(_fetch_command_events_best_effort, ctx, cmd_id)
        events_text = "\n".join([f"- {e}" for e in events]) if events else "No events found"

        theme_hint = f"{ui_name}\n{chosen_ui_desc}"
        scene_graph_json: str | None = None

        if existing_template is not None:
            final_template, norm_report = normalize_ui_template(
                str(existing_template),
                ui_name=ui_name,
                theme_hint=theme_hint,
            )
        else:
            aggregate_context = f"Aggregate: {agg_name}" + (f" (root entity: {agg_root})" if agg_root else "") if agg_name else ""
            display_lang = getattr(ctx, "display_language", "ko") or "ko"
            lang_instruction = (
                "\n\nIMPORTANT: All visible text (overrides) MUST be written in Korean (한글)."
                if display_lang == "ko"
                else "\n\nIMPORTANT: All visible text (overrides) MUST be written in English."
            )
            base_prompt = f"""UI Name: {ui_display_name}\nBounded Context: {bc_name} ({bc_id})\nAttached To: Command {cmd_name} ({cmd_id})\n{aggregate_context}\nUser Story: {user_story_text or f'[{chosen_us_id}]'}\nui_description:\n{chosen_ui_desc}\n\nRelated Events emitted by the Command:\n{events_text}{figma_screen_ref}{lang_instruction}"""

            if _is_figma_with_components_mode(ctx):
                # --- 024 Figma+Components mode: bound catalog first, fall back to JSX ---
                sg = await _generate_figma_components_scene_graph(
                    ctx, base_prompt, ui_display_name, bc_name=bc_name
                )
                if sg is None:
                    SmartLogger.log(
                        "INFO",
                        f"ingestion.ui_wireframe.figma_components.fallback ui={ui_display_name}",
                        category="ingestion.ui_wireframe.figma_components.fallback",
                        params={"session_id": ctx.session.id, "ui_name": ui_display_name},
                    )
                    sg = await _generate_jsx_scene_graph_for_figma_mode(
                        ctx,
                        ui_display_name=ui_display_name,
                        description=chosen_ui_desc,
                        bc_name=bc_name,
                    )
                if sg is not None:
                    import json as _json
                    scene_graph_json = _json.dumps(sg, ensure_ascii=False)
                final_template = ""
                norm_report = {"mode": "figma-with-components", "html_skipped": True}
            elif _is_figma_ui_mode(ctx):
                # --- Figma mode: pure JSX agent, NO HTML, NO component picking ---
                sg = await _generate_jsx_scene_graph_for_figma_mode(
                    ctx,
                    ui_display_name=ui_display_name,
                    description=chosen_ui_desc,
                    bc_name=bc_name,
                )
                if sg is not None:
                    import json as _json
                    scene_graph_json = _json.dumps(sg, ensure_ascii=False)
                # Skip HTML generation entirely in figma mode.
                final_template = ""
                norm_report = {"mode": "figma", "html_skipped": True}
            else:
                # --- Try component-based (open-pencil) first ---
                sg = await _generate_scene_graph(ctx, base_prompt, ui_display_name)
                if sg is not None:
                    import json as _json
                    scene_graph_json = _json.dumps(sg, ensure_ascii=False)
                    # Still generate a minimal HTML template for backward compat
                    final_template, norm_report = normalize_ui_template(
                        "",
                        ui_name=ui_name,
                        theme_hint=theme_hint,
                    )
                else:
                    # --- Fallback to HTML generation ---
                    html_prompt = f"Generate a wireframe HTML template.\n\n{base_prompt}\n\nUse labels and placeholders that fit this domain, not generic \"Label\" or \"Input\". Output ONLY the HTML fragment."
                    raw_html = await _llm_invoke_to_html(ctx, html_prompt)
                    final_template, norm_report = normalize_ui_template(
                        str(raw_html),
                        ui_name=ui_name,
                        theme_hint=theme_hint,
                    )

        ui = await asyncio.wait_for(
            asyncio.to_thread(
                ctx.client.create_ui,
                key=ui_id,
                name=ui_name,
                bc_id=bc_id,
                description=chosen_ui_desc,
                template=final_template,
                attached_to_id=cmd_id,
                attached_to_type="Command",
                attached_to_name=cmd_name,
                user_story_id=chosen_us_id,
                display_name=ui_display_name,
                scene_graph=scene_graph_json,
            ),
            timeout=10.0
        )

        # Command의 actor와 Event sequence를 가져와 UI 배치에 사용
        ui_actor = None
        ui_sequence = None
        try:
            with ctx.client.session() as _s:
                _r = _s.run(
                    "MATCH (cmd:Command {id: $cid}) OPTIONAL MATCH (cmd)-[:EMITS]->(evt:Event) RETURN cmd.actor AS actor, evt.sequence AS seq LIMIT 1",
                    cid=cmd_id,
                ).single()
                if _r:
                    ui_actor = _r["actor"]
                    if _r["seq"] is not None:
                        try: ui_sequence = int(_r["seq"])
                        except (TypeError, ValueError): pass
        except Exception:
            pass

        progress_event = ProgressEvent(
            phase=IngestionPhase.GENERATING_UI,
            message=f"UI 생성: {ui_name}",
            progress=88,
            data={
                "type": "UI",
                "object": {
                    "id": ui.get("id"),
                    "name": ui_name,
                    "displayName": ui.get("displayName") or ui_display_name,
                    "type": "UI",
                    "parentId": bc_id,
                    "template": final_template,
                    "attachedToId": cmd_id,
                    "attachedToType": "Command",
                    "attachedToName": cmd_name,
                    "userStoryId": chosen_us_id,
                    "description": chosen_ui_desc,
                    "sceneGraph": scene_graph_json,
                    "actor": ui_actor,
                    "sequence": ui_sequence,
                    "commandId": cmd_id,
                },
            },
        )
        return ui, progress_event
    except Exception as e:
        SmartLogger.log(
            "ERROR",
            "UI creation failed",
            category="ingestion.neo4j.ui",
            params={"session_id": ctx.session.id, "ui_id": ui_id, "command_id": cmd_id, "error": str(e)},
        )
        return None, None


async def _create_readmodel_ui(
    ctx: IngestionWorkflowContext,
    bc,
    rm: dict,
    chosen_us_id: str,
    chosen_ui_desc: str,
    user_story_ui: dict[str, str],
) -> tuple[dict | None, ProgressEvent | None]:
    """Create a single ReadModel UI asynchronously. Returns (ui_dict, progress_event) or (None, None) on skip/error."""
    # Handle both dict and object formats
    bc_id = bc.get("id") if isinstance(bc, dict) else getattr(bc, "id", None)
    bc_name = bc.get("name") if isinstance(bc, dict) else getattr(bc, "name", "")
    
    rm_id = rm.get("id")
    ui_id = build_ui_key("ReadModel", rm_id)
    ui_name = rm.get('name', rm_id)
    ui_display_name = rm.get("displayName") or ui_name

    try:
        existing_template = await asyncio.to_thread(_existing_ui_template_best_effort, ctx, ui_id)

        us_obj = next((u for u in (ctx.user_stories or []) if getattr(u, "id", None) == chosen_us_id), None)
        user_story_text = ""
        figma_screen_ref = ""
        if us_obj is not None:
            role = getattr(us_obj, "role", "") or ""
            action = getattr(us_obj, "action", "") or ""
            benefit = getattr(us_obj, "benefit", "") or ""
            user_story_text = f"[{chosen_us_id}] As a {role}, I want to {action}, so that {benefit}".strip()

            # Figma screen reference with fuzzy fallback
            source_screen = getattr(us_obj, "source_screen_name", None) or ""
            if source_screen:
                figma_screen_ref = _resolve_figma_screen_ref(ctx, source_screen, "ReadModel", rm_id)

        theme_hint = f"{ui_name}\n{chosen_ui_desc}"
        scene_graph_json: str | None = None

        if existing_template is not None:
            final_template, norm_report = normalize_ui_template(
                str(existing_template),
                ui_name=ui_name,
                theme_hint=theme_hint,
            )
        else:
            display_lang = getattr(ctx, "display_language", "ko") or "ko"
            lang_instruction = (
                "\n\nIMPORTANT: All visible text (overrides) MUST be written in Korean (한글)."
                if display_lang == "ko"
                else "\n\nIMPORTANT: All visible text (overrides) MUST be written in English."
            )
            base_prompt = f"""UI Name: {ui_display_name}\nBounded Context: {bc_name} ({bc_id})\nAttached To: ReadModel {rm.get('name', rm_id)} ({rm_id})\nUser Story: {user_story_text or f'[{chosen_us_id}]'}\nui_description:\n{chosen_ui_desc}{figma_screen_ref}{lang_instruction}"""

            if _is_figma_with_components_mode(ctx):
                # --- 024 Figma+Components mode: bound catalog first, fall back to JSX ---
                sg = await _generate_figma_components_scene_graph(
                    ctx, base_prompt, ui_display_name, bc_name=bc_name
                )
                if sg is None:
                    SmartLogger.log(
                        "INFO",
                        f"ingestion.ui_wireframe.figma_components.fallback ui={ui_display_name}",
                        category="ingestion.ui_wireframe.figma_components.fallback",
                        params={"session_id": ctx.session.id, "ui_name": ui_display_name},
                    )
                    sg = await _generate_jsx_scene_graph_for_figma_mode(
                        ctx,
                        ui_display_name=ui_display_name,
                        description=chosen_ui_desc,
                        bc_name=bc_name,
                    )
                if sg is not None:
                    import json as _json
                    scene_graph_json = _json.dumps(sg, ensure_ascii=False)
                final_template = ""
                norm_report = {"mode": "figma-with-components", "html_skipped": True}
            elif _is_figma_ui_mode(ctx):
                # --- Figma mode: pure JSX agent, NO HTML, NO component picking ---
                sg = await _generate_jsx_scene_graph_for_figma_mode(
                    ctx,
                    ui_display_name=ui_display_name,
                    description=chosen_ui_desc,
                    bc_name=bc_name,
                )
                if sg is not None:
                    import json as _json
                    scene_graph_json = _json.dumps(sg, ensure_ascii=False)
                final_template = ""
                norm_report = {"mode": "figma", "html_skipped": True}
            else:
                # --- Try component-based (open-pencil) first ---
                sg = await _generate_scene_graph(ctx, base_prompt, ui_display_name)
                if sg is not None:
                    import json as _json
                    scene_graph_json = _json.dumps(sg, ensure_ascii=False)
                    final_template, norm_report = normalize_ui_template(
                        "",
                        ui_name=ui_name,
                        theme_hint=theme_hint,
                    )
                else:
                    # --- Fallback to HTML generation ---
                    html_prompt = f"Generate a wireframe HTML template.\n\n{base_prompt}\n\nUse labels and placeholders that fit this read model, not generic \"Label\" or \"Column\". Output ONLY the HTML fragment."
                    raw_html = await _llm_invoke_to_html(ctx, html_prompt)
                    final_template, norm_report = normalize_ui_template(
                        str(raw_html),
                        ui_name=ui_name,
                        theme_hint=theme_hint,
                    )

        ui = await asyncio.wait_for(
            asyncio.to_thread(
                ctx.client.create_ui,
                key=ui_id,
                name=ui_name,
                bc_id=bc_id,
                description=chosen_ui_desc,
                template=final_template,
                attached_to_id=rm_id,
                attached_to_type="ReadModel",
                attached_to_name=rm.get("name"),
                user_story_id=chosen_us_id,
                display_name=ui_display_name,
                scene_graph=scene_graph_json,
            ),
            timeout=10.0
        )

        # ReadModel의 actor와 trigger event sequence를 가져와 UI 배치에 사용
        rm_ui_actor = rm.get("actor") if isinstance(rm, dict) else getattr(rm, "actor", None)
        rm_ui_sequence = None
        try:
            with ctx.client.session() as _s:
                _r = _s.run(
                    "MATCH (rm:ReadModel {id: $rid})-[:HAS_CQRS]->(:CQRSConfig)-[:HAS_OPERATION]->(:CQRSOperation)-[:TRIGGERED_BY]->(evt:Event) RETURN evt.sequence AS seq LIMIT 1",
                    rid=rm_id,
                ).single()
                if _r and _r["seq"] is not None:
                    try: rm_ui_sequence = int(_r["seq"])
                    except (TypeError, ValueError): pass
        except Exception:
            pass

        progress_event = ProgressEvent(
            phase=IngestionPhase.GENERATING_UI,
            message=f"UI 생성: {ui_name}",
            progress=88,
            data={
                "type": "UI",
                "object": {
                    "id": ui.get("id"),
                    "name": ui_name,
                    "displayName": ui.get("displayName") or ui_display_name,
                    "type": "UI",
                    "parentId": bc_id,
                    "template": final_template,
                    "attachedToId": rm_id,
                    "attachedToType": "ReadModel",
                    "attachedToName": rm.get("name"),
                    "userStoryId": chosen_us_id,
                    "description": chosen_ui_desc,
                    "sceneGraph": scene_graph_json,
                    "actor": rm_ui_actor,
                    "sequence": rm_ui_sequence,
                    "readModelId": rm_id,
                    "isOutput": True,
                },
            },
        )
        return ui, progress_event
    except Exception as e:
        SmartLogger.log(
            "ERROR",
            "UI creation failed",
            category="ingestion.neo4j.ui",
            params={"session_id": ctx.session.id, "ui_id": ui_id, "readmodel_id": rm_id, "error": str(e)},
        )
        return None, None


async def generate_ui_wireframes_phase(ctx: IngestionWorkflowContext) -> AsyncGenerator[ProgressEvent, None]:
    """
    Optional phase: generate UI wireframe stickers for commands and readmodels, based on user story ui_description.

    Design goal: keep this lightweight and deterministic:
    - Create at most 1 UI per Command
    - Create at most 1 UI per ReadModel
    - Use the first related user story that has a ui_description
    - Attach UI to Command/ReadModel (ATTACHED_TO), and to BC (HAS_UI)
    
    Now processes UI creation in parallel batches for improved performance.
    """
    yield ProgressEvent(phase=IngestionPhase.GENERATING_UI, message="UI 와이어프레임 생성 중...", progress=87)

    user_story_ui: dict[str, str] = {}
    for us in ctx.user_stories or []:
        ui_desc = getattr(us, "ui_description", "") or ""
        if ui_desc.strip():
            us_id = us.get("id") if isinstance(us, dict) else getattr(us, "id", None)
            if us_id:
                user_story_ui[us_id] = ui_desc.strip()

    created = 0
    created_by_command: set[str] = set()
    created_by_readmodel: set[str] = set()

    # Build set of command IDs and names that are invoked by policies (no UI needed)
    policy_invoked_command_ids: set[str] = set()
    policy_invoked_command_names: set[str] = set()
    for pol in ctx.policies or []:
        invoke_cmd_id = getattr(pol, "invoke_command_id", None)
        if invoke_cmd_id:
            policy_invoked_command_ids.add(invoke_cmd_id)
        invoke_cmd = getattr(pol, "invoke_command", None)
        if invoke_cmd:
            policy_invoked_command_names.add(invoke_cmd)


    # Collect all UI creation tasks
    command_ui_tasks: list[callable] = []
    readmodel_ui_tasks: list[callable] = []

    for bc in ctx.bounded_contexts or []:
        # Handle both dict and object formats
        bc_id = bc.get("id") if isinstance(bc, dict) else getattr(bc, "id", None)
        
        # -------------------------------------------------------------
        # Command UI - collect tasks
        # -------------------------------------------------------------
        for agg in ctx.aggregates_by_bc.get(bc_id, []) or []:
            agg_id = agg.get("id") if isinstance(agg, dict) else getattr(agg, "id", None)
            for cmd in ctx.commands_by_agg.get(agg_id, []) or []:
                cmd_id = cmd.get("id") if isinstance(cmd, dict) else getattr(cmd, "id", None)
                cmd_name = cmd.get("name") if isinstance(cmd, dict) else getattr(cmd, "name", "")
                
                if cmd_id in created_by_command:
                    continue

                if cmd_id in policy_invoked_command_ids or cmd_name in policy_invoked_command_names:
                    continue

                story_ids = getattr(cmd, "user_story_ids", []) or []
                chosen_us_id = None
                chosen_ui_desc = ""
                for us_id in story_ids:
                    if us_id in user_story_ui:
                        chosen_us_id = us_id
                        chosen_ui_desc = user_story_ui[us_id]
                        break

                if not chosen_ui_desc:
                    continue

                # Add task for parallel processing
                command_ui_tasks.append(
                    partial(
                        _create_command_ui,
                        ctx, bc, cmd, agg, chosen_us_id, chosen_ui_desc, user_story_ui, policy_invoked_command_ids, policy_invoked_command_names
                    )
                )
                created_by_command.add(cmd_id)

        # -------------------------------------------------------------
        # ReadModel UI - collect tasks
        # -------------------------------------------------------------
        for rm in ctx.readmodels_by_bc.get(bc_id, []) or []:
            rm_id = rm.get("id")
            if not rm_id or rm_id in created_by_readmodel:
                continue

            story_ids = rm.get("user_story_ids", []) or []
            chosen_us_id = None
            chosen_ui_desc = ""
            for us_id in story_ids:
                if us_id in user_story_ui:
                    chosen_us_id = us_id
                    chosen_ui_desc = user_story_ui[us_id]
                    break

            if not chosen_ui_desc:
                continue

            # Add task for parallel processing
            readmodel_ui_tasks.append(
                partial(
                    _create_readmodel_ui,
                    ctx, bc, rm, chosen_us_id, chosen_ui_desc, user_story_ui
                )
            )
            created_by_readmodel.add(rm_id)

    # Bulk-with-binding (FR-019b): if a :FigmaBinding is active, after each
    # batch of UI creations finishes we hand the just-created UI ids to
    # figma_binding.bulk_sync.sync_batch which (a) ensures Figma pages exist
    # for the storyboards owning these UIs and (b) pushes each sceneGraph as
    # a Figma frame. Failures don't halt ingestion (FR-020 contract); they
    # set figmaSyncStatus on the affected :UI nodes for the FR-020 retry UX.
    # Lazy import — keeps the ingestion phase import graph clean.
    from api.features.figma_binding import bulk_sync as _figma_bulk_sync, repository as _fb_repo

    def _binding_active() -> bool:
        try:
            return _fb_repo.get_active_binding() is not None
        except Exception:
            return False

    # Process UI creation in batches (10 at a time to avoid overwhelming LLM API)
    BATCH_SIZE = 10
    all_tasks = command_ui_tasks + readmodel_ui_tasks

    for i in range(0, len(all_tasks), BATCH_SIZE):
        batch = all_tasks[i:i + BATCH_SIZE]
        results = await asyncio.gather(*[task() for task in batch], return_exceptions=True)

        # Collect UI ids written this batch for the figma sync sub-step.
        batch_ui_ids: list[str] = []

        for result in results:
            if isinstance(result, Exception):
                SmartLogger.log(
                    "ERROR",
                    "UI creation task failed",
                    category="ingestion.ui_wireframe.error",
                    params={"session_id": ctx.session.id, "error": str(result)},
                )
                continue

            ui, progress_event = result
            if ui is not None and progress_event is not None:
                ctx.uis.append(ui)
                created += 1
                yield progress_event
                ui_id = ui.get("id")
                if ui_id:
                    batch_ui_ids.append(ui_id)

        # Figma sync sub-step (FR-019b). Skipped silently if no binding.
        # FR-021: cancel-flag check happens AFTER this — the batch + its
        # sync sub-step are treated as one logical unit that runs to
        # natural completion before the next batch is dispatched.
        if batch_ui_ids and _binding_active():
            sync_events: list[tuple[str, dict]] = []

            def _capture(name: str, payload: dict) -> None:
                sync_events.append((name, payload))

            try:
                summary = await _figma_bulk_sync.sync_batch(
                    session_id=ctx.session.id,
                    ui_ids=batch_ui_ids,
                    on_event=_capture,
                )
            except Exception as e:  # noqa: BLE001 — never fail ingestion on figma issues
                SmartLogger.log(
                    "ERROR",
                    f"figma_binding.bulk_sync crashed: {e}",
                    category="figma_binding.bulk_sync.error",
                    params={"session_id": ctx.session.id, "error": str(e)},
                )
                summary = {"skipped": False, "syncedCount": 0, "failedCount": len(batch_ui_ids)}

            # Forward the captured per-UI events into the ingestion SSE stream
            # as ProgressEvent payloads. The frontend's existing 'progress'
            # listener picks them up via the data.figmaSync key (no new SSE
            # event type registration needed in this phase — see FR-020 UI
            # bits in Group D for the dedicated frontend handlers).
            for name, payload in sync_events:
                yield ProgressEvent(
                    phase=IngestionPhase.GENERATING_UI,
                    message=f"Figma 동기화: {payload.get('uiId', '')}",
                    progress=89,
                    data={"figmaSync": {"event": name, **payload}},
                )

    # 생성 결과 요약
    SmartLogger.log(
        "INFO",
        f"UI wireframes generation completed: {created} UIs created",
        category="ingestion.workflow.ui.summary",
        params={"session_id": ctx.session.id, "created_count": created},
    )


