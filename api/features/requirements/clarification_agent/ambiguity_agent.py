"""Deep-agent ambiguity scan (030).

Wraps the LangChain `deepagents` runtime with the SpecKit clarify methodology
(see `clarify_methodology.DEEP_AGENT_INSTRUCTIONS`) and a single terminal
tool `submit_clarification_questions` whose schema equals `QuestionQueue`.

External interface:
    run_ambiguity_scan(requirements, *, on_progress) -> QuestionQueue

`requirements` is the list of in-scope UserStory snapshots; `on_progress`
receives `ClarificationProgressEvent`s for the SSE channel.

Provider-agnostic: the agent receives its chat model from `get_llm()`
(spec 030 plan §Constitution VI).
"""

from __future__ import annotations

import uuid
from typing import Any, Callable, Optional

from pydantic import BaseModel, Field

from api.features.ingestion.ingestion_llm_runtime import get_llm
from api.features.requirements.clarification_agent.clarify_methodology import (
    DEEP_AGENT_INSTRUCTIONS,
    MAX_OPTIONS_PER_CLOSED_QUESTION,
    MAX_QUESTIONS_PER_SESSION,
    MIN_OPTIONS_PER_CLOSED_QUESTION,
)
from api.features.requirements.clarification_contracts import (
    AmbiguityCategory,
    ClarificationProgressEvent,
    ClarificationQuestionDTO,
    CoverageRow,
    CoverageStatus,
    QuestionOption,
    QuestionStatus,
    QuestionType,
)
from api.platform.observability.smart_logger import SmartLogger

# ── Public DTOs ──────────────────────────────────────────────────────────


class RequirementForScan(BaseModel):
    id: str
    role: str = ""
    action: str = ""
    benefit: str = ""
    priority: str = "medium"
    status: str = "draft"
    acceptanceCriteria: list[str] = Field(default_factory=list)


class QuestionQueue(BaseModel):
    questions: list[ClarificationQuestionDTO] = Field(default_factory=list)
    noAmbiguities: bool = False
    deferredNote: Optional[str] = None
    coverage: list[CoverageRow] = Field(default_factory=list)


# ── Helpers ──────────────────────────────────────────────────────────────


def _emit(on_progress: Optional[Callable], event: ClarificationProgressEvent) -> None:
    if on_progress is None:
        return
    try:
        on_progress(event)
    except Exception as exc:  # noqa: BLE001
        SmartLogger.log(
            "WARN",
            f"on_progress callback raised: {exc}",
            category="requirements.clarification.on_progress_error",
            params={"error": str(exc)},
        )


def _requirements_section(requirements: list[RequirementForScan]) -> str:
    lines: list[str] = []
    for r in requirements:
        ac = "; ".join(r.acceptanceCriteria) if r.acceptanceCriteria else "(none)"
        lines.append(
            f"- id={r.id}\n"
            f"  role: {r.role}\n"
            f"  action: {r.action}\n"
            f"  benefit: {r.benefit}\n"
            f"  priority: {r.priority}; status: {r.status}\n"
            f"  acceptanceCriteria: {ac}"
        )
    return "\n".join(lines) if lines else "(empty scope)"


def _normalize_questions(
    raw_questions: list[dict[str, Any]],
    *,
    valid_requirement_ids: set[str],
) -> list[ClarificationQuestionDTO]:
    """Enforce the contract invariants on whatever the LLM returned."""
    normalized: list[ClarificationQuestionDTO] = []
    for raw in raw_questions[:MAX_QUESTIONS_PER_SESSION]:
        try:
            category_value = raw.get("category") or "functional_scope"
            try:
                category = AmbiguityCategory(category_value)
            except ValueError:
                category = AmbiguityCategory.functional_scope

            question_type_value = (raw.get("questionType") or "closed").lower()
            if question_type_value not in ("closed", "short_answer"):
                question_type_value = "closed"
            question_type = QuestionType(question_type_value)

            referenced = [
                rid
                for rid in (raw.get("referencedRequirementIds") or [])
                if rid in valid_requirement_ids
            ]
            if not referenced:
                # Drop questions whose anchor requirement isn't in scope.
                continue

            options_raw = raw.get("options") or []
            options: list[QuestionOption] = []
            if question_type == QuestionType.closed:
                for o in options_raw[:MAX_OPTIONS_PER_CLOSED_QUESTION]:
                    if isinstance(o, dict) and o.get("label"):
                        options.append(
                            QuestionOption(
                                key=str(o.get("key") or o["label"])[:32],
                                label=str(o["label"]),
                            )
                        )
                if len(options) < MIN_OPTIONS_PER_CLOSED_QUESTION:
                    # Demote to short_answer if the LLM didn't supply enough
                    # mutually-exclusive choices.
                    question_type = QuestionType.short_answer
                    options = []

            normalized.append(
                ClarificationQuestionDTO(
                    questionId=str(raw.get("questionId") or uuid.uuid4()),
                    order=int(raw.get("order") or (len(normalized) + 1)),
                    category=category,
                    priority=int(raw.get("priority") or (len(normalized) + 1)),
                    questionType=question_type,
                    questionText=str(raw.get("questionText") or "").strip(),
                    referencedRequirementIds=referenced,
                    recommendedAnswer=str(raw.get("recommendedAnswer") or "").strip(),
                    options=options,
                    status=QuestionStatus.pending,
                )
            )
        except Exception as exc:  # noqa: BLE001
            SmartLogger.log(
                "WARN",
                f"Skipping malformed clarification question: {exc}",
                category="requirements.clarification.question_malformed",
                params={"raw": raw, "error": str(exc)},
            )
            continue
    return normalized


