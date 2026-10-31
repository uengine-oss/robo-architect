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
- 도구 에이전트: scan · residual 같은 에이전트는 도구 여럿을 주고 고르게 한다(tool_choice
  auto · required). 도구 목록을 지시문에 넣고 `{"tool_calls": [...]}` 이나 `{"content": ...}`
  JSON 하나로 답하게 한다. 앞선 도구 호출과 그 결과도 대화 글에 넣는다.
- JSON 응답: response_format(json_schema · json_object)이 오면 스키마를 지시문에 넣고, 답에서 JSON 만
  골라 content 로 돌려준다(코드 펜스 · 설명이 섞여도).
- stream=true 면 완성된 답을 OpenAI SSE 조각으로 보낸다(분석기는 반복 감시 때문에 스트림으로 부른다).

## 안전

Claude 에게 **도구를 하나도 주지 않는다**(텍스트 생성만, MCP 서버도 없이). 빈 임시 폴더에서 돌리고,
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
#: 텍스트 생성만 — 내장 도구는 하나도 없이(--tools ""), 사용자 설정의 MCP 서버도 띄우지 않는다
#: (--strict-mcp-config, 설정 파일 없음). 도구가 하나라도 남으면 --max-turns 1 에서 도구를 부르려다
#: error_max_turns 로 끝난다(분석기 scan 에이전트가 「파일 읽기」 같은 말을 보고 실제 도구를 찾았다).
_TEXT_ONLY = ["--tools", "", "--strict-mcp-config"]


