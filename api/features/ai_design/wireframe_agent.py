"""Backend-side wireframe generation agent.

This is the "real" backend port of open-pencil's AI design generation —
it runs the LLM agent loop on the server, calls the wireframe service
(`api/platform/open_pencil_client.py`) to convert JSX → SceneGraph, and
persists the result to the UI node in Neo4j.

Why backend-only? See specs/016-figma-document-binding decisions and
the conversation that produced this module: bulk generation triggered
by ingestion completion + Figma binding can't reliably run in the
browser, and CORE_TOOLS used during initial generation are essentially
just `render(jsx)` + `calc(expr)` — both portable.

This module is the *initial generation* path. Interactive
chat-refinement of an existing design (where read-back tools matter)
stays browser-side for now.
"""

from __future__ import annotations

import asyncio
import json
import math
import re
import uuid
from typing import Any, AsyncGenerator

from fastapi import HTTPException
from langchain_core.messages import (
    AIMessage,
    HumanMessage,
    ToolMessage,
)

from api.platform.llm import get_llm
from api.platform.llm_messages import build_system_message
from api.platform.neo4j import get_session
from api.platform.observability.smart_logger import SmartLogger
from api.platform import open_pencil_client


# Maximum agent steps. open-pencil uses 50; we cap lower because our v1
# system prompt asks for a single render call — we should rarely need
# more than 2–3 turns.
MAX_AGENT_STEPS = 8


# Adapted from open-pencil/src/ai/system-prompt.md, trimmed to what's
# necessary for one-shot wireframe generation. Intentionally tells the
# LLM to produce a SINGLE render call so the backend can take the
# resulting SceneGraph as-is without merging multiple fragments (a
# follow-up Phase will lift this restriction).
SYSTEM_PROMPT = """You are a UI wireframe generator. Given a screen description, you produce ONE call to the `render` tool with a complete JSX wireframe for that screen, then end with a one-sentence summary.

# Rendering

The `render` tool takes JSX and produces design nodes. JavaScript expressions (map, ternaries, Array.from) work inside JSX. **Each render call must have exactly ONE root element.**

Available elements: Frame, Text, Rectangle, Ellipse, Line, Star, Polygon, Group, Section, Component, Icon.

All styling is via props — no `style`, `className`, or CSS. Colors are hex only (#RRGGBB or #RRGGBBAA).

## Props reference

**Position:** x={N}, y={N} — only without auto-layout parent.

**Sizing:** w={N}, h={N} (px), w="hug"/h="hug" (default, shrink-to-fit), w="fill"/h="fill" (stretch, requires flex parent), grow={N}, minW={N}, maxW={N}.

**Layout:** flex="row"|"col" enables auto-layout. gap={N}, wrap, rowGap={N}. justify="start"|"end"|"center"|"between" (NO "evenly"). items="start"|"end"|"center"|"stretch". Padding: p={N}, px={N}, py={N}, pt/pr/pb/pl={N}.

**Appearance:** bg="#hex", stroke="#hex", strokeWidth={N}, rounded={N}, roundedTL/TR/BL/BR={N}, opacity={0-1}, rotate={deg}, overflow="hidden", shadow="offX offY blur #color".

**Text (only on <Text>):** size={N}, weight="bold"|"medium"|{N}, color="#hex", font="Family", textAlign="left"|"center"|"right", lineHeight={N}, maxLines={N}.

**Icon:** <Icon name="lucide:heart" size={20} color="#000" /> — vector icon. Always set color.

**Identity:** name="string" for the layers panel.

## Layout rules

- Every Frame with 2+ children needs `flex="col"` or `flex="row"`.
- Every parent containing children using `w="fill"` or `h="fill"` MUST set `flex` itself.
- Multiline text MUST use `w="fill"` (NOT a fixed width).
- Text without `color` is invisible — always set color on every Text.

## Spacing & typography

Spacing from 4px grid: 4, 8, 12, 16, 20, 24, 32, 48. Padding ≥ gap. Card rounded 16–24, button 8–12, chip 4–8.

Type scale: Display 32–40, H1 24–28, H2 20–22, H3 17–18, Body 14–15, Caption 12–13. 2–3 weights max.

# Korean text

If the screen description is in Korean, USE KOREAN labels in the wireframe. Do not translate to English.

# CRITICAL: produce ONE render call

Do NOT make multiple render calls. Pack the entire screen into a single JSX root frame. The `replace_id`, `parent_id`, `insert_index`, `x`, `y` parameters are not needed for fresh generation — only `jsx` is.

If you need arithmetic, use the `calc` tool instead of doing math in your head.

After the render call succeeds, write a single-line Korean summary describing what was generated.
"""


