"""Tests for the answer encoder (030 — T024).

The encoder is a single-step `get_llm().with_structured_output(...)` call,
so these tests stub `get_llm()` to return a chain whose `invoke()` returns
a pre-baked `_LLMProposal`. The contract under test is the wrapper logic
around that call: answer normalization (FR-005/FR-006), invalidated-text
replacement (FR-008), and the `needsDisambiguation` re-prompt path (FR-007).
"""

from __future__ import annotations

from unittest import mock

from api.features.requirements.clarification_agent import answer_encoder as enc
from api.features.requirements.clarification_contracts import (
    AmbiguityCategory,
    AnswerRequest,
    ClarificationQuestionDTO,
    QuestionOption,
    QuestionType,
    UserStorySnapshot,
)


def _question(
    *,
    qtype: QuestionType = QuestionType.closed,
    options: list[QuestionOption] | None = None,
    recommended: str = "기본 추천",
    text: str = "이 요구사항을 어떻게 명확히 할까?",
) -> ClarificationQuestionDTO:
    return ClarificationQuestionDTO(
        questionId="q-1",
        category=AmbiguityCategory.non_functional,
        questionType=qtype,
        questionText=text,
        referencedRequirementIds=["us-1"],
        recommendedAnswer=recommended,
        options=options or [
            QuestionOption(key="a", label="p95 < 1s"),
            QuestionOption(key="b", label="p95 < 3s"),
        ],
    )


def _snapshot(action: str = "주문을 빠르게 검색", criteria: list[str] | None = None) -> UserStorySnapshot:
    return UserStorySnapshot(
        role="고객",
        action=action,
        benefit="더 좋은 UX",
        priority="medium",
        status="draft",
        acceptanceCriteria=criteria or ["주문 검색 결과가 빠르게 표시된다"],
    )


# ── Answer normalization ────────────────────────────────────────────────


def test_normalize_recommended_returns_recommended_text() -> None:
    q = _question(recommended="  p95 < 1s  ")
    assert enc.normalize_final_answer(q, AnswerRequest(questionId="q-1", mode="recommended")) == "p95 < 1s"


def test_normalize_option_returns_option_label() -> None:
    q = _question()
    out = enc.normalize_final_answer(
        q, AnswerRequest(questionId="q-1", mode="option", optionKey="b")
    )
    assert out == "p95 < 3s"


def test_normalize_option_unknown_key_returns_empty() -> None:
    q = _question()
    out = enc.normalize_final_answer(
        q, AnswerRequest(questionId="q-1", mode="option", optionKey="zzz")
    )
    assert out == ""


def test_normalize_free_text_caps_at_five_words() -> None:
    q = _question(qtype=QuestionType.short_answer, options=[])
    out = enc.normalize_final_answer(
        q,
        AnswerRequest(
            questionId="q-1", mode="free_text", text="아주 빠르고 정확하고 신뢰성 있는 검색 결과"
        ),
    )
    assert len(out.split()) == 5


def test_normalize_skip_returns_skip_marker() -> None:
    assert (
        enc.normalize_final_answer(_question(), AnswerRequest(questionId="q-1", mode="skip"))
        == "(skip)"
    )


def test_normalize_empty_free_text_returns_empty() -> None:
    q = _question(qtype=QuestionType.short_answer, options=[])
    out = enc.normalize_final_answer(
        q, AnswerRequest(questionId="q-1", mode="free_text", text="   ")
    )
    assert out == ""


# ── Encoder happy path: produces a valid before/after proposal ──────────


def test_encode_answer_produces_before_after_proposal() -> None:
    q = _question()
    before = _snapshot(action="주문을 빠르게 검색")
    llm_after = UserStorySnapshot(
        role="고객",
        action="주문을 p95 1초 이내에 검색",
        benefit="더 좋은 UX",
        priority="medium",
        status="draft",
        acceptanceCriteria=["주문 검색이 1초 이내에 응답한다"],
    )
    llm_proposal = enc._LLMProposal(
        edits=[enc._LLMEdit(requirementId="us-1", after=llm_after, fieldsSummary="action+ac")],
        needsDisambiguation=False,
    )

    chain = mock.MagicMock()
    chain.invoke.return_value = llm_proposal
    llm = mock.MagicMock()
    llm.with_structured_output.return_value = chain
    with mock.patch.object(enc, "get_llm", return_value=llm):
        proposal = enc.encode_answer(
            question=q,
            final_answer="p95 < 1s",
            requirements=[{"id": "us-1", "snapshot": before}],
        )

    assert proposal.questionId == "q-1"
    assert proposal.finalAnswer == "p95 < 1s"
    assert proposal.needsDisambiguation is False
    assert len(proposal.edits) == 1
    edit = proposal.edits[0]
    assert edit.requirementId == "us-1"
    assert edit.before == before
    # FR-008: the "after" snapshot must reflect the new measurable target —
    # not be a duplicate of the original text plus an addendum.
    assert "빠르게" not in edit.after.action, (
        "after.action must replace the vague 'fast' word, not duplicate it"
    )
    assert "1초" in edit.after.action


