from unittest.mock import patch

from pydantic import BaseModel

from api.platform.llm import get_llm


class _Result(BaseModel):
    value: str


def test_openai_structured_output_defaults_to_function_calling(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    monkeypatch.setenv("LLM_MODEL", "gpt-4.1")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")

    with patch(
        "langchain_openai.ChatOpenAI.with_structured_output",
        autospec=True,
        return_value="structured",
    ) as structured:
        llm = get_llm()
        assert llm.with_structured_output(_Result) == "structured"

    assert structured.call_args.kwargs["method"] == "function_calling"


def test_openai_structured_output_keeps_explicit_method(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    monkeypatch.setenv("LLM_MODEL", "gpt-4.1")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")

    with patch(
        "langchain_openai.ChatOpenAI.with_structured_output",
        autospec=True,
        return_value="structured",
    ) as structured:
        llm = get_llm()
        assert llm.with_structured_output(_Result, method="json_schema") == "structured"

    assert structured.call_args.kwargs["method"] == "json_schema"