# ─── Tool definitions for LangChain `bind_tools` ─────────────────────────


RENDER_TOOL = {
    "name": "render",
    "description": (
        "Render JSX to design nodes. Pack the entire screen into one JSX "
        "root element. Example: <Frame name=\"Card\" w={320} h=\"hug\" "
        "flex=\"col\" gap={16} p={24} bg=\"#FFF\" rounded={16}>"
        "<Text size={18} weight=\"bold\" color=\"#111\">Title</Text></Frame>"
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "jsx": {
                "type": "string",
                "description": "JSX string to render. ONE root element only.",
            },
        },
        "required": ["jsx"],
    },
}


CALC_TOOL = {
    "name": "calc",
    "description": (
        "Evaluate a math expression and return the numeric result. Supports "
        "+ - * / parentheses, floor(), ceil(), min(), max(). Use this for "
        "any layout arithmetic (column widths, gaps, totals)."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "expr": {"type": "string", "description": "Arithmetic expression."},
        },
        "required": ["expr"],
    },
}


# Whitelist of characters allowed in calc expressions (safety).
_CALC_ALLOWED = re.compile(r"^[\d\.\s\+\-\*\/\(\),floorceilminmax]+$")


def _safe_calc(expr: str) -> float:
    expr = (expr or "").strip()
    if not _CALC_ALLOWED.fullmatch(expr):
        raise ValueError(f"unsupported calc expression: {expr!r}")
    # eval with no builtins; only the four allowlisted callables.
    return eval(  # noqa: S307 — sandboxed
        expr,
        {"__builtins__": {}},
        {"floor": math.floor, "ceil": math.ceil, "min": min, "max": max},
    )


# ─── Wireframe-service render helper ─────────────────────────────────────


# Cap concurrent renders against the Bun wireframe service. Each render is
# CPU-heavy (JSX → SceneGraph + Yoga layout), and firing 10 in parallel from
# the ingestion phase's batched asyncio.gather causes httpx ReadTimeout on
# most of them — observed reproducibly in figma-mode bulk runs.  A small
# semaphore queues callers so each render gets the throughput it needs
# instead of every request starving the others.
_RENDER_SEM: asyncio.Semaphore | None = None
# 2 is the empirical sweet spot: 3 still produced sporadic
# "Unexpected end of JSON input" 500s from Bun (request-body reads getting
# cut under load), 1 serializes the bulk run too aggressively. Lower if you
# observe more flakes.
_RENDER_CONCURRENCY = 2


def _render_sem() -> asyncio.Semaphore:
    global _RENDER_SEM
    if _RENDER_SEM is None:
        _RENDER_SEM = asyncio.Semaphore(_RENDER_CONCURRENCY)
    return _RENDER_SEM


async def _render_jsx(jsx: str, *, name: str, width: int = 375, height: int = 812) -> dict[str, Any] | None:
    """Forward JSX to the open-pencil wireframe service. Sync httpx wrapped
    in a thread to avoid blocking the event loop. Concurrency-limited and
    transient-retry-aware so a Bun-side hiccup (request-body cut, slow
    parse, transient 5xx) doesn't surface to the LLM, which would otherwise
    give up the render in a single failed turn.
    """
    attempts = 3
    last_err: Exception | None = None
    for i in range(attempts):
        async with _render_sem():
            try:
                result = await asyncio.to_thread(
                    open_pencil_client.render_wireframe,
                    jsx=jsx,
                    name=name,
                    width=width,
                    height=height,
                )
            except Exception as e:
                last_err = e
                result = None
        if result and "nodes" in result:
            return result
        # Wait outside the semaphore so other renders can progress.
        if i < attempts - 1:
            await asyncio.sleep(0.5 * (2 ** i))  # 0.5s, 1s
    if last_err:
        SmartLogger.log(
            "WARN",
            f"_render_jsx exhausted retries for {name}: {last_err}",
            category="ai_design.wireframe.render.retries_exhausted",
            params={"name": name, "error": str(last_err)},
        )
    return None


