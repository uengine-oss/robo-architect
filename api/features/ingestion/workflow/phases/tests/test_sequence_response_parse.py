"""User Story sequencing 응답 파싱 — 펜스 · 앞뒤 설명 · 잘림 · 정상."""

from __future__ import annotations

import json

import pytest
from langchain_core.messages import AIMessage

from api.features.ingestion.workflow.phases.user_story_sequencing import _parse_sequence_response
from api.platform.observability.smart_logger import SmartLogger

BODY = '{"US-001": 1, "US-002": "2"}'


@pytest.mark.parametrize(
    "content",
    [
        BODY,
        f"```json\n{BODY}\n```",
        f"순서는 다음과 같습니다.\n```json\n{BODY}\n```\n참고하세요.",
        f"순서: {BODY}",
    ],
    ids=["normal", "fence", "fence+prose", "prose"],
)
def test_tolerates_fence_and_prose(content):
    assert _parse_sequence_response(AIMessage(content=content)) == {"US-001": 1, "US-002": 2}


def test_truncated_raises_and_logs_branch():
    seen = []

    def obs(level, message, category, params):
        if category == "llm.structured_output.text_parse_failed":
            seen.append(params)

    SmartLogger.add_observer(obs)
    try:
        msg = AIMessage(content='{"US-001": 1, "US-0', response_metadata={"finish_reason": "length"})
        with pytest.raises(json.JSONDecodeError):
            _parse_sequence_response(msg)
    finally:
        SmartLogger.remove_observer(obs)
    assert seen and seen[0]["stage"] == "user_story_sequencing"
    assert seen[0]["branch"] == "다" and seen[0]["kind"] == "truncated"
