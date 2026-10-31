"""OpenAI 호환 /v1/chat/completions — 뒤에서 내 PC 의 Claude Code(`claude -p`)가 답한다.

## 왜 필요한가

레거시 분석기(robo-data-analyzer, Docker 안)는 LangChain ChatOpenAI 로 함수마다 LLM 을 부른다.
OpenAI 키가 없거나 만료되면 13장(레거시 코드 분석)이 통째로 멈춘다. Lite 는 프로포절 단계마다
이미 사용자의 Claude Code 구독을 쓰므로(platform/skill_runner), 분석기도 같은 길로 보낸다.
분석기 쪽은 config yaml 하나(`llm/configs/claude_code_bridge.yaml`)로 이 주소를 가리킨다.

## 무엇을 흉내 내나

- 일반 호출: messages → 텍스트 답(`choices[0].message.content`).
- 구조화 출력: 분석기는 `with_structured_output(..., method="function_calling")` 이라
  요청에 tools 하나와 그것을 강제하는 tool_choice 가 온다. 그 스키마를 지시문에 넣어
  JSON 하나만 답하게 하고, 그 JSON 을 `tool_calls[0].function.arguments` 로 돌려준다.

## 안전

Claude 에게 **도구를 하나도 주지 않는다**(텍스트 생성만). 빈 임시 폴더에서 돌리고,
Anthropic 키 변수는 지운다(로컬 로그인 세션 사용 — skill_runner 와 같은 이유).
"""
from __future__ import annotations

import asyncio
import json
import os
import tempfile
import time
import uuid
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse

from api.platform.observability.smart_logger import SmartLogger
from api.platform.skill_runner import (
    _resolve_claude_bin,
    _run_process_sync,
    _skill_env,
    extract_json,
)

router = APIRouter(prefix="/api/llm-bridge/v1", tags=["llm-bridge"])

#: 동시에 띄우는 claude 수. 분석기는 함수마다 부르니 너무 많이 띄우면 PC 가 버겁다.
_CONCURRENCY = int(os.getenv("ROBO_LLM_BRIDGE_CONCURRENCY", "4"))
_SEM = asyncio.Semaphore(_CONCURRENCY)
#: 호출 한 번의 상한(초).
_TIMEOUT = int(os.getenv("ROBO_LLM_BRIDGE_TIMEOUT", "600"))
#: config 의 model 이 "claude-code" 면 이 모델을 쓴다(빈 값이면 CLI 기본).
_DEFAULT_MODEL = os.getenv("ROBO_LLM_BRIDGE_MODEL", "sonnet")
#: 텍스트 생성만 — 파일 · 셸 · 웹 도구는 모두 막는다.
_NO_TOOLS = ["Bash", "Read", "Write", "Edit", "MultiEdit", "Glob", "Grep", "WebFetch",
             "WebSearch", "NotebookEdit", "Task", "TodoWrite"]


