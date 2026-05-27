"""Answer encoder (030).

A focused `get_llm().with_structured_output(...)` call that converts the
user's final answer to a clarification question into a concrete
`RequirementEditProposal`. Replaces — does not duplicate — invalidated
requirement text (FR-008). Returns `needsDisambiguation=true` when the
answer is uninterpretable (FR-007).

This is intentionally a single-step structured-output call (research R4):
encoding is narrow and benefits from schema enforcement, while the deep
agent is reserved for the open-ended ambiguity scan.
"""

from __future__ import annotations

from typing import Any, Optional

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from api.features.ingestion.ingestion_llm_runtime import get_llm
from api.features.requirements.clarification_contracts import (
    AnswerRequest,
    ClarificationQuestionDTO,
    QuestionType,
    RequirementEdit,
    RequirementEditProposal,
    UserStorySnapshot,
)
from api.platform.observability.smart_logger import SmartLogger

_SYSTEM_PROMPT = (
    "You encode a user's clarification answer back into the affected user "
    "stories. For each affected requirement, return its full `after` snapshot "
    "(role/action/benefit/priority/status/acceptanceCriteria) with the "
    "answer's resolution applied. Replace — do not duplicate — text the "
    "answer invalidates. Preserve the original intent and unrelated text. If "
    "the answer cannot be interpreted, set `needsDisambiguation=true` and "
    "provide a short Korean re-prompt; otherwise leave it false and return "
    "the edits."
)


class _LLMEdit(BaseModel):
    requirementId: str
    after: UserStorySnapshot
    fieldsSummary: str = ""


class _LLMProposal(BaseModel):
    edits: list[_LLMEdit] = Field(default_factory=list)
    needsDisambiguation: bool = False
    disambiguationPrompt: Optional[str] = None


def normalize_final_answer(
    question: ClarificationQuestionDTO, req: AnswerRequest
) -> str:
    """Convert an `AnswerRequest` into the canonical final-answer string.

    Returns an empty string when the answer cannot be normalized (caller
    should treat as `needsDisambiguation`).
    """
    if req.mode == "skip":
        return "(skip)"
    if req.mode == "recommended":
        return (question.recommendedAnswer or "").strip()
    if req.mode == "option":
        if question.questionType != QuestionType.closed or not req.optionKey:
            return ""
        for opt in question.options:
            if opt.key == req.optionKey:
                return opt.label
        return ""
    if req.mode == "free_text":
        text = (req.text or "").strip()
        if not text:
            return ""
        # Spec FR-005: free-form answers are short (≤5 words).
        words = text.split()
        if len(words) > 5:
            text = " ".join(words[:5])
        return text
    return ""


def _requirements_section(requirements: list[dict[str, Any]]) -> str:
    lines: list[str] = []
    for r in requirements:
        snap: UserStorySnapshot = r["snapshot"]
        ac = "; ".join(snap.acceptanceCriteria) if snap.acceptanceCriteria else "(none)"
        lines.append(
            f"- id={r['id']}\n"
            f"  role: {snap.role}\n"
            f"  action: {snap.action}\n"
            f"  benefit: {snap.benefit}\n"
            f"  priority: {snap.priority}; status: {snap.status}\n"
            f"  acceptanceCriteria: {ac}"
        )
    return "\n".join(lines)


def encode_answer(
    *,
    question: ClarificationQuestionDTO,
    final_answer: str,
    requirements: list[dict[str, Any]],
) -> RequirementEditProposal:
    """Encode the user's final answer into a `RequirementEditProposal`."""
    if not requirements:
        return RequirementEditProposal(
            questionId=question.questionId,
            finalAnswer=final_answer,
            edits=[],
            needsDisambiguation=False,
        )

    by_id: dict[str, UserStorySnapshot] = {r["id"]: r["snapshot"] for r in requirements}
    prompt = (
        f"# Question (category={question.category.value})\n{question.questionText}\n\n"
        f"# User's final answer\n{final_answer}\n\n"
        f"# Affected requirements ({len(requirements)})\n"
        f"{_requirements_section(requirements)}\n\n"
        "Return one `after` snapshot per affected requirement. Keep the "
        "structure even when the answer leaves a field unchanged — the diff "
        "is computed against the snapshot above."
    )

    try:
        structured = get_llm().with_structured_output(_LLMProposal)
        raw: _LLMProposal = structured.invoke(
            [SystemMessage(content=_SYSTEM_PROMPT), HumanMessage(content=prompt)]
        )
    except Exception as exc:  # noqa: BLE001
        SmartLogger.log(
            "ERROR",
            f"Answer encoder LLM failed: {exc}",
            category="requirements.clarification.encoder_error",
            params={"question_id": question.questionId, "error": str(exc)},
        )
        return RequirementEditProposal(
            questionId=question.questionId,
            finalAnswer=final_answer,
            edits=[],
            needsDisambiguation=True,
            disambiguationPrompt="답변 인코딩 중 오류가 발생했습니다. 다시 입력해 주세요.",
        )

    if raw.needsDisambiguation:
        return RequirementEditProposal(
            questionId=question.questionId,
            finalAnswer=final_answer,
            edits=[],
            needsDisambiguation=True,
            disambiguationPrompt=(
                raw.disambiguationPrompt or "답변을 더 구체적으로 설명해 주세요."
            ),
        )

    edits: list[RequirementEdit] = []
    for raw_edit in raw.edits:
        before = by_id.get(raw_edit.requirementId)
        if before is None:
            # Drop edits whose target isn't in scope.
            continue
        # Sanitize: keep field types stable and drop empty-after-strip ACs.
        after = UserStorySnapshot(
            role=(raw_edit.after.role or before.role).strip() or before.role,
            action=(raw_edit.after.action or before.action).strip() or before.action,
            benefit=(raw_edit.after.benefit or "").strip(),
            priority=raw_edit.after.priority or before.priority,
            status=raw_edit.after.status or before.status,
            acceptanceCriteria=[
                s.strip() for s in (raw_edit.after.acceptanceCriteria or []) if s and s.strip()
            ],
        )
        edits.append(
            RequirementEdit(
                requirementId=raw_edit.requirementId,
                baseUpdatedAt=None,  # caller stamps after structured-output return
                before=before,
                after=after,
                fieldsSummary=(raw_edit.fieldsSummary or "").strip(),
            )
        )

    if not edits:
        return RequirementEditProposal(
            questionId=question.questionId,
            finalAnswer=final_answer,
            edits=[],
            needsDisambiguation=True,
            disambiguationPrompt="이 답변을 영향받는 요구사항에 적용할 수 없습니다. 답변을 다시 입력해 주세요.",
        )

    return RequirementEditProposal(
        questionId=question.questionId,
        finalAnswer=final_answer,
        edits=edits,
        needsDisambiguation=False,
    )
