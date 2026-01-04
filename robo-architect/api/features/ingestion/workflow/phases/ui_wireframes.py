from __future__ import annotations

import asyncio
import time
from typing import AsyncGenerator

from langchain_core.messages import HumanMessage, SystemMessage

from api.features.ingestion.ingestion_contracts import IngestionPhase, ProgressEvent
from api.features.ingestion.workflow.ingestion_workflow_context import IngestionWorkflowContext
from api.platform.env import get_llm_provider_model
from api.platform.observability.smart_logger import SmartLogger
from api.platform.ui_wireframe_template import normalize_ui_template


_UI_WIREFRAME_SYSTEM_PROMPT = """You generate a modern UI wireframe HTML fragment for a single screen (Ant Design-like or Material-like).\n\nOutput rules (STRICT):\n- Output ONLY raw HTML fragment. Do NOT use markdown or code fences.\n- Do NOT output <!doctype>, <html>, <head>, <body>.\n- Do NOT include <script> tags.\n- Do NOT include inline event handlers like onclick=, onload=, etc.\n- Do NOT use javascript: URLs.\n- You MAY include a <style> block, but:\n  - Every selector MUST be scoped under `.wf-root`\n  - MUST NOT use @import or url(...)\n\nRoot container (MUST):\n- The fragment MUST start with a root container like:\n  <div class=\"wf-root wf-theme-ant\" data-wf-root=\"1\"> ... </div>\n  or\n  <div class=\"wf-root wf-theme-material\" data-wf-root=\"1\"> ... </div>\n\nModern UI quality requirements:\n- Use an App Bar / Toolbar at the top (title + primary actions).\n- Use Card-based sections.\n- For table/list screens: include a table toolbar (search/filter/actions), column headers, row actions, and pagination area.\n- For form screens: use a 2-column grid layout, labels + help/validation placeholders, primary/secondary button group.\n- Optionally include tabs/segments, chips/badges, and empty/loading/error state placeholders.\n- No JS behavior; structure only. Prefer accessible attributes (aria-*, role).\n\nPrefer these classes to match the preview styling:\n- wf-appbar, wf-title, wf-subtitle, wf-card, wf-card__header, wf-card__title, wf-card__body,\n  wf-actions, wf-btn, wf-btn--primary, wf-input, wf-label, wf-grid, wf-col-6, wf-col-12,\n  wf-table, wf-table__toolbar, wf-pagination, wf-chip, wf-badge, wf-state, wf-state--error, wf-empty\n"""



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
            rec = session.run("MATCH (ui:UI {id: $id}) RETURN ui.template as template", id=ui_id).single()
            t = rec.get("template") if rec else None
            if isinstance(t, str) and t.strip():
                return t
    except Exception:
        return None
    return None


def _llm_invoke_to_html(ctx: IngestionWorkflowContext, prompt: str) -> str:
    """
    Invoke the configured LLM and extract plain HTML text.
    """
    resp = ctx.llm.invoke([SystemMessage(content=_UI_WIREFRAME_SYSTEM_PROMPT), HumanMessage(content=prompt)])
    if isinstance(resp, str):
        return resp
    content = getattr(resp, "content", None)
    if isinstance(content, str):
        return content
    return str(resp)


