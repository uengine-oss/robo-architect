"""Tests for the in-memory pending-clarification flag tracker (030)."""

from __future__ import annotations

import pytest

from api.features.requirements.clarification_agent import clarification_flags as flags
from api.features.requirements.clarification_contracts import (
    AmbiguityCategory,
    ClarificationQuestionDTO,
    QuestionType,
)


def _q(qid: str, ref_ids: list[str], category: AmbiguityCategory) -> ClarificationQuestionDTO:
    return ClarificationQuestionDTO(
        questionId=qid,
        category=category,
        questionType=QuestionType.short_answer,
        questionText="?",
        referencedRequirementIds=ref_ids,
    )


@pytest.fixture(autouse=True)
def _isolate(monkeypatch):
    monkeypatch.setattr(flags, "_FLAGS", {})
    yield


def test_record_flags_marks_every_referenced_user_story() -> None:
    flags.record_flags(
        session_id="s-1",
        scope_type="bounded_context",
        scope_id="bc-x",
        questions=[
            _q("q-1", ["us-a", "us-b"], AmbiguityCategory.non_functional),
            _q("q-2", ["us-b"], AmbiguityCategory.edge_cases),
        ],
    )
    snap = flags.snapshot()
    assert set(snap.keys()) == {"us-a", "us-b"}
    assert snap["us-a"].questionIds == ["q-1"]
    # us-b is touched by two questions in the same session — merged.
    assert set(snap["us-b"].questionIds) == {"q-1", "q-2"}
    assert set(snap["us-b"].categories) == {"non_functional", "edge_cases"}


def test_record_skips_empty_questions() -> None:
    flags.record_flags(
        session_id="s-1", scope_type="project", scope_id="*", questions=[]
    )
    assert flags.snapshot() == {}


def test_clear_flag_drops_one_user_story() -> None:
    flags.record_flags(
        session_id="s-1", scope_type="project", scope_id="*",
        questions=[_q("q-1", ["us-a"], AmbiguityCategory.functional_scope)],
    )
    flags.record_flags(
        session_id="s-1", scope_type="project", scope_id="*",
        questions=[_q("q-2", ["us-b"], AmbiguityCategory.functional_scope)],
    )
    flags.clear_flag("us-a")
    snap = flags.snapshot()
    assert "us-a" not in snap
    assert "us-b" in snap


def test_clear_session_flags_drops_only_that_session() -> None:
    flags.record_flags(
        session_id="s-1", scope_type="project", scope_id="*",
        questions=[_q("q-1", ["us-a"], AmbiguityCategory.functional_scope)],
    )
    flags.record_flags(
        session_id="s-2", scope_type="project", scope_id="*",
        questions=[_q("q-2", ["us-b"], AmbiguityCategory.functional_scope)],
    )
    flags.clear_session_flags("s-1")
    snap = flags.snapshot()
    assert "us-a" not in snap
    assert snap["us-b"].sessionId == "s-2"


def test_dict_questions_also_accepted() -> None:
    # The route layer may also pass already-serialized dicts.
    flags.record_flags(
        session_id="s-1",
        scope_type="user_story",
        scope_id="us-a",
        questions=[
            {
                "questionId": "q-raw",
                "category": "edge_cases",
                "referencedRequirementIds": ["us-a"],
            }
        ],
    )
    snap = flags.snapshot()
    assert snap["us-a"].questionIds == ["q-raw"]
    assert snap["us-a"].categories == ["edge_cases"]
