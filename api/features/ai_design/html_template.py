"""UI 노드의 HTML 와이어프레임(`ui.template`) 생성·수정 — 하나의 생성기.

캔버스 인스펙터(`POST /api/ai-design/html-edit/{id}`)와 프로포절 Accept 뒤
"UI 와이어프레임 생성"(D-5 ⑰)이 **같은 함수**를 쓴다. 새 생성기를 짜지 않는다.

캔버스 UINode 의 "✓ Wireframe / No wireframe" 은 `ui.template` 유무로 갈린다 —
그래서 이 생성기가 채우는 값이 곧 그 배지다.
"""

from __future__ import annotations

from langchain_core.messages import HumanMessage

from api.platform.llm_messages import build_system_message


class UINodeNotFound(LookupError):
    pass


class TemplateGenerationError(RuntimeError):
    pass


def _load_ui_context(ui_node_id: str) -> dict | None:
    from api.platform.neo4j import get_session

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
    return dict(rec) if rec else None


def build_prompts(ctx: dict, instruction: str = "", display_lang: str = "ko") -> tuple[str, str, str]:
    """(system_prompt, user_prompt, ui_name) — LLM 없이 시험할 수 있게 떼어 둔다."""
    ui_name = ctx.get("displayName") or ctx.get("name") or "Wireframe"
    ui_desc = ctx.get("description") or ""
    attached_type = ctx.get("attachedToType") or ""
    attached_name = ctx.get("attachedToName") or ""
    bc_name = ctx.get("bcName") or ""
    existing_template = ctx.get("template") or ""

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
    return system_prompt, user_prompt, ui_name


async def generate_html_template(ui_node_id: str, instruction: str = "",
                                 display_lang: str = "ko") -> str:
    """UI 노드 문맥으로 HTML 와이어프레임을 만들거나(instruction 없음) 고쳐서
    `ui.template` 에 저장하고 그 값을 돌려준다."""
    from api.platform.llm import get_llm
    from api.platform.neo4j import get_session
    from api.platform.ui_wireframe_template import normalize_ui_template

    ctx = _load_ui_context(ui_node_id)
    if not ctx:
        raise UINodeNotFound(f"UI node {ui_node_id} not found")

    system_prompt, user_prompt, ui_name = build_prompts(ctx, instruction, display_lang)

    try:
        llm = get_llm()
        # async 경로 — 동기 .invoke() 는 이벤트 루프를 막는다(서버 전체가 멈춘다).
        resp = await llm.ainvoke([build_system_message(system_prompt), HumanMessage(content=user_prompt)])
        raw_html = resp if isinstance(resp, str) else getattr(resp, "content", str(resp))
        if not isinstance(raw_html, str):
            raw_html = str(raw_html)
    except Exception as e:  # noqa: BLE001
        raise TemplateGenerationError(f"LLM 호출 실패: {e}") from e

    template, _report = normalize_ui_template(raw_html, ui_name=ui_name)

    with get_session() as session:
        session.run(
            "MATCH (ui:UI {id: $id}) SET ui.template = $tmpl, ui.updatedAt = datetime()",
            id=ui_node_id,
            tmpl=template,
        )
    return template