# ─── Neo4j read/write ────────────────────────────────────────────────────


def _read_ui_node(ui_node_id: str) -> dict[str, Any] | None:
    """Read a UI node + its enclosing BC for prompt context."""
    with get_session() as session:
        rec = session.run(
            """
            MATCH (u:UI {id: $uid})
            OPTIONAL MATCH (bc:BoundedContext)-[:HAS_UI]->(u)
            RETURN u.id AS id,
                   coalesce(u.displayName, u.name) AS displayName,
                   u.name AS name,
                   u.description AS description,
                   bc.name AS bcName,
                   bc.description AS bcDescription
            LIMIT 1
            """,
            uid=ui_node_id,
        ).single()
    if not rec:
        return None
    return dict(rec)


def _save_scene_graph(ui_node_id: str, scene_graph: dict[str, Any]) -> None:
    """Persist sceneGraph (JSON string) on the UI node, matching what the
    existing browser path stores via `/api/graph/update-node`."""
    sg_str = json.dumps(scene_graph, ensure_ascii=False)
    with get_session() as session:
        session.run(
            """
            MATCH (u:UI {id: $uid})
            SET u.sceneGraph = $sg,
                u.designSource = 'backend',
                u.updatedAt = datetime()
            """,
            uid=ui_node_id,
            sg=sg_str,
        )


# ─── Agent loop ──────────────────────────────────────────────────────────


def _build_user_prompt(ui_node: dict[str, Any]) -> str:
    name = ui_node.get("displayName") or ui_node.get("name") or "Untitled"
    description = (ui_node.get("description") or "").strip() or "(설명 없음)"
    bc_name = ui_node.get("bcName")
    bc_desc = ui_node.get("bcDescription")
    bc_block = f"\nBoundedContext: {bc_name}" if bc_name else ""
    if bc_desc:
        bc_block += f"\nBC description: {bc_desc}"

    return (
        f"화면 이름: {name}\n"
        f"설명: {description}{bc_block}\n\n"
        "위 화면의 UI 와이어프레임을 한 번의 render 호출로 만들어 주세요. "
        "한국어 라벨을 사용하고, 너비 375px, 높이 hug 또는 적절한 px로 작성합니다."
    )


# ─── Reusable agent loop (no DB I/O, no SSE) ─────────────────────────────


