"""Unit tests for api.platform.llm_messages (feature 031)."""

from __future__ import annotations

import pytest
from langchain_core.messages import SystemMessage

from api.platform.language import (
    ENV_DEFAULT_LANGUAGE_KEY,
    clear_request_language,
    set_request_language,
)
from api.platform.llm_messages import LANGUAGE_DIRECTIVE_TEMPLATE, build_system_message


@pytest.fixture(autouse=True)
def _isolate(monkeypatch):
    monkeypatch.delenv(ENV_DEFAULT_LANGUAGE_KEY, raising=False)
    clear_request_language()
    yield
    clear_request_language()


def test_returns_system_message_instance():
    msg = build_system_message("You are a DDD expert.")
    assert isinstance(msg, SystemMessage)


def test_user_content_preserved_verbatim_at_front():
    original = "You are a DDD expert analyzing user stories."
    msg = build_system_message(original)
    # The caller's content must appear unchanged at the very start
    assert msg.content.startswith(original)


def test_language_directive_appended_after_blank_line():
    set_request_language("ko-KR")
    msg = build_system_message("Caller instructions.")
    expected_directive = LANGUAGE_DIRECTIVE_TEMPLATE.format(tag="ko-KR")
    assert msg.content == f"Caller instructions.\n\n{expected_directive}"


def test_directive_uses_var_when_set():
    set_request_language("ja-JP")
    msg = build_system_message("X")
    assert "Respond in ja-JP" in msg.content


def test_directive_uses_env_when_var_unset(monkeypatch):
    monkeypatch.setenv(ENV_DEFAULT_LANGUAGE_KEY, "ko-KR")
    msg = build_system_message("X")
    assert "Respond in ko-KR" in msg.content


def test_directive_uses_hardcoded_fallback_when_nothing_set():
    msg = build_system_message("X")
    assert "Respond in en-US" in msg.content


def test_exotic_bcp47_tag_passed_through_verbatim():
    """Per FR-011: any well-formed BCP-47 tag is accepted unchanged."""
    set_request_language("af-ZA")
    msg = build_system_message("X")
    assert "Respond in af-ZA" in msg.content


def test_skip_directive_returns_plain_system_message():
    """Test-only escape hatch produces a deterministic byte-for-byte SystemMessage."""
    set_request_language("ko-KR")
    msg = build_system_message("Plain content.", _skip_language_directive=True)
    assert msg.content == "Plain content."
    # No directive injected
    assert "Respond in" not in msg.content


def test_multiple_calls_with_same_language_are_idempotent():
    set_request_language("en-US")
    a = build_system_message("Prompt.")
    b = build_system_message("Prompt.")
    assert a.content == b.content


def test_language_change_reflected_on_next_call():
    set_request_language("ko-KR")
    a = build_system_message("X")
    set_request_language("ja-JP")
    b = build_system_message("X")
    assert "ko-KR" in a.content
    assert "ja-JP" in b.content
