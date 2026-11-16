"""구조화 출력 진단 — 펜스 · 앞뒤 설명 · 잘림 · 정상 · 스키마 불일치 · 요청 거절.

가짜 응답을 `ChatOpenAI._generate` 에 꽂아 **langchain 의 실제 tool 파서**를
지나게 한다. 각 경우에서 (1) 갈래가 맞게 기록되는지 (2) 감싸지 않은 원래
`include_raw=False` 동작과 결과가 같은지(살린 경우 하나만 예외)를 본다.
"""

from __future__ import annotations

import asyncio
from unittest.mock import patch

import pytest
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_openai import ChatOpenAI
from pydantic import BaseModel

from api.platform import llm_structured_diag as diag
from api.platform.llm import get_llm
from api.platform.observability.smart_logger import SmartLogger


class Story(BaseModel):
    id: str
    action: str


class StoryList(BaseModel):
    user_stories: list[Story]


GOOD = {"user_stories": [{"id": "US-001", "action": "도서를 검색한다"}]}
GOOD_JSON = '{"user_stories": [{"id": "US-001", "action": "도서를 검색한다"}]}'


@pytest.fixture
def llm(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    monkeypatch.setenv("LLM_MODEL", "gpt-4.1")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.delenv("PGPT_BASE_URL", raising=False)
    return get_llm(max_tokens=8000)


@pytest.fixture
def logs():
    seen: list[tuple] = []

    def obs(level, message, category, params):
        if category and category.startswith(diag.CATEGORY_PREFIX):
            seen.append((level, category, params))

    SmartLogger.add_observer(obs)
    yield seen
    SmartLogger.remove_observer(obs)


def _reply(msg: AIMessage):
    def _gen(self, messages, stop=None, run_manager=None, **kwargs):
        return ChatResult(generations=[ChatGeneration(message=msg)])

    return patch.object(ChatOpenAI, "_generate", _gen)


def _tool_msg(args: dict, finish="tool_calls") -> AIMessage:
    return AIMessage(
        content="",
        tool_calls=[{"name": "StoryList", "args": args, "id": "call_1", "type": "tool_call"}],
        response_metadata={"finish_reason": finish, "model_name": "gpt-4.1"},
    )


def _outcome(fn):
    try:
        return ("ok", fn())
    except Exception as e:  # noqa: BLE001
        return ("raise", type(e))


def _both(llm, msg):
    """(감싼 결과, 원래 결과)."""
    inp = [HumanMessage(content="x")]
    with _reply(msg):
        wrapped = _outcome(lambda: llm.with_structured_output(StoryList).invoke(inp))
        original = _outcome(
            lambda: ChatOpenAI.with_structured_output(
                llm, StoryList, method="function_calling", include_raw=False
            ).invoke(inp)
        )
    return wrapped, original


# --- 정상 -------------------------------------------------------------------
def test_normal_tool_call_passes_through_silently(llm, logs):
    wrapped, original = _both(llm, _tool_msg(GOOD))
    assert wrapped == original
    assert wrapped[0] == "ok" and wrapped[1].user_stories[0].id == "US-001"
    assert logs == []


def test_async_path_same(llm, logs):
    msg = _tool_msg(GOOD)

    async def _agen(self, messages, stop=None, run_manager=None, **kwargs):
        return ChatResult(generations=[ChatGeneration(message=msg)])

    with patch.object(ChatOpenAI, "_agenerate", _agen):
        got = asyncio.run(llm.with_structured_output(StoryList).ainvoke([HumanMessage(content="x")]))
    assert got.user_stories[0].action == "도서를 검색한다"
    assert logs == []


# --- 가: tools 를 버리고 본문으로 답함 + 나: 펜스 / 앞뒤 설명 ------------------
@pytest.mark.parametrize(
    "content",
    [
        f"```json\n{GOOD_JSON}\n```",
        f"다음은 결과입니다:\n```json\n{GOOD_JSON}\n```\n이상입니다.",
        f"요청하신 User Story 입니다. {GOOD_JSON} 확인 부탁드립니다.",
        GOOD_JSON,
    ],
    ids=["fence", "fence+prose", "prose-no-fence", "bare-content"],
)
def test_content_only_json_is_recovered_and_logged(llm, logs, content):
    msg = AIMessage(content=content, response_metadata={"finish_reason": "stop"})
    wrapped, original = _both(llm, msg)
    assert original == ("ok", None)  # 예전: None → 호출부가 AttributeError
    assert wrapped[0] == "ok" and wrapped[1] == StoryList.model_validate(GOOD)
    assert len(logs) == 1
    level, category, params = logs[0]
    assert level == "ERROR"
    assert category == "llm.structured_output.recovered"
    assert params["branch"] == "가" and params["kind"] == "tool_ignored"
    assert params["stage"] == "StoryList" and params["method"] == "function_calling"
    assert params["response"]["tool_calls"] == 0
    assert params["response"]["finish_reason"] == "stop"
    assert params["max_tokens"] == 8000


def test_content_only_unrelated_json_is_not_recovered(llm, logs):
    msg = AIMessage(content='설명: {"foo": 1}', response_metadata={"finish_reason": "stop"})
    wrapped, original = _both(llm, msg)
    assert wrapped == original == ("ok", None)
    assert logs[0][1] == "llm.structured_output.parse_failed"
    assert logs[0][2]["kind"] == "tool_ignored"


# --- 다: 잘림 -----------------------------------------------------------------
def test_truncated_content_is_not_recovered(llm, logs):
    cut = GOOD_JSON[:-12]
    msg = AIMessage(content=f"```json\n{cut}", response_metadata={"finish_reason": "length"})
    wrapped, original = _both(llm, msg)
    assert wrapped == original
    _lvl, category, params = logs[0]
    assert category == "llm.structured_output.parse_failed"
    assert params["branch"] == "다" and params["kind"] == "truncated"
    assert params["response"]["content"]["len"] == len(cut) + len("```json\n")


def test_truncated_tool_args_logged_as_truncated(llm, logs):
    msg = AIMessage(
        content="",
        invalid_tool_calls=[{
            "name": "StoryList", "args": GOOD_JSON[:-12], "id": "call_1",
            "error": "Function StoryList arguments are not valid JSON", "type": "invalid_tool_call",
        }],
        response_metadata={"finish_reason": "length"},
    )
    wrapped, original = _both(llm, msg)
    assert wrapped == original
    params = logs[0][2]
    assert params["branch"] == "다" and params["kind"] == "truncated"
    assert params["response"]["invalid_tool_calls"] == 1
    assert params["response"]["invalid_args"]["len"] == len(GOOD_JSON) - 12


def test_fenced_tool_args_classified_as_fence(llm, logs):
    msg = AIMessage(
        content="",
        invalid_tool_calls=[{
            "name": "StoryList", "args": f"```json\n{GOOD_JSON}\n```", "id": "c",
            "error": "not valid JSON", "type": "invalid_tool_call",
        }],
        response_metadata={"finish_reason": "tool_calls"},
    )
    wrapped, original = _both(llm, msg)
    assert wrapped == original
    assert logs[0][2]["branch"] == "나" and logs[0][2]["kind"] == "fenced_tool_args"


# --- 라: 필드 이름·형이 다름 -----------------------------------------------------
def test_schema_mismatch_raises_same_and_logs_locations(llm, logs):
    msg = _tool_msg({"userStories": [{"id": "US-001", "action": "x"}]})
    wrapped, original = _both(llm, msg)
    assert wrapped == original and wrapped[0] == "raise"
    params = logs[0][2]
    assert params["branch"] == "라" and params["kind"] == "schema_mismatch"
    assert any(v["loc"] == "user_stories" for v in params["validation_errors"])


# --- 가: 프록시가 요청을 거절 ----------------------------------------------------
class _BadRequest(Exception):
    status_code = 400


def test_request_rejected_is_logged_and_reraised(llm, logs):
    def _gen(self, messages, stop=None, run_manager=None, **kwargs):
        raise _BadRequest("Unrecognized request argument supplied: tools")

    with patch.object(ChatOpenAI, "_generate", _gen):
        with pytest.raises(_BadRequest):
            llm.with_structured_output(StoryList).invoke([HumanMessage(content="x")])
    _lvl, category, params = logs[0]
    assert category == "llm.structured_output.request_error"
    assert params["branch"] == "가" and params["kind"] == "request_rejected"
    assert params["status_code"] == 400


# --- 맥락 · 가리기 ----------------------------------------------------------------
def test_context_provider_adds_phase(llm, logs):
    diag.register_context_provider(lambda: {"phase": "user_stories"})
    try:
        _both(llm, AIMessage(content="no json", response_metadata={"finish_reason": "stop"}))
    finally:
        diag._context_providers[:] = [f for f in diag._context_providers if f.__name__ != "<lambda>"]
    assert logs[0][2]["phase"] == "user_stories"


def test_redact_masks_keys_and_personal_data():
    s = diag.redact("key sk-abcdefghijklmnop mail a.b@posco.com tel 010-1234-5678 Bearer abcdefghijk")
    assert "sk-abcdefghijklmnop" not in s and "posco.com" not in s and "1234-5678" not in s
    assert "abcdefghijk" not in s


def test_head_tail_cuts_long_text():
    ht = diag.head_tail("a" * 300 + "b" * 300)
    assert ht["len"] == 600 and ht["head"] == "a" * 200 and ht["tail"] == "b" * 200


# --- 공용 관용 파서 ----------------------------------------------------------------
@pytest.mark.parametrize(
    "text",
    [GOOD_JSON, f"```json\n{GOOD_JSON}\n```", f"```\n{GOOD_JSON}\n```",
     f"결과:\n```json\n{GOOD_JSON}\n```\n끝", f"결과는 {GOOD_JSON} 입니다"],
)
def test_parse_llm_json_tolerates_fence_and_prose(text):
    assert diag.parse_llm_json(text) == GOOD


def test_parse_llm_json_truncated_raises_original_error():
    import json

    with pytest.raises(json.JSONDecodeError):
        diag.parse_llm_json('{"a": [1, 2')


def test_explicit_include_raw_is_untouched(llm, logs):
    with _reply(_tool_msg(GOOD)):
        out = llm.with_structured_output(StoryList, include_raw=True).invoke([HumanMessage(content="x")])
    assert set(out) == {"raw", "parsed", "parsing_error"}
