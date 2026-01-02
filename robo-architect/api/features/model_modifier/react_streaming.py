from __future__ import annotations

import json
import time
from typing import Any, AsyncGenerator, Dict, List

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from api.platform.llm import get_llm as get_platform_llm
from api.platform.neo4j import get_session
from api.platform.observability.smart_logger import SmartLogger

from .chat_runtime_settings import AI_AUDIT_LOG_ENABLED, OPENAI_API_KEY, OPENAI_MODEL
from .react_prompt import REACT_SYSTEM_PROMPT
from .react_sections import extract_section
from .sse_events import format_sse_event


def _gen_change_id() -> str:
    # Short, stable-enough for a single stream. Not cryptographic.
    return f"chg-{int(time.time() * 1000)}-{int(time.perf_counter() * 1000000) % 1000000}"


def _sanitize_updates(change: dict[str, Any]) -> dict[str, Any]:
    """
    Normalize legacy fields into `updates` for update/create actions.
    This keeps the system tolerant while we transition prompt formats.
    """
    updates = change.get("updates")
    if isinstance(updates, dict):
        return updates

    updates = {}
    for k in ["description", "template", "attachedToId", "attachedToType", "attachedToName"]:
        if k in change:
            updates[k] = change.get(k)
    return updates


def _selected_node_map(selected_nodes: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for n in selected_nodes or []:
        node_id = n.get("id")
        if node_id:
            out[str(node_id)] = n
    return out


def _fetch_node_snapshot(target_id: str) -> dict[str, Any] | None:
    """
    Fetch a minimal snapshot for confirm UI: current fields + labels.
    NOTE: sync neo4j call; acceptable at change-block granularity.
    """
    query = """
    MATCH (n {id: $id})
    RETURN labels(n) as labels,
           n.id as id,
           n.name as name,
           n.description as description,
           n.template as template,
           n.attachedToId as attachedToId,
           n.attachedToType as attachedToType,
           n.attachedToName as attachedToName
    """
    with get_session() as session:
        rec = session.run(query, id=target_id).single()
        if not rec:
            return None
        return {
            "labels": rec.get("labels") or [],
            "id": rec.get("id"),
            "name": rec.get("name"),
            "description": rec.get("description"),
            "template": rec.get("template"),
            "attachedToId": rec.get("attachedToId"),
            "attachedToType": rec.get("attachedToType"),
            "attachedToName": rec.get("attachedToName"),
        }


async def stream_react_response(
    prompt: str,
    selected_nodes: List[Dict[str, Any]],
    conversation_history: List[Dict[str, Any]],
) -> AsyncGenerator[str, None]:
    try:
        if not OPENAI_API_KEY:
            yield format_sse_event(
                "error",
                {"message": "OPENAI_API_KEY가 설정되지 않았습니다. 서버 환경변수를 설정해주세요."},
            )
            return

        t0 = time.perf_counter()
        first_token_ms: int | None = None

        llm = get_platform_llm(
            provider="openai",
            model=OPENAI_MODEL,
            streaming=True,
            api_key=OPENAI_API_KEY,
        )

        nodes_context = "\n".join(
            [
                f"- {node.get('type', 'Unknown')}: {node.get('name', node.get('id'))} "
                f"(ID: {node.get('id')}, BC: {node.get('bcId', 'N/A')})"
                for node in selected_nodes
            ]
        )

        messages = [SystemMessage(content=REACT_SYSTEM_PROMPT)]
        for msg in conversation_history[-5:]:
            if msg.get("type") == "user":
                messages.append(HumanMessage(content=msg.get("content", "")))
            elif msg.get("type") == "assistant":
                messages.append(AIMessage(content=msg.get("content", "")))

        current_message = f"""## Selected Nodes
{nodes_context}

## User Request
{prompt}

## Instructions
1. First, analyze what changes are needed (THOUGHT)
2. Then describe the specific actions to take (ACTION)
3. After each action, describe the result (OBSERVATION)
4. If changes cascade to other nodes, continue the ReAct loop
5. Finally, summarize all changes made

Format your response like this:
💭 THOUGHT: ...
⚡ ACTION: ...
👁️ OBSERVATION: ...
✅ SUMMARY: ...

For each proposed change, also output a JSON block (DRAFT ONLY) in this format:
```json
{{
  "changeId": "chg-...",
  "action": "rename|update|create|delete|connect",
  "targetId": "...",
  "targetType": "Command|Event|Policy|Aggregate|ReadModel|UI|BoundedContext",
  "targetName": "...",
  "bcId": "BC-xxx",
  "rationale": "why this change is necessary",
  "updates": {{
    "description": "...",
    "template": "<div class=\\"wf-root wf-theme-ant\\" data-wf-root=\\"1\\">...</div>",
    "attachedToId": "...",
    "attachedToType": "Command|ReadModel",
    "attachedToName": "..."
  }}
}}
```

Rules:
- For "update": put ALL property changes inside `updates` (field patch). Do not invent extra fields.
- For UI wireframes: `updates.template` MUST be a body-only HTML fragment (no markdown fences).
  - MUST NOT include: <!doctype>, <html>, <head>, <body>
  - MUST NOT include: <script>, inline event handlers (on*), javascript: URLs
  - MUST start with: <div class="wf-root wf-theme-ant|wf-theme-material" data-wf-root="1"> ... </div>
  - <style> is allowed ONLY if every selector is scoped under `.wf-root`, and it MUST NOT use @import or url(...)
  - Make it modern UI (Ant/Material): app bar, cards, table toolbar + pagination, form grid, tabs/segments, chips/badges, empty/loading/error placeholders
- For "rename": set `targetName` to the NEW name (and you may omit `updates`).

For "connect" actions, include:
- "sourceId"
- "connectionType": "TRIGGERS" | "INVOKES" | "EMITS"
"""
        messages.append(HumanMessage(content=current_message))

        selected_map = _selected_node_map(selected_nodes)

        draft_changes: list[dict[str, Any]] = []
        buffer = ""
        raw_output = ""
        chunk_count = 0
        total_chars = 0
        json_blocks_seen = 0
        json_decode_errors = 0

        # De-dup streaming events: only emit when section content actually changes.
        # Without this, the backend may re-emit THOUGHT/ACTION/OBSERVATION on every token,
        # and the frontend will keep appending trace lines.
        last_sent_thought: str | None = None
        last_sent_action: str | None = None
        last_sent_observation: str | None = None

        if AI_AUDIT_LOG_ENABLED:
            SmartLogger.log(
                "INFO",
                "Chat modify: LLM call starting (streaming).",
                category="api.chat.llm.start",
                params={
                    "model": OPENAI_MODEL,
                    "prompt": prompt,
                    "system_prompt": REACT_SYSTEM_PROMPT,
                    "constructed_user_message": current_message,
                    # Reproducibility: keep raw payloads (SmartLogger can offload to detail files).
                    "selected_nodes": selected_nodes,
                    "conversation_history": conversation_history,
                }
            )

        async for chunk in llm.astream(messages):
            if not chunk.content:
                continue

            buffer += chunk.content
            raw_output += chunk.content
            chunk_count += 1
            total_chars += len(chunk.content)

            if first_token_ms is None:
                first_token_ms = int((time.perf_counter() - t0) * 1000)
                if AI_AUDIT_LOG_ENABLED:
                    SmartLogger.log(
                        "INFO",
                        "Chat modify: first token received from LLM.",
                        category="api.chat.llm.first_token",
                        params={"first_token_ms": first_token_ms, "model": OPENAI_MODEL}
                    )

            if "THOUGHT:" in buffer:
                thought = extract_section(buffer, "THOUGHT")
                if thought and thought != last_sent_thought:
                    last_sent_thought = thought
                    yield format_sse_event("thought", {"content": thought})

            if "ACTION:" in buffer:
                action_txt = extract_section(buffer, "ACTION")
                if action_txt and action_txt != last_sent_action:
                    last_sent_action = action_txt
                    yield format_sse_event("action", {"content": action_txt})

            if "OBSERVATION:" in buffer:
                obs = extract_section(buffer, "OBSERVATION")
                if obs and obs != last_sent_observation:
                    last_sent_observation = obs
                    yield format_sse_event("observation", {"content": obs})

            while "```json" in buffer and "```" in buffer[buffer.find("```json") + 7 :]:
                start = buffer.find("```json") + 7
                end = buffer.find("```", start)
                if end <= start:
                    break
                json_str = buffer[start:end].strip()
                try:
                    json_blocks_seen += 1
                    change = json.loads(json_str)

                    # Normalize / enrich draft payload
                    if not change.get("changeId"):
                        change["changeId"] = _gen_change_id()

                    action = change.get("action")
                    if action in ("update", "create"):
                        change["updates"] = _sanitize_updates(change)

                    # Best-effort before/after for confirm UI
                    before: dict[str, Any] = {}
                    after: dict[str, Any] = {}
                    target_id = change.get("targetId")
                    if target_id:
                        # Prefer selected-nodes context for speed/consistency
                        src = selected_map.get(str(target_id))
                        if src:
                            for k in ["name", "description", "template", "attachedToId", "attachedToType", "attachedToName"]:
                                if k in src:
                                    before[k] = src.get(k)
                        else:
                            snap = _fetch_node_snapshot(str(target_id))
                            if snap:
                                for k in ["name", "description", "template", "attachedToId", "attachedToType", "attachedToName"]:
                                    before[k] = snap.get(k)

                    # Compute after from updates / rename targetName
                    if change.get("action") == "rename" and change.get("targetName") is not None:
                        after["name"] = change.get("targetName")
                    updates = change.get("updates") if isinstance(change.get("updates"), dict) else {}
                    for k, v in updates.items():
                        after[k] = v
                    change["before"] = before
                    change["after"] = after

                    draft_changes.append(change)
                    yield format_sse_event("draft_change", {"draft": change})
                    if AI_AUDIT_LOG_ENABLED:
                        SmartLogger.log(
                            "INFO",
                            "Chat modify: draft change block captured (not applied).",
                            category="api.chat.draft.block",
                            params={
                                "change": change,
                            }
                        )
                except json.JSONDecodeError:
                    json_decode_errors += 1
                    pass
                buffer = buffer[: buffer.find("```json")] + buffer[end + 3 :]

        total_ms = int((time.perf_counter() - t0) * 1000)
        if AI_AUDIT_LOG_ENABLED:
            SmartLogger.log(
                "INFO",
                "Chat modify: LLM streaming completed.",
                category="api.chat.llm.done",
                params={
                    "model": OPENAI_MODEL,
                    "duration_ms": total_ms,
                    "first_token_ms": first_token_ms,
                    "stream": {"chunks": chunk_count, "chars": total_chars},
                    "json_blocks": {
                        "seen": json_blocks_seen,
                        "json_decode_errors": json_decode_errors,
                    },
                    # Reproducibility: keep raw data.
                    "draft_changes": draft_changes,
                    "raw_output": raw_output,
                }
            )

        summary_section = extract_section(raw_output, "SUMMARY")
        final_summary = (
            summary_section
            if summary_section
            else f"제안 완료: {len(draft_changes)}개의 변경사항을 준비했습니다. 승인 후 적용됩니다."
        )

        yield format_sse_event(
            "draft_complete",
            {"summary": final_summary, "draftChanges": draft_changes},
        )

    except Exception as e:
        if AI_AUDIT_LOG_ENABLED:
            SmartLogger.log(
                "ERROR",
                "Chat modify failed: exception during streaming.",
                category="api.chat.llm.error",
                params={"error": {"type": type(e).__name__, "message": str(e)}}
            )
        yield format_sse_event("error", {"message": str(e)})