# ── FR-008: invalidated text replaced, not duplicated ──────────────────


def test_invalidated_text_replaced_not_duplicated() -> None:
    q = _question()
    before = _snapshot(
        action="가능한 한 빠르게 그리고 빠르게 주문을 검색",
        criteria=["빠르게 응답한다"],
    )
    llm_after = UserStorySnapshot(
        role="고객",
        action="주문을 p95 1초 이내에 검색",
        benefit=before.benefit,
        priority=before.priority,
        status=before.status,
        acceptanceCriteria=["p95 응답 시간이 1초 이내다"],
    )
    chain = mock.MagicMock()
    chain.invoke.return_value = enc._LLMProposal(
        edits=[enc._LLMEdit(requirementId="us-1", after=llm_after, fieldsSummary="action+ac")],
    )
    llm = mock.MagicMock()
    llm.with_structured_output.return_value = chain
    with mock.patch.object(enc, "get_llm", return_value=llm):
        proposal = enc.encode_answer(
            question=q,
            final_answer="p95 < 1s",
            requirements=[{"id": "us-1", "snapshot": before}],
        )

    after = proposal.edits[0].after
    # The vague word must be gone from both action and criteria.
    assert "빠르게" not in after.action
    assert all("빠르게" not in c for c in after.acceptanceCriteria)


# ── FR-007: uninterpretable answer → needsDisambiguation ───────────────


def test_uninterpretable_answer_returns_needs_disambiguation() -> None:
    q = _question()
    before = _snapshot()
    chain = mock.MagicMock()
    chain.invoke.return_value = enc._LLMProposal(
        edits=[],
        needsDisambiguation=True,
        disambiguationPrompt="구체적인 응답 시간 목표(예: p95 < 1s)를 알려주세요.",
    )
    llm = mock.MagicMock()
    llm.with_structured_output.return_value = chain
    with mock.patch.object(enc, "get_llm", return_value=llm):
        proposal = enc.encode_answer(
            question=q,
            final_answer="잘 모르겠음",
            requirements=[{"id": "us-1", "snapshot": before}],
        )

    assert proposal.needsDisambiguation is True
    assert proposal.edits == []
    assert proposal.disambiguationPrompt and "p95" in proposal.disambiguationPrompt


# ── Edits with no in-scope requirement are dropped ──────────────────────


def test_edits_referencing_unknown_requirement_dropped() -> None:
    q = _question()
    before = _snapshot()
    llm_proposal = enc._LLMProposal(
        edits=[
            enc._LLMEdit(requirementId="ghost", after=_snapshot()),  # unknown id
            enc._LLMEdit(
                requirementId="us-1",
                after=UserStorySnapshot(
                    role="고객", action="주문을 1초 이내 검색", benefit=before.benefit
                ),
            ),
        ],
    )
    chain = mock.MagicMock()
    chain.invoke.return_value = llm_proposal
    llm = mock.MagicMock()
    llm.with_structured_output.return_value = chain
    with mock.patch.object(enc, "get_llm", return_value=llm):
        proposal = enc.encode_answer(
            question=q,
            final_answer="p95 < 1s",
            requirements=[{"id": "us-1", "snapshot": before}],
        )

    assert [e.requirementId for e in proposal.edits] == ["us-1"]


# ── LLM exception → graceful needsDisambiguation ───────────────────────


def test_llm_failure_returns_needs_disambiguation() -> None:
    q = _question()
    before = _snapshot()
    chain = mock.MagicMock()
    chain.invoke.side_effect = RuntimeError("provider blew up")
    llm = mock.MagicMock()
    llm.with_structured_output.return_value = chain
    with mock.patch.object(enc, "get_llm", return_value=llm):
        proposal = enc.encode_answer(
            question=q,
            final_answer="rec",
            requirements=[{"id": "us-1", "snapshot": before}],
        )

    assert proposal.needsDisambiguation is True
    assert proposal.disambiguationPrompt
