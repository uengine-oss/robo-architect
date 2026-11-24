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
                   ui.attachedToId AS attachedToId,
                   ui.template AS template,
                   bc.name AS bcName
            """,
            id=ui_node_id,
        ).single()
        if not rec:
            return None
        ctx = dict(rec)
        # 2026-11-24: 생성 단계와 같은 재료 — 붙은 Command · ReadModel 의 필드와 목록/상세 구분
        ctx["fields"] = []
        ctx["multiple"] = None
        kind = ctx.get("attachedToType")
        if kind in ("Command", "ReadModel") and ctx.get("attachedToId"):
            try:
                rows = session.run(
                    f"""
                    MATCH (n:{kind} {{id: $id}})-[:HAS_PROPERTY]->(p:Property)
                    RETURN p.name as name, p.displayName as displayName, p.type as type,
                           p.isRequired as isRequired, p.description as description
                    """,
                    id=ctx["attachedToId"],
                )
                ctx["fields"] = [dict(r) for r in rows if r and r.get("name")]
                if kind == "ReadModel":
                    m = session.run("MATCH (n:ReadModel {id: $id}) RETURN n.isMultipleResult as m",
                                    id=ctx["attachedToId"]).single()
                    ctx["multiple"] = m["m"] if m else None
            except Exception:  # noqa: BLE001 — 재료가 없으면 예전처럼 만든다
                pass
    return ctx


_STYLE_RE = None


def _strip_style(html: str) -> str:
    """LLM 에 보낼 때는 테마 CSS 를 뺀다 — 화면 구조만 보면 된다. 돌려받은 뒤 normalize 가 다시 넣는다."""
    import re

    global _STYLE_RE
    if _STYLE_RE is None:
        _STYLE_RE = re.compile(r"(?is)<\s*style\b[^>]*>.*?<\s*/\s*style\s*>")
    return _STYLE_RE.sub("", html or "").strip()


def build_prompts(ctx: dict, instruction: str = "", display_lang: str = "ko") -> tuple[str, str, str]:
    """(system_prompt, user_prompt, ui_name) — LLM 없이 시험할 수 있게 떼어 둔다.

    2026-11-24: 처음 생성(ES 승격)과 **같은 규칙**을 쓴다 — 시스템 프롬프트 · 모델 필드 · 화면 종류(입력 폼 /
    조회 목록 / 조회 상세). 전에는 이 수정 챗만 옛 규칙(스타일 직접 작성 · 필드 없음)이라 고칠수록 어긋났다.
    """
    from api.features.ingestion.workflow.phases.ui_wireframes import (
        _UI_WIREFRAME_SYSTEM_PROMPT,
        _html_screen_prompt,
        _rm_is_multiple,
    )

    ui_name = ctx.get("displayName") or ctx.get("name") or "Wireframe"
    ui_desc = ctx.get("description") or ""
    attached_type = ctx.get("attachedToType") or ""
    attached_name = ctx.get("attachedToName") or ""
    bc_name = ctx.get("bcName") or ""
    existing_template = _strip_style(ctx.get("template") or "")
    fields = ctx.get("fields") or []

    lang_instruction = (
        "All visible text MUST be written in Korean (한글)."
        if display_lang == "ko"
        else "All visible text MUST be written in English."
    )
    system_prompt = f"{_UI_WIREFRAME_SYSTEM_PROMPT}\n- {lang_instruction}\n"

    context = (
        f"Screen: {ui_name}\n"
        + (f"Bounded Context: {bc_name}\n" if bc_name else "")
        + (f"Attached to: {attached_type} {attached_name}\n" if attached_name else "")
        + (f"Description: {ui_desc}\n" if ui_desc else "")
    )
    kind = "ReadModel" if attached_type == "ReadModel" else "Command"
    # 화면 종류 · 필드 규칙(생성 단계와 같은 문장)
    rules = _html_screen_prompt(kind, context.strip(), fields, multiple=_rm_is_multiple(ctx.get("multiple")))

    if instruction and existing_template:
        user_prompt = (
            f"{rules}\n\n"
            "Here is the CURRENT wireframe HTML (styles omitted — keep using the wf-* classes):\n"
            f"```html\n{existing_template}\n```\n\n"
            f"Apply this change and return the FULL updated HTML fragment. Change only what is asked:\n{instruction}"
        )
    elif instruction:
        user_prompt = f"{rules}\n\nAdditional requirement from the user:\n{instruction}"
    else:
        user_prompt = rules
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