def _normalize_coverage(raw_coverage: list[dict[str, Any]]) -> list[CoverageRow]:
    rows: list[CoverageRow] = []
    seen: set[AmbiguityCategory] = set()
    for raw in raw_coverage or []:
        try:
            cat = AmbiguityCategory(raw.get("category"))
        except (ValueError, TypeError):
            continue
        if cat in seen:
            continue
        try:
            status = CoverageStatus(raw.get("status") or "outstanding")
        except ValueError:
            status = CoverageStatus.outstanding
        rows.append(CoverageRow(category=cat, status=status))
        seen.add(cat)
    # Ensure every category appears.
    for cat in AmbiguityCategory:
        if cat not in seen:
            rows.append(CoverageRow(category=cat, status=CoverageStatus.outstanding))
    return rows


# ── Core entrypoint ──────────────────────────────────────────────────────


def run_ambiguity_scan(
    requirements: list[RequirementForScan],
    *,
    on_progress: Optional[Callable[[ClarificationProgressEvent], None]] = None,
) -> QuestionQueue:
    """Run the deep-agent ambiguity scan and return a `QuestionQueue`.

    Never raises for LLM-side failures: callers translate exceptions into a
    session `status=failed` via SSE `error` events (FR-013). Caller is
    responsible for catching exceptions raised by `deepagents` import or
    runtime errors and converting them into the failed-session signal.
    """
    if not requirements:
        return QuestionQueue(
            questions=[],
            noAmbiguities=True,
            deferredNote=None,
            coverage=_normalize_coverage([]),
        )

    _emit(
        on_progress,
        ClarificationProgressEvent(
            phase="loading_scope",
            message=f"{len(requirements)}개 요구사항 로드",
            progress=0.05,
            data={"requirementCount": len(requirements)},
        ),
    )

    valid_ids = {r.id for r in requirements}
    captured: dict[str, Any] = {}

    # The terminal tool — when the deep agent calls this, we capture the
    # arguments and return a sentinel ack so the agent loop terminates.
    from langchain_core.tools import tool

    @tool("submit_clarification_questions")
    def submit_clarification_questions(
        questions: list[dict[str, Any]],
        noAmbiguities: bool = False,
        deferredNote: Optional[str] = None,
        coverage: Optional[list[dict[str, Any]]] = None,
    ) -> str:
        """Submit the final clarification question queue (terminal tool)."""
        captured["questions"] = questions or []
        captured["noAmbiguities"] = bool(noAmbiguities)
        captured["deferredNote"] = deferredNote
        captured["coverage"] = coverage or []
        return "queue accepted"

    user_message = (
        "Scan the following extracted requirements and produce a prioritized "
        f"clarification question queue (≤ {MAX_QUESTIONS_PER_SESSION}). When "
        "your queue is final, call `submit_clarification_questions` exactly "
        "once with the structured payload — that ends the session.\n\n"
        f"# Requirements in scope ({len(requirements)})\n"
        f"{_requirements_section(requirements)}"
    )

    _emit(
        on_progress,
        ClarificationProgressEvent(
            phase="scanning",
            message="딥 에이전트 모호성 스캔 중...",
            progress=0.2,
            data={"requirementCount": len(requirements)},
        ),
    )

    try:
        from deepagents import create_deep_agent
    except ImportError as exc:
        SmartLogger.log(
            "ERROR",
            "deepagents package is not installed — cannot run ambiguity scan",
            category="requirements.clarification.deepagents_missing",
            params={"error": str(exc)},
        )
        raise RuntimeError(
            "deepagents 패키지가 설치되어 있지 않습니다. "
            "`uv sync` 후 다시 시도하세요."
        ) from exc

    agent = create_deep_agent(
        tools=[submit_clarification_questions],
        instructions=DEEP_AGENT_INSTRUCTIONS,
        model=get_llm(),
    )

    _emit(
        on_progress,
        ClarificationProgressEvent(
            phase="drafting_questions",
            message="후보 질문 작성 중...",
            progress=0.6,
            data={"drafted": 0},
        ),
    )

    agent.invoke({"messages": [{"role": "user", "content": user_message}]})

    if "questions" not in captured:
        SmartLogger.log(
            "WARN",
            "Deep agent finished without calling submit_clarification_questions",
            category="requirements.clarification.no_terminal_call",
            params={"requirementCount": len(requirements)},
        )
        # Treat as analysis failure so the route layer can surface it.
        raise RuntimeError("deep agent did not submit a question queue")

    questions = _normalize_questions(
        captured["questions"], valid_requirement_ids=valid_ids
    )
    no_ambiguities = bool(captured.get("noAmbiguities")) and not questions
    deferred_note = captured.get("deferredNote") if not no_ambiguities else None
    coverage = _normalize_coverage(captured.get("coverage") or [])

    queue = QuestionQueue(
        questions=questions,
        noAmbiguities=no_ambiguities,
        deferredNote=deferred_note,
        coverage=coverage,
    )

    _emit(
        on_progress,
        ClarificationProgressEvent(
            phase="questions_ready",
            message=(
                "모호성 없음" if no_ambiguities else f"{len(questions)}개 질문 준비됨"
            ),
            progress=1.0,
            data={
                "questions": [q.model_dump() for q in questions],
                "noAmbiguities": no_ambiguities,
                "deferredNote": deferred_note,
            },
        ),
    )

    return queue
