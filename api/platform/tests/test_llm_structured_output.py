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
        llm.with_structured_output(_Result)

    assert structured.call_args.kwargs["method"] == "function_calling"
    # 진단을 위해 안에서는 raw 를 함께 받는다(llm_structured_diag.wrap_structured).
    assert structured.call_args.kwargs["include_raw"] is True


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
        llm.with_structured_output(_Result, method="json_schema")

    assert structured.call_args.kwargs["method"] == "json_schema"
