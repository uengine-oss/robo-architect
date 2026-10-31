"""LLM 다리(OpenAI 호환 → claude -p) — 도구 모드 판정, 대화 글, 답 해석, SSE 조각.

claude 를 실제로 부르지 않는다. 분석기의 세 가지 부름을 흉내 낸다:
구조화 출력(함수 하나 강제), 도구 에이전트(scan · residual — 고르게 함), 일반 글.
"""
import json

import pytest
from fastapi import HTTPException

from api.features.llm_bridge.router import build_prompt, completion_response, stream_chunks, tool_mode

LS = {"type": "function", "function": {"name": "ls", "description": "List a folder",
                                         "parameters": {"type": "object", "properties": {"path": {"type": "string"}}}}}
SUBMIT = {"type": "function", "function": {"name": "submit_scan", "description": "Submit the result",
                                             "parameters": {"type": "object", "properties": {"summary": {"type": "string"}}}}}


def test_tool_mode():
    assert tool_mode({"messages": []}) == ("text", [])
    assert tool_mode({"tools": [LS, SUBMIT], "tool_choice": "none"})[0] == "text"
    mode, fns = tool_mode({"tools": [LS, SUBMIT], "tool_choice": {"type": "function", "function": {"name": "submit_scan"}}})
    assert mode == "forced" and [f["name"] for f in fns] == ["submit_scan"]
    # 이름이 없거나 auto 면 첫 도구를 강제하지 않는다 — 고르게 한다
    assert tool_mode({"tools": [LS, SUBMIT]})[0] == "choose"
    assert tool_mode({"tools": [LS, SUBMIT], "tool_choice": "auto"})[0] == "choose"
    assert tool_mode({"tools": [LS, SUBMIT], "tool_choice": "required"})[0] == "required"


def test_prompt_keeps_tool_history():
    body = {"tools": [LS, SUBMIT], "messages": [
        {"role": "system", "content": "You scan projects."},
        {"role": "user", "content": "Scan it."},
        {"role": "assistant", "content": "", "tool_calls": [
            {"id": "call_1", "type": "function", "function": {"name": "ls", "arguments": "{\"path\": \"src\"}"}}]},
        {"role": "tool", "tool_call_id": "call_1", "content": "Main.java"},
    ]}
    system, prompt, mode, fns = build_prompt(body)
    assert system == "You scan projects."
    assert mode == "choose" and len(fns) == 2
    assert '"name": "ls"' in prompt and '"path": "src"' in prompt
    assert "[tool result: ls]\nMain.java" in prompt
    assert "- submit_scan: Submit the result" in prompt
    assert '{"content": ' in prompt   # choose 는 끝맺음 답을 허용한다
    assert '{"content": ' not in build_prompt({**body, "tool_choice": "required"})[1]


def test_choose_answers():
    fns = [LS["function"], SUBMIT["function"]]
    msg = completion_response("claude-code", '{"tool_calls": [{"name": "ls", "arguments": {"path": "."}}]}',
                              "choose", fns)["choices"][0]
    assert msg["finish_reason"] == "tool_calls"
    call = msg["message"]["tool_calls"][0]
    assert call["function"]["name"] == "ls" and json.loads(call["function"]["arguments"]) == {"path": "."}
    # 모르는 도구는 버리고, 끝맺음 답은 글로
    msg = completion_response("m", '{"content": "done"}', "choose", fns)["choices"][0]
    assert msg["finish_reason"] == "stop" and msg["message"]["content"] == "done"
    msg = completion_response("m", 'sure: {"name": "submit_scan", "arguments": {"summary": "x"}}', "choose", fns)
    assert msg["choices"][0]["message"]["tool_calls"][0]["function"]["name"] == "submit_scan"
    msg = completion_response("m", "no json here", "choose", fns)["choices"][0]
    assert msg["finish_reason"] == "stop" and msg["message"]["content"] == "no json here"


def test_forced_answer():
    out = completion_response("m", '```json\n{"summary": "adds"}\n```', "forced", [SUBMIT["function"]])
    call = out["choices"][0]["message"]["tool_calls"][0]
    assert call["function"]["name"] == "submit_scan" and json.loads(call["function"]["arguments"]) == {"summary": "adds"}
    with pytest.raises(HTTPException):
        completion_response("m", "no json", "forced", [SUBMIT["function"]])


def test_stream_chunks():
    full = completion_response("m", '{"tool_calls": [{"name": "ls", "arguments": {}}]}', "choose", [LS["function"]])
    events = list(stream_chunks(full, include_usage=True))
    assert events[-1] == "data: [DONE]\n\n"
    first = json.loads(events[0][6:])
    assert first["object"] == "chat.completion.chunk"
    assert first["choices"][0]["delta"]["tool_calls"][0]["index"] == 0
    assert json.loads(events[1][6:])["choices"][0]["finish_reason"] == "tool_calls"
    assert "usage" in json.loads(events[2][6:])


def test_json_response_format():
    rf = {"type": "json_schema", "json_schema": {"name": "TableDesc", "schema": {"type": "object", "properties": {"description": {"type": "string"}}}}}
    _, prompt, mode, _ = build_prompt({"messages": [{"role": "user", "content": "Describe table store."}], "response_format": rf})
    assert mode == "json" and '"description"' in prompt
    out = completion_response("m", 'Here it is:\n```json\n{"description": "가게"}\n```', "json")
    assert json.loads(out["choices"][0]["message"]["content"]) == {"description": "가게"}
    assert out["choices"][0]["finish_reason"] == "stop"
    with pytest.raises(HTTPException):
        completion_response("m", "no json", "json")
    # 도구가 있으면 도구 모드가 먼저
    assert build_prompt({"messages": [], "tools": [LS], "response_format": rf})[2] == "choose"


def test_english_mode_asks_for_english_values(monkeypatch):
    from api.platform.skill_runner import _with_output_language
    monkeypatch.setenv("ROBO_LANG", "en")
    assert "OUTPUT LANGUAGE: English" in _with_output_language("요약해 줘")
    monkeypatch.setenv("ROBO_LANG", "ko")
    assert _with_output_language("요약해 줘") == "요약해 줘"
