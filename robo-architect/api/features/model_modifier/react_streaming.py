from __future__ import annotations

import json
import time
from typing import Any, AsyncGenerator, Dict, List

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from api.platform.observability.request_logging import sha256_text, summarize_for_log
from api.platform.observability.smart_logger import SmartLogger

from .chat_runtime_settings import AI_AUDIT_LOG_ENABLED, AI_AUDIT_LOG_FULL_OUTPUT, OPENAI_API_KEY, OPENAI_MODEL
from .model_change_application import apply_change
from .react_prompt import REACT_SYSTEM_PROMPT
from .react_sections import extract_section
from .sse_events import format_sse_event


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

        llm = ChatOpenAI(
            model=OPENAI_MODEL,
            temperature=0.7,
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

For each change, also output a JSON block in this format:
```json
{{"action": "rename|update|create|delete|connect", "targetId": "...", "targetName": "...", "targetType": "...", "description": "...", "bcId": "BC-xxx"}}
```

For "connect" actions, include:
- "sourceId"
- "connectionType": "TRIGGERS" | "INVOKES" | "EMITS"
"""
        messages.append(HumanMessage(content=current_message))

        applied_changes: list[dict[str, Any]] = []
        buffer = ""
        raw_output = ""
        chunk_count = 0
        total_chars = 0
        json_blocks_seen = 0
        json_blocks_applied = 0
        json_decode_errors = 0

        if AI_AUDIT_LOG_ENABLED:
            SmartLogger.log(
                "INFO",
                "Chat modify: LLM call starting (streaming).",
                category="api.chat.llm.start",
                params={
                    "model": OPENAI_MODEL,
                    "temperature": 0.7,
                    "selected_nodes_count": len(selected_nodes),
                    "conversation_history_count": len(conversation_history),
                    "prompt": prompt,
                    "prompt_sha256": sha256_text(prompt),
                    "prompt_len": len(prompt),
                    "system_prompt_sha256": sha256_text(REACT_SYSTEM_PROMPT),
                    "system_prompt_len": len(REACT_SYSTEM_PROMPT),
                    "constructed_user_message": current_message,
                    "constructed_user_message_sha256": sha256_text(current_message),
                    "constructed_user_message_len": len(current_message),
                    "selected_nodes": summarize_for_log(selected_nodes),
                    "conversation_history_tail": summarize_for_log(conversation_history[-5:]),
                },
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
                        params={"first_token_ms": first_token_ms, "model": OPENAI_MODEL},
                    )

            if "THOUGHT:" in buffer:
                thought = extract_section(buffer, "THOUGHT")
                if thought:
                    yield format_sse_event("thought", {"content": thought})

            if "ACTION:" in buffer:
                action_txt = extract_section(buffer, "ACTION")
                if action_txt:
                    yield format_sse_event("action", {"content": action_txt})

            if "OBSERVATION:" in buffer:
                obs = extract_section(buffer, "OBSERVATION")
                if obs:
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
                    t_apply0 = time.perf_counter()
                    applied = await apply_change(change)
                    apply_ms = int((time.perf_counter() - t_apply0) * 1000)
                    if applied:
                        applied_changes.append(change)
                        json_blocks_applied += 1
                        yield format_sse_event("change", {"change": change})
                    if AI_AUDIT_LOG_ENABLED:
                        SmartLogger.log(
                            "INFO",
                            "Chat modify: change block processed.",
                            category="api.chat.change.block",
                            params={
                                "applied": applied,
                                "apply_ms": apply_ms,
                                "change": summarize_for_log(change),
                            },
                        )
                except json.JSONDecodeError:
                    json_decode_errors += 1
                    pass
                buffer = buffer[: buffer.find("```json")] + buffer[end + 3 :]

            yield format_sse_event("content", {"content": chunk.content})

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
                        "applied": json_blocks_applied,
                        "json_decode_errors": json_decode_errors,
                    },
                    "applied_changes": summarize_for_log(applied_changes),
                    "raw_output": (raw_output if AI_AUDIT_LOG_FULL_OUTPUT else summarize_for_log(raw_output)),
                    "raw_output_sha256": sha256_text(raw_output),
                    "raw_output_len": len(raw_output),
                },
            )

        yield format_sse_event(
            "complete",
            {"summary": f"완료: {len(applied_changes)}개의 변경사항이 적용되었습니다.", "appliedChanges": applied_changes},
        )

    except Exception as e:
        if AI_AUDIT_LOG_ENABLED:
            SmartLogger.log(
                "ERROR",
                "Chat modify failed: exception during streaming.",
                category="api.chat.llm.error",
                params={"error": {"type": type(e).__name__, "message": str(e)}},
            )
        yield format_sse_event("error", {"message": str(e)})