async def run_render_agent(
    *,
    name: str,
    description: str = "",
    bc_name: str = "",
    bc_description: str = "",
    extra_context: str = "",
    on_event: callable = None,
) -> tuple[dict[str, Any] | None, str | None]:
    """Pure backend wireframe agent — no Neo4j read, no Neo4j write, no SSE.

    Used by:
      - the SSE endpoint (`stream_generate_wireframe`), which wraps this with
        DB read/write and event streaming;
      - the ingestion phase (`ui_wireframes`), which calls it inline when
        `session.ui_generation_mode == "figma"` and embeds the resulting
        sceneGraph into the UI node it's about to create.

    Returns (scene_graph, summary). `scene_graph` is the SerializedSceneGraph
    dict from the wireframe service, or None on failure. `summary` is the
    LLM's final assistant text, or None.

    `on_event` is an optional callback(event_name, data_dict) — the SSE wrapper
    uses this to forward per-step progress; the ingestion path passes None.
    """
    if not await asyncio.to_thread(open_pencil_client.is_available):
        if on_event:
            on_event("error", {"message": "Wireframe service (open-pencil)가 실행 중이 아닙니다."})
        return None, None

    try:
        llm = get_llm()
    except Exception as e:
        if on_event:
            on_event("error", {"message": f"LLM 설정 오류: {e}"})
        return None, None

    bound = llm.bind_tools([RENDER_TOOL, CALC_TOOL]) if hasattr(llm, "bind_tools") else llm

    ui_ctx = {
        "displayName": name,
        "description": description,
        "bcName": bc_name,
        "bcDescription": bc_description,
    }
    user_prompt = _build_user_prompt(ui_ctx)
    if extra_context:
        user_prompt += f"\n\n참고:\n{extra_context}"

    messages: list[Any] = [
        build_system_message(SYSTEM_PROMPT),
        HumanMessage(content=user_prompt),
    ]

    final_scene_graph: dict[str, Any] | None = None
    final_summary: str | None = None
    # Cache the most recent JSX the LLM tried to render. If the loop ends
    # without a successful render (LLM tends to summarize after a tool error
    # instead of retrying), we use this to do one last direct render attempt
    # below — no extra LLM round-trip needed since we already have valid JSX.
    last_jsx: str | None = None

    for step in range(MAX_AGENT_STEPS):
        if on_event:
            on_event("llm_step", {"step": step + 1, "of": MAX_AGENT_STEPS})

        try:
            ai_msg = await bound.ainvoke(messages)
        except Exception as e:
            SmartLogger.log("ERROR", f"ai_design.wireframe.llm_error: {e}", category="ai_design.wireframe.llm_error")
            if on_event:
                on_event("error", {"message": f"LLM 호출 실패: {e}"})
            return None, None

        messages.append(ai_msg)

        text = _msg_text(ai_msg)
        if text:
            final_summary = text

        tool_calls = getattr(ai_msg, "tool_calls", None) or []
        if not tool_calls:
            break

        for tc in tool_calls:
            tool_name = tc.get("name")
            tool_args = tc.get("args") or {}
            tc_id = tc.get("id") or ""

            if on_event:
                on_event("tool_call", {"name": tool_name, "args_preview": _short_repr(tool_args)})

            if tool_name == "render":
                jsx = tool_args.get("jsx") or ""
                if not jsx.strip():
                    err = "render 호출에 jsx 인자가 비어있습니다."
                    messages.append(ToolMessage(content=err, tool_call_id=tc_id))
                    if on_event:
                        on_event("tool_result", {"name": tool_name, "ok": False, "error": err})
                    continue
                last_jsx = jsx
                try:
                    sg = await _render_jsx(jsx, name=name)
                except Exception as e:
                    err = f"wireframe service 호출 실패: {e}"
                    messages.append(ToolMessage(content=err, tool_call_id=tc_id))
                    if on_event:
                        on_event("tool_result", {"name": tool_name, "ok": False, "error": err})
                    continue
                if not sg or "nodes" not in sg:
                    err = "wireframe service가 sceneGraph를 반환하지 않았습니다."
                    messages.append(ToolMessage(content=err, tool_call_id=tc_id))
                    if on_event:
                        on_event("tool_result", {"name": tool_name, "ok": False, "error": err})
                    continue
                final_scene_graph = sg
                node_count = len(sg.get("nodes") or {})
                summary = f"render 성공: {node_count}개 노드 생성됨."
                messages.append(ToolMessage(content=summary, tool_call_id=tc_id))
                if on_event:
                    on_event("tool_result", {"name": tool_name, "ok": True, "nodeCount": node_count})
                    on_event("render_progress", {"nodeCount": node_count})
            elif tool_name == "calc":
                expr = tool_args.get("expr") or ""
                try:
                    result = _safe_calc(expr)
                except Exception as e:
                    err = f"calc 실패: {e}"
                    messages.append(ToolMessage(content=err, tool_call_id=tc_id))
                    if on_event:
                        on_event("tool_result", {"name": tool_name, "ok": False, "error": err})
                    continue
                messages.append(ToolMessage(content=str(result), tool_call_id=tc_id))
                if on_event:
                    on_event("tool_result", {"name": tool_name, "ok": True, "value": result})
            else:
                err = f"알 수 없는 툴: {tool_name}"
                messages.append(ToolMessage(content=err, tool_call_id=tc_id))
                if on_event:
                    on_event("tool_result", {"name": tool_name, "ok": False, "error": err})

    # Final fallback: agent loop ended without a successful render but the LLM
    # did emit JSX at some point. Re-issue that JSX directly — no further LLM
    # round-trip needed. Handles the common pattern where the LLM follows up a
    # transient render error with a summary instead of retrying.
    if final_scene_graph is None and last_jsx:
        SmartLogger.log(
            "INFO",
            f"ai_design.wireframe.final_fallback name={name}",
            category="ai_design.wireframe.final_fallback",
            params={"name": name, "jsx_len": len(last_jsx)},
        )
        if on_event:
            on_event("final_fallback", {"reason": "agent_gave_up_after_render_error"})
        try:
            sg = await _render_jsx(last_jsx, name=name)
            if sg and "nodes" in sg:
                final_scene_graph = sg
                if on_event:
                    on_event("render_progress", {"nodeCount": len(sg.get("nodes") or {})})
        except Exception as e:
            SmartLogger.log(
                "WARN",
                f"ai_design.wireframe.final_fallback failed: {e}",
                category="ai_design.wireframe.final_fallback_failed",
                params={"name": name, "error": str(e)},
            )

    return final_scene_graph, final_summary


