"""사용자별 생성 모델 선택(X-LLM-Model) — 2026-11-16."""

import asyncio

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.platform import llm_model_choice as choice
from api.platform.env import get_chat_model, get_llm_model


@pytest.fixture(autouse=True)
def _models(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    monkeypatch.setenv("LLM_MODEL", "gpt-4.1")
    monkeypatch.delenv("OPENAI_MODEL", raising=False)
    monkeypatch.delenv("CHAT_MODEL", raising=False)

    async def fake_list(*, force=False):
        return ["gpt-4.1", "gpt-4o", "o3-mini"], None

    monkeypatch.setattr(choice, "list_models", fake_list)


def test_parse_models_drops_non_chat_and_sorts():
    payload = {"data": [{"id": "text-embedding-3-small"}, {"id": "gpt-4o"}, {"id": "whisper-1"},
                        {"id": "gpt-4.1"}, {"id": "gpt-4o"}, {"id": "tts-1"}, {"id": "dall-e-3"}]}
    assert choice._parse_models(payload) == ["gpt-4.1", "gpt-4o"]


def test_accept_only_listed_names():
    assert asyncio.run(choice.accept("gpt-4o")) == "gpt-4o"
    assert asyncio.run(choice.accept("evil-model")) is None
    assert asyncio.run(choice.accept("gpt-4.1")) is None      # 기본값과 같으면 덮지 않는다
    assert asyncio.run(choice.accept("")) is None


def test_accept_when_list_unavailable(monkeypatch):
    async def broken(*, force=False):
        return None, "HTTP 500"

    monkeypatch.setattr(choice, "list_models", broken)
    assert asyncio.run(choice.accept("gpt-4o")) is None       # 목록을 모르면 기본값으로


def test_getters_follow_selection(monkeypatch):
    token = choice.set_selected_model("gpt-4o")
    try:
        assert get_llm_model() == "gpt-4o"
        assert get_chat_model() == "gpt-4o"
        monkeypatch.setenv("LLM_PROVIDER", "anthropic")
        assert get_llm_model() == "gpt-4.1"                   # openai 가 아니면 쓰지 않는다
    finally:
        choice._SELECTED.reset(token)
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    assert get_llm_model() == "gpt-4.1"


def _app():
    app = FastAPI()
    seen: dict = {}

    @app.get("/probe")
    async def probe():
        seen["endpoint"] = get_llm_model()

        async def later():
            await asyncio.sleep(0)
            return get_llm_model()

        seen["task"] = await asyncio.create_task(later())    # ingestion 처럼 요청 안에서 만든 작업
        return seen

    app.add_middleware(choice.LlmModelChoiceMiddleware)
    return TestClient(app)


def test_middleware_passes_choice_to_endpoint_and_tasks():
    client = _app()
    assert client.get("/probe", headers={"X-LLM-Model": "gpt-4o"}).json() == {"endpoint": "gpt-4o", "task": "gpt-4o"}
    assert client.get("/probe", headers={"X-LLM-Model": "nope"}).json() == {"endpoint": "gpt-4.1", "task": "gpt-4.1"}
    assert client.get("/probe").json() == {"endpoint": "gpt-4.1", "task": "gpt-4.1"}
    assert choice.selected_model() is None                    # 요청 밖으로 새지 않는다


def test_resolve_model_in_llm_factory():
    from api.platform.llm import _resolve_model

    token = choice.set_selected_model("o3-mini")
    try:
        assert _resolve_model("openai", None) == "o3-mini"
        assert _resolve_model("openai", "gpt-4.1") == "gpt-4.1"   # 호출부가 이름을 박았으면 그것
    finally:
        choice._SELECTED.reset(token)