async def generate_ui_wireframes_phase(ctx: IngestionWorkflowContext) -> AsyncGenerator[ProgressEvent, None]:
    """
    Optional phase: generate UI wireframe stickers for commands and readmodels, based on user story ui_description.

    Design goal: keep this lightweight and deterministic:
    - Create at most 1 UI per Command
    - Create at most 1 UI per ReadModel
    - Use the first related user story that has a ui_description
    - Attach UI to Command/ReadModel (ATTACHED_TO), and to BC (HAS_UI)
    """
    yield ProgressEvent(phase=IngestionPhase.GENERATING_UI, message="UI 와이어프레임 생성 중...", progress=87)

    user_story_ui: dict[str, str] = {}
    for us in ctx.user_stories or []:
        ui_desc = getattr(us, "ui_description", "") or ""
        if ui_desc.strip():
            user_story_ui[us.id] = ui_desc.strip()

    created = 0
    created_by_command: set[str] = set()
    created_by_readmodel: set[str] = set()

    # Build set of command names that are invoked by policies (no UI needed)
    # Policy-invoked commands are triggered by backend events, not user interaction
    policy_invoked_commands: set[str] = set()
    for pol in ctx.policies or []:
        invoke_cmd = getattr(pol, "invoke_command", None)
        if invoke_cmd:
            policy_invoked_commands.add(invoke_cmd)

    if policy_invoked_commands:
        SmartLogger.log(
            "INFO",
            "Policy-invoked commands identified (will skip UI generation)",
            category="ingestion.ui_wireframe.policy_filter",
            params={
                "session_id": ctx.session.id,
                "policy_invoked_commands": list(policy_invoked_commands),
            },
        )

    for bc in ctx.bounded_contexts or []:
        # -------------------------------------------------------------
        # Command UI
        # -------------------------------------------------------------
        for agg in ctx.aggregates_by_bc.get(bc.id, []) or []:
            for cmd in ctx.commands_by_agg.get(agg.id, []) or []:
                if cmd.id in created_by_command:
                    continue

                # Skip commands invoked by policies (they don't need UI - triggered by backend events)
                if cmd.name in policy_invoked_commands:
                    SmartLogger.log(
                        "INFO",
                        "UI generation skipped for policy-invoked command",
                        category="ingestion.ui_wireframe.skip",
                        params={
                            "session_id": ctx.session.id,
                            "command_id": cmd.id,
                            "command_name": cmd.name,
                        },
                    )
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

                # Deterministic + collision-free (explicit target type)
                ui_id = f"UI-CMD-{cmd.id}"
                ui_name = cmd.name

                try:
                    # Avoid extra generation if template already exists (idempotency / 1x per node)
                    existing_template = _existing_ui_template_best_effort(ctx, ui_id)

                    # Prompt enrichment (best-effort)
                    us_obj = next((u for u in (ctx.user_stories or []) if getattr(u, "id", None) == chosen_us_id), None)
                    user_story_text = ""
                    if us_obj is not None:
                        role = getattr(us_obj, "role", "") or ""
                        action = getattr(us_obj, "action", "") or ""
                        benefit = getattr(us_obj, "benefit", "") or ""
                        user_story_text = f"[{chosen_us_id}] As a {role}, I want to {action}, so that {benefit}".strip()

                    events = _fetch_command_events_best_effort(ctx, cmd.id)
                    events_text = "\n".join([f"- {e}" for e in events]) if events else "No events found"

                    theme_hint = f"{ui_name}\n{chosen_ui_desc}"
                    fallback_used = False
                    llm_ms = 0
                    if existing_template is not None:
                        final_template, norm_report = normalize_ui_template(
                            str(existing_template),
                            ui_name=ui_name,
                            theme_hint=theme_hint,
                        )
                        fallback_used = bool(getattr(norm_report, "fallback_used", False))
                        SmartLogger.log(
                            "INFO",
                            "UI wireframe template reused and normalized",
                            category="ingestion.ui_wireframe.normalize",
                            params={
                                "session_id": ctx.session.id,
                                "ui_id": ui_id,
                                "ui_name": ui_name,
                                "attached_to_id": cmd.id,
                                "attached_to_type": "Command",
                                "source": "existing_template",
                                "llm_ms": 0,
                                "fallback_used": fallback_used,
                                "template_len": len(final_template),
                                "normalize": norm_report.as_dict(),
                                # Reproducibility
                                "inputs": {
                                    "bc": {"id": bc.id, "name": bc.name},
                                    "command": {"id": cmd.id, "name": cmd.name},
                                    "user_story_id": chosen_us_id,
                                    "user_story_text": user_story_text,
                                    "ui_description": chosen_ui_desc,
                                    "events": events,
                                    "events_text": events_text,
                                    "theme_hint": theme_hint,
                                },
                                "template_before": str(existing_template),
                                "template_after": final_template,
                            }
                        )
                    else:
                        prompt = f"""Generate a wireframe HTML template.\n\nUI Name: {ui_name}\nBounded Context: {bc.name} ({bc.id})\nAttached To: Command {cmd.name} ({cmd.id})\nUser Story: {user_story_text or f'[{chosen_us_id}]'}\nui_description:\n{chosen_ui_desc}\n\nRelated Events emitted by the Command:\n{events_text}\n"""

                        provider, model = get_llm_provider_model()
                        SmartLogger.log(
                            "INFO",
                            "UI wireframe LLM invoke starting",
                            category="ingestion.llm.ui_wireframe.start",
                            params={
                                "session_id": ctx.session.id,
                                "ui_id": ui_id,
                                "ui_name": ui_name,
                                "attached_to_id": cmd.id,
                                "attached_to_type": "Command",
                                "llm": {"provider": provider, "model": model},
                                # Reproducibility
                                "inputs": {
                                    "bc": {"id": bc.id, "name": bc.name},
                                    "command": {"id": cmd.id, "name": cmd.name},
                                    "user_story_id": chosen_us_id,
                                    "user_story_text": user_story_text,
                                    "ui_description": chosen_ui_desc,
                                    "events": events,
                                    "events_text": events_text,
                                    "prompt": prompt,
                                    "theme_hint": theme_hint,
                                },
                            }
                        )
                        t0 = time.perf_counter()
                        raw_html = _llm_invoke_to_html(ctx, prompt)
                        llm_ms = int((time.perf_counter() - t0) * 1000)

                        final_template, norm_report = normalize_ui_template(
                            str(raw_html),
                            ui_name=ui_name,
                            theme_hint=theme_hint,
                        )
                        fallback_used = bool(getattr(norm_report, "fallback_used", False))

                        SmartLogger.log(
                            "INFO",
                            "UI wireframe LLM invoke completed",
                            category="ingestion.llm.ui_wireframe.done",
                            params={
                                "session_id": ctx.session.id,
                                "ui_id": ui_id,
                                "ui_name": ui_name,
                                "attached_to_id": cmd.id,
                                "attached_to_type": "Command",
                                "llm_ms": llm_ms,
                                "fallback_used": fallback_used,
                                "template_len": len(final_template),
                                "normalize": norm_report.as_dict(),
                                # Reproducibility
                                "raw_llm_output": str(raw_html),
                                "normalized_template": final_template,
                            },
                        )

                    ui = ctx.client.create_ui(
                        id=ui_id,
                        name=ui_name,
                        bc_id=bc.id,
                        description=chosen_ui_desc,
                        template=final_template,
                        attached_to_id=cmd.id,
                        attached_to_type="Command",
                        attached_to_name=cmd.name,
                        user_story_id=chosen_us_id,
                    )
                    ctx.uis.append(ui)
                    created += 1
                    created_by_command.add(cmd.id)

                    yield ProgressEvent(
                        phase=IngestionPhase.GENERATING_UI,
                        message=f"UI 생성: {ui_name}",
                        progress=88,
                        data={
                            "type": "UI",
                            "object": {
                                "id": ui_id,
                                "name": ui_name,
                                "type": "UI",
                                "parentId": bc.id,
                                "template": final_template,
                                "attachedToId": cmd.id,
                                "attachedToType": "Command",
                                "attachedToName": cmd.name,
                                "userStoryId": chosen_us_id,
                                "description": chosen_ui_desc,
                            },
                        },
                    )
                    await asyncio.sleep(0.08)
                except Exception as e:
                    SmartLogger.log(
                        "WARNING",
                        "UI creation skipped",
                        category="ingestion.neo4j.ui",
                        params={"session_id": ctx.session.id, "ui_id": ui_id, "command_id": cmd.id, "error": str(e)},
                    )

        # -------------------------------------------------------------
        # ReadModel UI
        # -------------------------------------------------------------
        for rm in ctx.readmodels_by_bc.get(bc.id, []) or []:
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

            ui_id = f"UI-RM-{rm_id}"
            ui_name = rm.get('name', rm_id)

            try:
                # Avoid extra generation if template already exists (idempotency / 1x per node)
                existing_template = _existing_ui_template_best_effort(ctx, ui_id)

                # User story enrichment (best-effort)
                us_obj = next((u for u in (ctx.user_stories or []) if getattr(u, "id", None) == chosen_us_id), None)
                user_story_text = ""
                if us_obj is not None:
                    role = getattr(us_obj, "role", "") or ""
                    action = getattr(us_obj, "action", "") or ""
                    benefit = getattr(us_obj, "benefit", "") or ""
                    user_story_text = f"[{chosen_us_id}] As a {role}, I want to {action}, so that {benefit}".strip()

                theme_hint = f"{ui_name}\n{chosen_ui_desc}"
                fallback_used = False
                llm_ms = 0
                if existing_template is not None:
                    final_template, norm_report = normalize_ui_template(
                        str(existing_template),
                        ui_name=ui_name,
                        theme_hint=theme_hint,
                    )
                    fallback_used = bool(getattr(norm_report, "fallback_used", False))
                    SmartLogger.log(
                        "INFO",
                        "UI wireframe template reused and normalized",
                        category="ingestion.ui_wireframe.normalize",
                        params={
                            "session_id": ctx.session.id,
                            "ui_id": ui_id,
                            "ui_name": ui_name,
                            "attached_to_id": rm_id,
                            "attached_to_type": "ReadModel",
                            "source": "existing_template",
                            "llm_ms": 0,
                            "fallback_used": fallback_used,
                            "template_len": len(final_template),
                            "normalize": norm_report.as_dict(),
                            # Reproducibility
                            "inputs": {
                                "bc": {"id": bc.id, "name": bc.name},
                                "readmodel": {"id": rm_id, "name": rm.get("name", rm_id)},
                                "user_story_id": chosen_us_id,
                                "user_story_text": user_story_text,
                                "ui_description": chosen_ui_desc,
                                "theme_hint": theme_hint,
                            },
                            "template_before": str(existing_template),
                            "template_after": final_template,
                        },
                    )
                else:
                    prompt = f"""Generate a wireframe HTML template.\n\nUI Name: {ui_name}\nBounded Context: {bc.name} ({bc.id})\nAttached To: ReadModel {rm.get('name', rm_id)} ({rm_id})\nUser Story: {user_story_text or f'[{chosen_us_id}]'}\nui_description:\n{chosen_ui_desc}\n"""

                    provider, model = get_llm_provider_model()
                    SmartLogger.log(
                        "INFO",
                        "UI wireframe LLM invoke starting",
                        category="ingestion.llm.ui_wireframe.start",
                        params={
                            "session_id": ctx.session.id,
                            "ui_id": ui_id,
                            "ui_name": ui_name,
                            "attached_to_id": rm_id,
                            "attached_to_type": "ReadModel",
                            "llm": {"provider": provider, "model": model},
                            # Reproducibility
                            "inputs": {
                                "bc": {"id": bc.id, "name": bc.name},
                                "readmodel": {"id": rm_id, "name": rm.get("name", rm_id)},
                                "user_story_id": chosen_us_id,
                                "user_story_text": user_story_text,
                                "ui_description": chosen_ui_desc,
                                "prompt": prompt,
                                "theme_hint": theme_hint,
                            },
                        },
                    )
                    t0 = time.perf_counter()
                    raw_html = _llm_invoke_to_html(ctx, prompt)
                    llm_ms = int((time.perf_counter() - t0) * 1000)

                    final_template, norm_report = normalize_ui_template(
                        str(raw_html),
                        ui_name=ui_name,
                        theme_hint=theme_hint,
                    )
                    fallback_used = bool(getattr(norm_report, "fallback_used", False))

                    SmartLogger.log(
                        "INFO",
                        "UI wireframe LLM invoke completed",
                        category="ingestion.llm.ui_wireframe.done",
                        params={
                            "session_id": ctx.session.id,
                            "ui_id": ui_id,
                            "ui_name": ui_name,
                            "attached_to_id": rm_id,
                            "attached_to_type": "ReadModel",
                            "llm_ms": llm_ms,
                            "fallback_used": fallback_used,
                            "template_len": len(final_template),
                            "normalize": norm_report.as_dict(),
                            # Reproducibility
                            "raw_llm_output": str(raw_html),
                            "normalized_template": final_template,
                        },
                    )

                ui = ctx.client.create_ui(
                    id=ui_id,
                    name=ui_name,
                    bc_id=bc.id,
                    description=chosen_ui_desc,
                    template=final_template,
                    attached_to_id=rm_id,
                    attached_to_type="ReadModel",
                    attached_to_name=rm.get("name"),
                    user_story_id=chosen_us_id,
                )
                ctx.uis.append(ui)
                created += 1
                created_by_readmodel.add(rm_id)

                yield ProgressEvent(
                    phase=IngestionPhase.GENERATING_UI,
                    message=f"UI 생성: {ui_name}",
                    progress=88,
                    data={
                        "type": "UI",
                        "object": {
                            "id": ui_id,
                            "name": ui_name,
                            "type": "UI",
                            "parentId": bc.id,
                            "template": final_template,
                            "attachedToId": rm_id,
                            "attachedToType": "ReadModel",
                            "attachedToName": rm.get("name"),
                            "userStoryId": chosen_us_id,
                            "description": chosen_ui_desc,
                        },
                    },
                )
                await asyncio.sleep(0.08)
            except Exception as e:
                SmartLogger.log(
                    "WARNING",
                    "UI creation skipped",
                    category="ingestion.neo4j.ui",
                    params={"session_id": ctx.session.id, "ui_id": ui_id, "readmodel_id": rm_id, "error": str(e)},
                )

    SmartLogger.log(
        "INFO",
        "UI wireframes generated",
        category="ingestion.workflow.ui",
        params={"session_id": ctx.session.id, "count": created},
    )