def _sse(event: str, data: dict[str, Any]) -> str:
    payload = json.dumps(data, ensure_ascii=False)
    return f"event: {event}\ndata: {payload}\n\n"


async def stream_generate_wireframe(
    ui_node_id: str,
) -> AsyncGenerator[str, None]:
    """SSE wrapper around `run_render_agent` for the Inspector "백엔드 AI로 생성"
    button. Reads the UI node from Neo4j → runs the agent → persists sceneGraph.
    """
    sess_id = uuid.uuid4().hex[:12]
    SmartLogger.log(
        "INFO",
        f"ai_design.wireframe.start ui_node_id={ui_node_id} sess={sess_id}",
        category="ai_design.wireframe.start",
        params={"ui_node_id": ui_node_id, "sess": sess_id},
    )

    ui_node = _read_ui_node(ui_node_id)
    if not ui_node:
        yield _sse("error", {"message": f"UI 노드 {ui_node_id}를 찾을 수 없습니다."})
        return

    yield _sse("context_loaded", {
        "uiNodeId": ui_node["id"],
        "displayName": ui_node.get("displayName"),
        "bcName": ui_node.get("bcName"),
    })

    # Buffer agent events into a queue we yield from. Required because the
    # callback is sync but we want to interleave with async work.
    event_buffer: list[tuple[str, dict]] = []

    def _capture(name: str, data: dict) -> None:
        event_buffer.append((name, data))

    scene_graph, final_summary = await run_render_agent(
        name=ui_node.get("displayName") or ui_node.get("name") or "Wireframe",
        description=ui_node.get("description") or "",
        bc_name=ui_node.get("bcName") or "",
        bc_description=ui_node.get("bcDescription") or "",
        on_event=_capture,
    )

    # Drain captured events to the SSE stream.
    for name, data in event_buffer:
        yield _sse(name, data)

    if not scene_graph:
        SmartLogger.log(
            "WARN",
            f"ai_design.wireframe.no_scene_graph ui_node_id={ui_node_id}",
            category="ai_design.wireframe.no_scene_graph",
        )
        # If the agent emitted an explicit error event, that's already in the
        # buffer; otherwise emit a generic one.
        if not any(n == "error" for n, _ in event_buffer):
            yield _sse("error", {"message": "LLM이 render 툴을 호출하지 않아 sceneGraph가 만들어지지 않았습니다."})
        return

    try:
        await asyncio.to_thread(_save_scene_graph, ui_node_id, scene_graph)
    except Exception as e:
        SmartLogger.log("ERROR", f"ai_design.wireframe.persist_failed: {e}", category="ai_design.wireframe.persist_failed")
        yield _sse("error", {"message": f"sceneGraph 저장 실패: {e}"})
        return

    node_count = len(scene_graph.get("nodes") or {})
    yield _sse("persist_done", {"uiNodeId": ui_node_id, "nodeCount": node_count})
    SmartLogger.log(
        "INFO",
        f"ai_design.wireframe.done ui_node_id={ui_node_id} nodes={node_count}",
        category="ai_design.wireframe.done",
        params={"ui_node_id": ui_node_id, "node_count": node_count},
    )
    yield _sse("done", {
        "uiNodeId": ui_node_id,
        "nodeCount": node_count,
        "summary": final_summary,
    })


# ─── helpers ─────────────────────────────────────────────────────────────


def _msg_text(msg: Any) -> str:
    """Extract plain text from a LangChain AIMessage, ignoring tool_use blocks."""
    content = getattr(msg, "content", None)
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        out: list[str] = []
        for block in content:
            if isinstance(block, dict) and block.get("type") in ("text", "text_delta"):
                t = block.get("text") or block.get("delta") or ""
                if isinstance(t, str):
                    out.append(t)
            elif isinstance(block, str):
                out.append(block)
        return "".join(out)
    return ""


def _short_repr(obj: Any, limit: int = 200) -> str:
    s = json.dumps(obj, ensure_ascii=False) if not isinstance(obj, str) else obj
    return s if len(s) <= limit else s[:limit] + "…"