def _content_text(content: Any) -> str:
    """OpenAI message.content — 문자열이거나 [{type:text,text}] 목록."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(p.get("text", "") for p in content if isinstance(p, dict))
    return "" if content is None else str(content)


def _forced_tool(body: dict) -> dict | None:
    """요청이 함수 하나를 강제하면 그 함수 정의를 돌려준다."""
    tools = body.get("tools") or []
    if not tools:
        return None
    choice = body.get("tool_choice")
    name = None
    if isinstance(choice, dict):
        name = (choice.get("function") or {}).get("name")
    for tool in tools:
        fn = tool.get("function") or {}
        if name is None or fn.get("name") == name:
            return fn
    return None


def build_prompt(body: dict) -> tuple[str, str, dict | None]:
    """(system, user prompt, 강제 함수) — 대화는 한 덩어리 글로 넘긴다."""
    system_parts: list[str] = []
    turns: list[str] = []
    for msg in body.get("messages") or []:
        role = msg.get("role")
        text = _content_text(msg.get("content"))
        if role == "system":
            system_parts.append(text)
        elif role == "assistant":
            turns.append(f"[assistant]\n{text}")
        elif role == "tool":
            turns.append(f"[tool result]\n{text}")
        else:
            turns.append(text if len(body.get("messages") or []) <= 2 else f"[user]\n{text}")
    fn = _forced_tool(body)
    if fn:
        schema = json.dumps(fn.get("parameters") or {}, ensure_ascii=False)
        turns.append(
            "Answer by calling the function below. Output ONLY one JSON object with the "
            "function's arguments — it must validate against this JSON Schema. No prose, "
            f"no code fences.\nfunction: {fn.get('name')}\nschema: {schema}"
        )
    return "\n\n".join(system_parts), "\n\n".join(turns), fn


def _claude_cmd(system: str, model: str) -> list[str]:
    cmd = [_resolve_claude_bin(), "-p", "--output-format", "json", "--max-turns", "1",
           "--disallowedTools", *_NO_TOOLS]
    use = _DEFAULT_MODEL if model in ("", "claude-code") else model
    if use:
        cmd += ["--model", use]
    if system:
        cmd += ["--append-system-prompt", system]
    return cmd


async def _ask_claude(system: str, prompt: str, model: str) -> str:
    async with _SEM:
        with tempfile.TemporaryDirectory(prefix="llm-bridge-") as cwd:
            proc = await asyncio.to_thread(
                _run_process_sync, _claude_cmd(system, model), cwd, _TIMEOUT,
                prompt.encode("utf-8"),
            )
    if proc.returncode != 0:
        raise HTTPException(status_code=502, detail=f"claude exited {proc.returncode}: "
                            f"{(proc.stderr or b'')[-400:].decode('utf-8', 'replace')}")
    raw = (proc.stdout or b"").decode("utf-8", "replace")
    try:
        envelope = json.loads(raw)
    except json.JSONDecodeError:
        return raw.strip()
    if envelope.get("is_error"):
        raise HTTPException(status_code=502, detail=f"claude error: {str(envelope.get('result'))[:400]}")
    return str(envelope.get("result") or "")


def completion_response(model: str, text: str, fn: dict | None) -> dict:
    """OpenAI chat.completion 모양으로 감싼다."""
    message: dict[str, Any] = {"role": "assistant", "content": text}
    finish = "stop"
    if fn:
        args = extract_json(text)
        if not isinstance(args, dict):
            raise HTTPException(status_code=502, detail="claude did not return a JSON object for the tool call")
        message = {"role": "assistant", "content": None, "tool_calls": [{
            "id": f"call_{uuid.uuid4().hex[:24]}", "type": "function",
            "function": {"name": fn.get("name"), "arguments": json.dumps(args, ensure_ascii=False)},
        }]}
        finish = "tool_calls"
    return {
        "id": f"chatcmpl-{uuid.uuid4().hex[:24]}", "object": "chat.completion",
        "created": int(time.time()), "model": model or "claude-code",
        "choices": [{"index": 0, "message": message, "finish_reason": finish}],
        "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
    }


def stream_chunks(full: dict, include_usage: bool):
    """완성된 응답을 OpenAI SSE 조각으로 — 분석기는 반복 감시 때문에 stream=True(stream_usage)로 부른다.
    claude -p 는 한 번에 답하므로 내용 한 조각 + 끝 조각(+ 사용량) + [DONE]."""
    base = {"id": full["id"], "object": "chat.completion.chunk", "created": full["created"], "model": full["model"]}
    choice = full["choices"][0]
    msg = choice["message"]
    delta: dict[str, Any] = {"role": "assistant", "content": msg.get("content")}
    if msg.get("tool_calls"):
        delta["tool_calls"] = [{"index": i, **tc} for i, tc in enumerate(msg["tool_calls"])]
    yield f"data: {json.dumps({**base, 'choices': [{'index': 0, 'delta': delta, 'finish_reason': None}]}, ensure_ascii=False)}\n\n"
    yield f"data: {json.dumps({**base, 'choices': [{'index': 0, 'delta': {}, 'finish_reason': choice['finish_reason']}]})}\n\n"
    if include_usage:
        yield f"data: {json.dumps({**base, 'choices': [], 'usage': full['usage']})}\n\n"
    yield "data: [DONE]\n\n"


@router.post("/chat/completions")
async def chat_completions(request: Request):
    body = await request.json()
    model = str(body.get("model") or "")
    system, prompt, fn = build_prompt(body)
    started = time.monotonic()
    text = await _ask_claude(system, prompt, model)
    SmartLogger.log("INFO", "LLM bridge answered via Claude Code.", category="api.llm_bridge.done",
                    params={"model": model, "tool": (fn or {}).get("name"), "seconds": round(time.monotonic() - started, 1),
                            "prompt_chars": len(prompt), "stream": bool(body.get("stream"))})
    full = completion_response(model, text, fn)
    if body.get("stream"):
        include_usage = bool((body.get("stream_options") or {}).get("include_usage"))
        return StreamingResponse(stream_chunks(full, include_usage), media_type="text/event-stream")
    return full


@router.get("/models")
async def models() -> dict:
    return {"object": "list", "data": [{"id": "claude-code", "object": "model", "owned_by": "local"}]}