def _content_text(content: Any) -> str:
    """OpenAI message.content — 문자열이거나 [{type:text,text}] 목록."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(p.get("text", "") for p in content if isinstance(p, dict))
    return "" if content is None else str(content)


def tool_mode(body: dict) -> tuple[str, list[dict]]:
    """("text" | "forced" | "choose" | "required", 쓸 함수 정의들).

    forced = tool_choice 가 함수 하나를 이름으로 정했다(구조화 출력). choose = 도구를 쓸지
    말지 · 무엇을 쓸지 모델이 고른다. required = 도구 중 하나는 꼭 부른다.
    """
    fns = [t.get("function") or {} for t in body.get("tools") or [] if (t.get("function") or {}).get("name")]
    choice = body.get("tool_choice")
    if not fns or choice == "none":
        return "text", []
    if isinstance(choice, dict):
        name = (choice.get("function") or {}).get("name")
        picked = [f for f in fns if f.get("name") == name]
        return ("forced", picked) if picked else ("required", fns)
    if choice in ("required", "any"):
        return "required", fns
    return "choose", fns


def _tool_names(messages: list[dict]) -> dict[str, str]:
    """tool_call_id → 함수 이름 (도구 결과 앞에 무엇의 결과인지 적으려고)."""
    names: dict[str, str] = {}
    for msg in messages:
        for call in msg.get("tool_calls") or []:
            names[str(call.get("id"))] = (call.get("function") or {}).get("name") or "?"
    return names


def _calls_text(calls: list[dict]) -> str:
    out = []
    for call in calls:
        fn = call.get("function") or {}
        args = fn.get("arguments")
        try:
            args = json.loads(args) if isinstance(args, str) else args
        except json.JSONDecodeError:
            pass
        out.append({"name": fn.get("name"), "arguments": args})
    return json.dumps({"tool_calls": out}, ensure_ascii=False)


def _choose_directive(mode: str, fns: list[dict]) -> str:
    tools = "\n".join(
        f"- {f.get('name')}: {(f.get('description') or '').strip()}\n  parameters: "
        f"{json.dumps(f.get('parameters') or {}, ensure_ascii=False)}" for f in fns
    )
    answer = (
        "" if mode == "required" else
        ' — or, when no tool call is needed any more, {"content": "<your final answer>"}'
    )
    return (
        "You are one turn of a tool-using agent. Tools available to you:\n"
        f"{tools}\n\n"
        "Decide the next step. Output ONLY one JSON object: "
        '{"tool_calls": [{"name": "<tool name>", "arguments": {...}}]} to call one or more tools'
        f"{answer}. Arguments must validate against the tool's parameters schema. "
        "The tool results come back to you in the next turn. No prose, no code fences."
    )


def build_prompt(body: dict) -> tuple[str, str, str, list[dict]]:
    """(system, user prompt, 모드, 함수 정의들) — 대화는 한 덩어리 글로 넘긴다.
    모드: text · forced · choose · required(도구), json(response_format)."""
    messages = body.get("messages") or []
    names = _tool_names(messages)
    system_parts: list[str] = []
    turns: list[str] = []
    for msg in messages:
        role = msg.get("role")
        text = _content_text(msg.get("content"))
        if role == "system":
            system_parts.append(text)
        elif role == "assistant":
            calls = msg.get("tool_calls") or []
            body_text = "\n".join(x for x in (text, _calls_text(calls) if calls else "") if x)
            turns.append(f"[assistant]\n{body_text}")
        elif role == "tool":
            turns.append(f"[tool result: {names.get(str(msg.get('tool_call_id')), '?')}]\n{text}")
        else:
            turns.append(text if len(messages) <= 2 else f"[user]\n{text}")
    mode, fns = tool_mode(body)
    if mode == "forced":
        fn = fns[0]
        schema = json.dumps(fn.get("parameters") or {}, ensure_ascii=False)
        turns.append(
            "Answer by calling the function below. Output ONLY one JSON object with the "
            "function's arguments — it must validate against this JSON Schema. No prose, "
            f"no code fences.\nfunction: {fn.get('name')}\nschema: {schema}"
        )
    elif mode in ("choose", "required"):
        turns.append(_choose_directive(mode, fns))
    elif _json_format(body) is not None:
        mode = "json"
        schema = _json_format(body)
        turns.append(
            "Output ONLY one JSON object" + (
                f" that validates against this JSON Schema: {json.dumps(schema, ensure_ascii=False)}" if schema else ""
            ) + ". No prose, no code fences."
        )
    return "\n\n".join(system_parts), "\n\n".join(turns), mode, fns


def _json_format(body: dict) -> dict | None:
    """response_format 이 JSON 을 요구하면 그 스키마({} = 스키마 없는 json_object), 아니면 None.
    LangChain 의 기본 구조화 출력(method="json_schema")이 이 길로 온다 — SDK 가 content 를 바로 JSON 으로 읽는다."""
    rf = body.get("response_format")
    if not isinstance(rf, dict):
        return None
    if rf.get("type") == "json_schema":
        return (rf.get("json_schema") or {}).get("schema") or {}
    if rf.get("type") == "json_object":
        return {}
    return None


def _claude_cmd(system: str, model: str) -> list[str]:
    cmd = [_resolve_claude_bin(), "-p", "--output-format", "json", "--max-turns", "1", *_TEXT_ONLY]
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
    raw = (proc.stdout or b"").decode("utf-8", "replace")
    if proc.returncode != 0 and not raw.strip().startswith("{"):
        _fail(f"claude exited {proc.returncode}: {(proc.stderr or b'')[-400:].decode('utf-8', 'replace')}")
    try:
        envelope = json.loads(raw)
    except json.JSONDecodeError:
        return raw.strip()
    if envelope.get("is_error"):
        _fail(f"claude error ({envelope.get('subtype')}): {str(envelope.get('result'))[:400]}")
    return str(envelope.get("result") or "")


def _fail(detail: str) -> None:
    """분석기는 상태 코드만 남기므로 까닭은 여기 로그에 적는다."""
    SmartLogger.log("WARNING", "LLM bridge call failed.", category="api.llm_bridge.error", params={"detail": detail})
    raise HTTPException(status_code=502, detail=detail)


def _tool_call(name: str, args: Any) -> dict:
    return {"id": f"call_{uuid.uuid4().hex[:24]}", "type": "function",
            "function": {"name": name, "arguments": json.dumps(args if isinstance(args, dict) else {}, ensure_ascii=False)}}


def answer_message(text: str, mode: str, fns: list[dict]) -> tuple[dict, str]:
    """Claude 의 답 글 → (assistant message, finish_reason)."""
    if mode == "forced":
        args = extract_json(text)
        if not isinstance(args, dict):
            _fail(f"claude did not return a JSON object for the tool call: {text[:300]}")
        return {"role": "assistant", "content": None, "tool_calls": [_tool_call(fns[0].get("name"), args)]}, "tool_calls"
    if mode == "json":
        parsed = extract_json(text)
        if not isinstance(parsed, (dict, list)):
            _fail(f"claude did not return JSON for response_format: {text[:300]}")
        return {"role": "assistant", "content": json.dumps(parsed, ensure_ascii=False)}, "stop"
    if mode in ("choose", "required"):
        known = {f.get("name") for f in fns}
        parsed = extract_json(text)
        if isinstance(parsed, dict):
            calls = [c for c in parsed.get("tool_calls") or [] if isinstance(c, dict) and c.get("name") in known]
            if calls:
                return {"role": "assistant", "content": None,
                        "tool_calls": [_tool_call(c["name"], c.get("arguments")) for c in calls]}, "tool_calls"
            if isinstance(parsed.get("content"), str):
                return {"role": "assistant", "content": parsed["content"]}, "stop"
            # {"name": ..., "arguments": ...} 하나만 답한 경우
            if parsed.get("name") in known:
                return {"role": "assistant", "content": None,
                        "tool_calls": [_tool_call(parsed["name"], parsed.get("arguments"))]}, "tool_calls"
    return {"role": "assistant", "content": text}, "stop"


def completion_response(model: str, text: str, mode: str = "text", fns: list[dict] | None = None) -> dict:
    """OpenAI chat.completion 모양으로 감싼다."""
    message, finish = answer_message(text, mode, fns or [])
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
    system, prompt, mode, fns = build_prompt(body)
    started = time.monotonic()
    text = await _ask_claude(system, prompt, model)
    full = completion_response(model, text, mode, fns)
    msg = full["choices"][0]["message"]
    SmartLogger.log("INFO", "LLM bridge answered via Claude Code.", category="api.llm_bridge.done",
                    params={"model": model, "mode": mode, "tools": len(fns),
                            "called": [c["function"]["name"] for c in msg.get("tool_calls") or []],
                            "seconds": round(time.monotonic() - started, 1),
                            "prompt_chars": len(prompt), "stream": bool(body.get("stream"))})
    if body.get("stream"):
        include_usage = bool((body.get("stream_options") or {}).get("include_usage"))
        return StreamingResponse(stream_chunks(full, include_usage), media_type="text/event-stream")
    return full


@router.get("/models")
async def models() -> dict:
    return {"object": "list", "data": [{"id": "claude-code", "object": "model", "owned_by": "local"}]}
