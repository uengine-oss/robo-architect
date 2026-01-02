from __future__ import annotations

import asyncio
import html as _html
import re
import time
from typing import AsyncGenerator

from langchain_core.messages import HumanMessage, SystemMessage

from api.features.ingestion.ingestion_contracts import IngestionPhase, ProgressEvent
from api.features.ingestion.workflow.ingestion_workflow_context import IngestionWorkflowContext
from api.platform.env import get_llm_provider_model
from api.platform.observability.smart_logger import SmartLogger


_UI_WIREFRAME_SYSTEM_PROMPT = """You generate a wireframe-level HTML template for a single screen.\n\nOutput rules (STRICT):\n- Output ONLY raw HTML. Do NOT use markdown or code fences.\n- Do NOT include <script> tags.\n- Do NOT include inline event handlers like onclick=, onload=, etc.\n- Do NOT use javascript: URLs.\n- Keep it wireframe-level: structural layout + placeholder inputs/buttons/tables.\n\nContent requirements:\n- Include a clear screen title.\n- Include sections for search/filter/list/detail when implied.\n- Use simple semantic tags: <div>, <header>, <section>, <h1>-<h3>, <p>, <label>, <input>, <button>, <table>, <thead>, <tbody>, <tr>, <th>, <td>.\n"""


def _strip_markdown_fences(text: str) -> str:
    """
    Best-effort removal of markdown code fences the LLM might accidentally emit.
    """
    s = (text or "").strip()
    if not s:
        return ""
    # Remove leading ```lang and trailing ```
    s = re.sub(r"^\s*```[a-zA-Z0-9_-]*\s*", "", s)
    s = re.sub(r"\s*```\s*$", "", s)
    return s.strip()


def _sanitize_html_template(html: str) -> str:
    """
    Minimal HTML safety pass (baseline policy):
    - Remove <script> blocks
    - Remove inline event handlers (on*)
    - Strip javascript: URLs

    NOTE: Not a full sanitizer; scoped to the explicit constraints for wireframe preview.
    """
    if not isinstance(html, str):
        return ""

    # Remove script blocks
    html = re.sub(r"<\s*script\b[^>]*>.*?<\s*/\s*script\s*>", "", html, flags=re.IGNORECASE | re.DOTALL)

    # Remove inline event handlers like onclick="..." or onload='...'
    html = re.sub(r"\s+on[a-zA-Z]+\s*=\s*(\"[^\"]*\"|'[^']*'|[^\s>]+)", "", html, flags=re.IGNORECASE)

    # Remove javascript: in href/src (best-effort)
    html = re.sub(r"javascript\s*:", "", html, flags=re.IGNORECASE)
    return html


def _keyword_blocks(ui_text: str) -> str:
    """
    Deterministic wireframe blocks based on keywords (Korean-focused; lightweight).
    """
    t = (ui_text or "")
    blocks: list[str] = []

    if any(k in t for k in ["검색", "search"]):
        blocks.append(
            """
            <section class="wf-section wf-section--search">
              <h3>검색</h3>
              <div>
                <label>검색어</label>
                <input type="text" placeholder="검색어를 입력하세요" />
                <button type="button">검색</button>
              </div>
            </section>
            """
        )

    if any(k in t for k in ["필터", "filter"]):
        blocks.append(
            """
            <section class="wf-section wf-section--filter">
              <h3>필터</h3>
              <div>
                <label>상태</label>
                <input type="text" placeholder="예: 진행중 / 완료" />
                <button type="button">적용</button>
                <button type="button">초기화</button>
              </div>
            </section>
            """
        )

    if any(k in t for k in ["목록", "리스트", "list"]):
        blocks.append(
            """
            <section class="wf-section wf-section--list">
              <h3>목록</h3>
              <table border="1" cellpadding="6" cellspacing="0">
                <thead>
                  <tr><th>컬럼 A</th><th>컬럼 B</th><th>상태</th><th>액션</th></tr>
                </thead>
                <tbody>
                  <tr><td>...</td><td>...</td><td>...</td><td><button type="button">보기</button></td></tr>
                  <tr><td>...</td><td>...</td><td>...</td><td><button type="button">보기</button></td></tr>
                </tbody>
              </table>
            </section>
            """
        )

    if any(k in t for k in ["상세", "detail"]):
        blocks.append(
            """
            <section class="wf-section wf-section--detail">
              <h3>상세</h3>
              <div>
                <div><strong>필드 1</strong>: <span>...</span></div>
                <div><strong>필드 2</strong>: <span>...</span></div>
                <div><strong>필드 3</strong>: <span>...</span></div>
              </div>
            </section>
            """
        )

    return "\n".join(blocks).strip()


