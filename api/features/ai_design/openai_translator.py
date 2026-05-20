"""Translate between OpenAI Chat Completions wire format and LangChain message
objects, including streaming chunk → OpenAI delta conversion.

Goal: be tolerant of provider quirks. LangChain normalizes tool calls into
either `tool_call_chunks` (preferred for streaming) or `tool_calls` (fully
formed). Content can be a string OR a list of content blocks (Anthropic).
"""

from __future__ import annotations

import json
from typing import Any, Iterable

from langchain_core.messages import (
    AIMessage,
    AIMessageChunk,
    BaseMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)


# ─── OpenAI request → LangChain ────────────────────────────────────────────


def openai_messages_to_langchain(messages: list[dict[str, Any]]) -> list[BaseMessage]:
    """Convert an OpenAI-shaped `messages` array into LangChain BaseMessage list.

    Supports:
      - role=system | user | assistant | tool
      - assistant.tool_calls (list of {id, type, function: {name, arguments}})
      - role=tool with tool_call_id
    """
    out: list[BaseMessage] = []
    for m in messages or []:
        role = m.get("role")
        content = m.get("content") or ""

        if role == "system":
            out.append(SystemMessage(content=_content_to_text(content)))
        elif role == "user":
            out.append(HumanMessage(content=_content_to_text(content)))
        elif role == "assistant":
            tool_calls_in = m.get("tool_calls") or []
            tool_calls = []
            for tc in tool_calls_in:
                func = tc.get("function") or {}
                args_raw = func.get("arguments") or "{}"
                try:
                    args = json.loads(args_raw) if isinstance(args_raw, str) else args_raw
                except Exception:
                    args = {}
                tool_calls.append({
                    "id": tc.get("id") or "",
                    "name": func.get("name") or "",
                    "args": args,
                    "type": "tool_call",
                })
            out.append(AIMessage(
                content=_content_to_text(content),
                tool_calls=tool_calls,
            ))
        elif role == "tool":
            out.append(ToolMessage(
                content=_content_to_text(content),
                tool_call_id=m.get("tool_call_id") or "",
            ))
        # silently drop unknown roles — OpenAI also tolerates this
    return out


def openai_tools_to_langchain(tools: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    """Convert OpenAI tools array into the dict form `bind_tools` accepts.

    OpenAI shape: [{type: "function", function: {name, description, parameters}}]
    LangChain `bind_tools` accepts dicts with {name, description, parameters}.
    """
    if not tools:
        return []
    out: list[dict[str, Any]] = []
    for t in tools:
        fn = t.get("function") or {}
        if not fn.get("name"):
            continue
        out.append({
            "name": fn["name"],
            "description": fn.get("description") or "",
            "parameters": fn.get("parameters") or {"type": "object", "properties": {}},
        })
    return out


def _content_to_text(content: Any) -> str:
    """Flatten OpenAI/Anthropic-style content blocks into plain text."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict):
                if block.get("type") == "text" and isinstance(block.get("text"), str):
                    parts.append(block["text"])
        return "".join(parts)
    return ""


# ─── LangChain chunk → OpenAI delta ────────────────────────────────────────


def chunk_to_openai_delta(chunk: AIMessageChunk) -> dict[str, Any] | None:
    """Convert a single AIMessageChunk to an OpenAI Chat Completions delta dict.

    Returns None if the chunk has no payload to emit (LangChain sometimes
    yields empty chunks at start/end).
    """
    delta: dict[str, Any] = {}

    # Content (text)
    text = _extract_text_from_chunk_content(chunk.content)
    if text:
        delta["content"] = text

    # Tool call chunks (streaming partials). LangChain normalizes most
    # providers into this shape: list of {name?, args?, id?, index?}.
    tcc = getattr(chunk, "tool_call_chunks", None) or []
    if tcc:
        out_calls: list[dict[str, Any]] = []
        for i, item in enumerate(tcc):
            idx = item.get("index", i) if isinstance(item, dict) else i
            entry: dict[str, Any] = {"index": idx}
            if isinstance(item, dict):
                if item.get("id"):
                    entry["id"] = item["id"]
                    entry["type"] = "function"
                fn: dict[str, Any] = {}
                if item.get("name"):
                    fn["name"] = item["name"]
                if item.get("args") is not None:
                    # `args` in tool_call_chunks may be a string fragment OR a dict
                    fn["arguments"] = (
                        item["args"] if isinstance(item["args"], str)
                        else json.dumps(item["args"], ensure_ascii=False)
                    )
                if fn:
                    entry["function"] = fn
            out_calls.append(entry)
        delta["tool_calls"] = out_calls

    if not delta:
        return None
    return delta


def _extract_text_from_chunk_content(content: Any) -> str:
    """AIMessageChunk.content may be a string OR a list of content blocks
    (Anthropic returns blocks). We extract textual parts only — tool_use
    blocks are surfaced via tool_call_chunks instead.
    """
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict):
                btype = block.get("type")
                if btype in ("text", "text_delta"):
                    val = block.get("text") or block.get("delta") or ""
                    if isinstance(val, str):
                        parts.append(val)
        return "".join(parts)
    return ""


def langchain_finish_reason(chunk: AIMessageChunk | None) -> str | None:
    """Best-effort finish_reason extraction from chunk metadata.
    Returns OpenAI-style strings: 'stop' | 'tool_calls' | 'length' | None.
    """
    if chunk is None:
        return None
    meta = getattr(chunk, "response_metadata", None) or {}
    fr = meta.get("finish_reason") or meta.get("stop_reason")
    if not fr:
        return None
    if fr in ("end_turn", "stop", "stop_sequence"):
        return "stop"
    if fr in ("tool_use", "tool_calls", "function_call"):
        return "tool_calls"
    if fr in ("max_tokens", "length"):
        return "length"
    return "stop"
