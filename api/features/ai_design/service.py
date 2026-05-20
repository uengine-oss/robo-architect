"""Service layer: stream OpenAI-compatible Chat Completions backed by the
project's LangChain LLM runtime (api/platform/llm.py).
"""

from __future__ import annotations

import json
import time
import uuid
from typing import Any, AsyncGenerator

from api.platform.env import get_llm_provider_model
from api.platform.llm import get_llm
from api.platform.observability.smart_logger import SmartLogger

from .openai_translator import (
    chunk_to_openai_delta,
    langchain_finish_reason,
    openai_messages_to_langchain,
    openai_tools_to_langchain,
)


def get_health() -> dict[str, Any]:
    """Backend self-check for the AI Design proxy.

    The frontend bootstrap is purely static and does NOT require this
    endpoint — it exists only for ops/debug visibility (e.g. "what model
    will requests actually be served by?"). Provider/model are exposed for
    operability, never the API key.
    """
    provider, model = get_llm_provider_model()
    return {
        "ok": True,
        "provider": provider,
        "model": model,
    }


async def stream_chat_completion(req: dict[str, Any]) -> AsyncGenerator[str, None]:
    """Async generator yielding OpenAI Chat Completions SSE lines.

    Wire format:
      data: {chunk JSON}\n\n
      ...
      data: [DONE]\n\n
    """
    chat_id = f"chatcmpl-{uuid.uuid4().hex[:24]}"
    created = int(time.time())

    messages_in = req.get("messages") or []
    tools_in = req.get("tools") or []
    requested_model = req.get("model") or "auto"
    temperature = req.get("temperature")
    max_tokens = req.get("max_tokens")

    SmartLogger.log(
        "INFO",
        f"ai_design.chat.start id={chat_id} msgs={len(messages_in)} tools={len(tools_in)}",
        category="ai_design.chat.start",
        params={"chat_id": chat_id, "requested_model": requested_model},
    )

    kwargs: dict[str, Any] = {}
    if temperature is not None:
        kwargs["temperature"] = float(temperature)
    if max_tokens is not None:
        # LangChain providers accept `max_tokens` (Anthropic) / `max_output_tokens` (Google) /
        # `max_completion_tokens` (newer OpenAI). Best-effort: use `max_tokens`.
        kwargs["max_tokens"] = int(max_tokens)

    try:
        llm = get_llm(**kwargs)
    except Exception as e:
        yield _error_chunk(chat_id, created, "configuration_error", str(e))
        yield "data: [DONE]\n\n"
        return

    bound = llm
    lc_tools = openai_tools_to_langchain(tools_in)
    if lc_tools and hasattr(llm, "bind_tools"):
        try:
            bound = llm.bind_tools(lc_tools)
        except Exception as e:
            SmartLogger.log(
                "WARN",
                f"ai_design.bind_tools_failed: {e}",
                category="ai_design.bind_tools",
            )

    try:
        lc_messages = openai_messages_to_langchain(messages_in)
    except Exception as e:
        yield _error_chunk(chat_id, created, "invalid_request", f"Failed to parse messages: {e}")
        yield "data: [DONE]\n\n"
        return

    last_chunk = None
    role_emitted = False
    try:
        async for chunk in bound.astream(lc_messages):
            last_chunk = chunk
            delta = chunk_to_openai_delta(chunk)
            if delta is None:
                continue
            # Emit role once on the first delta with payload.
            if not role_emitted:
                delta = {"role": "assistant", **delta}
                role_emitted = True
            yield _data_chunk(chat_id, created, requested_model, delta=delta)
    except Exception as e:
        SmartLogger.log(
            "ERROR",
            f"ai_design.chat.stream_error id={chat_id}: {e}",
            category="ai_design.chat.error",
            params={"chat_id": chat_id, "error": str(e)},
        )
        yield _error_chunk(chat_id, created, "upstream_error", str(e))
        yield "data: [DONE]\n\n"
        return

    finish_reason = langchain_finish_reason(last_chunk) or "stop"

    # Final chunk: empty delta + finish_reason.
    final = {
        "id": chat_id,
        "object": "chat.completion.chunk",
        "created": created,
        "model": requested_model,
        "choices": [{"index": 0, "delta": {}, "finish_reason": finish_reason}],
    }
    yield f"data: {json.dumps(final, ensure_ascii=False)}\n\n"
    yield "data: [DONE]\n\n"

    SmartLogger.log(
        "INFO",
        f"ai_design.chat.done id={chat_id} finish={finish_reason}",
        category="ai_design.chat.done",
        params={"chat_id": chat_id, "finish_reason": finish_reason},
    )


# ─── helpers ──────────────────────────────────────────────────────────────


def _data_chunk(
    chat_id: str,
    created: int,
    model: str,
    *,
    delta: dict[str, Any],
    finish_reason: str | None = None,
) -> str:
    body = {
        "id": chat_id,
        "object": "chat.completion.chunk",
        "created": created,
        "model": model,
        "choices": [{
            "index": 0,
            "delta": delta,
            "finish_reason": finish_reason,
        }],
    }
    return f"data: {json.dumps(body, ensure_ascii=False)}\n\n"


def _error_chunk(chat_id: str, created: int, code: str, message: str) -> str:
    """Emit a final-style error chunk in OpenAI-friendly shape, then [DONE]."""
    body = {
        "id": chat_id,
        "object": "chat.completion.chunk",
        "created": created,
        "model": "error",
        "choices": [{
            "index": 0,
            "delta": {"content": f"⚠️ {message}"},
            "finish_reason": "stop",
        }],
        "error": {"type": code, "message": message},
    }
    return f"data: {json.dumps(body, ensure_ascii=False)}\n\n"