def _fallback_wireframe_html(*, ui_name: str, attached_to_label: str, ui_description: str, keyword_blocks: str) -> str:
    safe_name = _html.escape(ui_name or "UI")
    safe_attached = _html.escape(attached_to_label or "")
    safe_desc = _html.escape(ui_description or "")
    extra = keyword_blocks or ""
    return f"""
<div class="wireframe">
  <header class="wf-header">
    <h2>{safe_name}</h2>
    <p>{safe_attached}</p>
  </header>
  <section class="wf-section wf-section--intent">
    <h3>의도</h3>
    <pre>{safe_desc}</pre>
  </section>
  {extra}
  <section class="wf-section wf-section--actions">
    <h3>액션</h3>
    <div>
      <button type="button">Primary</button>
      <button type="button">Secondary</button>
    </div>
  </section>
</div>
""".strip()


def _safe_wireframe_wrapper(
    *,
    ui_name: str,
    attached_to_label: str,
    ui_description: str,
    llm_body_html: str,
    keyword_blocks: str,
) -> str:
    safe_name = _html.escape(ui_name or "UI")
    safe_attached = _html.escape(attached_to_label or "")
    safe_desc = _html.escape(ui_description or "")
    body = (llm_body_html or "").strip()
    extra = keyword_blocks or ""
    return f"""
<div class="wireframe">
  <header class="wf-header">
    <h2>{safe_name}</h2>
    <p>{safe_attached}</p>
  </header>
  <section class="wf-section wf-section--intent">
    <h3>의도</h3>
    <pre>{safe_desc}</pre>
  </section>
  {extra}
  <section class="wf-section wf-section--generated">
    <h3>와이어프레임</h3>
    {body}
  </section>
</div>
""".strip()


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

    for bc in ctx.bounded_contexts or []:
        # -------------------------------------------------------------
        # Command UI
        # -------------------------------------------------------------
        for agg in ctx.aggregates_by_bc.get(bc.id, []) or []:
            for cmd in ctx.commands_by_agg.get(agg.id, []) or []:
                if cmd.id in created_by_command:
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
                ui_name = f"{cmd.name} UI"

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

                    attached_to_label = f"Attached to Command: {cmd.name} ({cmd.id})"
                    keyword_blocks = _keyword_blocks(f"{ui_name}\n{chosen_ui_desc}")

                    fallback_used = False
                    llm_ms = 0
                    if existing_template is not None:
                        final_template = str(existing_template)
                        fallback_used = False
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
                            },
                        )
                        t0 = time.perf_counter()
                        raw_html = _llm_invoke_to_html(ctx, prompt)
                        llm_ms = int((time.perf_counter() - t0) * 1000)

                        raw_html = _strip_markdown_fences(raw_html)
                        raw_html = _sanitize_html_template(raw_html)

                        if not isinstance(raw_html, str) or not raw_html.strip():
                            fallback_used = True
                            final_template = _fallback_wireframe_html(
                                ui_name=ui_name,
                                attached_to_label=attached_to_label,
                                ui_description=chosen_ui_desc,
                                keyword_blocks=keyword_blocks,
                            )
                        else:
                            final_template = _safe_wireframe_wrapper(
                                ui_name=ui_name,
                                attached_to_label=attached_to_label,
                                ui_description=chosen_ui_desc,
                                llm_body_html=raw_html,
                                keyword_blocks=keyword_blocks,
                            )

                        # Final safety pass + size guard
                        final_template = _sanitize_html_template(final_template)
                        if len(final_template) > 50000:
                            fallback_used = True
                            final_template = _fallback_wireframe_html(
                                ui_name=ui_name,
                                attached_to_label=attached_to_label,
                                ui_description=chosen_ui_desc,
                                keyword_blocks=keyword_blocks,
                            )

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
            ui_name = f"{rm.get('name', rm_id)} UI"

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

                attached_to_label = f"Attached to ReadModel: {rm.get('name', rm_id)} ({rm_id})"
                keyword_blocks = _keyword_blocks(f"{ui_name}\n{chosen_ui_desc}")

                fallback_used = False
                llm_ms = 0
                if existing_template is not None:
                    final_template = str(existing_template)
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
                        },
                    )
                    t0 = time.perf_counter()
                    raw_html = _llm_invoke_to_html(ctx, prompt)
                    llm_ms = int((time.perf_counter() - t0) * 1000)

                    raw_html = _strip_markdown_fences(raw_html)
                    raw_html = _sanitize_html_template(raw_html)

                    if not isinstance(raw_html, str) or not raw_html.strip():
                        fallback_used = True
                        final_template = _fallback_wireframe_html(
                            ui_name=ui_name,
                            attached_to_label=attached_to_label,
                            ui_description=chosen_ui_desc,
                            keyword_blocks=keyword_blocks,
                        )
                    else:
                        final_template = _safe_wireframe_wrapper(
                            ui_name=ui_name,
                            attached_to_label=attached_to_label,
                            ui_description=chosen_ui_desc,
                            llm_body_html=raw_html,
                            keyword_blocks=keyword_blocks,
                        )

                    final_template = _sanitize_html_template(final_template)
                    if len(final_template) > 50000:
                        fallback_used = True
                        final_template = _fallback_wireframe_html(
                            ui_name=ui_name,
                            attached_to_label=attached_to_label,
                            ui_description=chosen_ui_desc,
                            keyword_blocks=keyword_blocks,
                        )

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


