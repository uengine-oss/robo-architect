"""
Proposal Strategic Diff skill invocation service.
자연어 → Strategic Diff + 명확화 질문.
"""

from __future__ import annotations

import json
from typing import AsyncGenerator

from api.features.proposal_lifecycle.services.proposal_ai_runner import (
    run_validated_skill_once,
    stream_validated_skill_json,
)
from api.features.proposal_lifecycle.services.proposal_ai_validation import (
    SkillScenario,
    retry_count_for_scenario,
    validate_strategic_output,
)
from api.platform.neo4j import get_session
from api.platform.neo4j_helpers import load_domain_nodes
from api.platform.observability.smart_logger import SmartLogger
from api.features.proposal_lifecycle.services import proposal_interactions, proposal_state_service

_SKILL_ROOT = "robo-proposals"
_SKILL_NAME = "robo-proposal"


def _build_intent_prompt(
    proposal_id: str,
    original_prompt: str,
    domain_nodes: list[dict],
    clarification_log: list[dict] | None = None,
    feedback_log: list[dict] | None = None,
    prev_strategic: dict | None = None,
    prev_tactical: list | None = None,
) -> str:
    node_list = "\n".join(
        f"- id: {n['id']}, type: {n.get('label', '')}, name: {n.get('name', '')}"
        for n in (domain_nodes or [])
    )
    clarify_section = ""
    if clarification_log:
        qa_lines = "\n".join(
            f"Q{e.get('questionIndex', i)}: {e.get('question', '')} → A: {e.get('answer', '')}"
            for i, e in enumerate(clarification_log)
        )
        clarify_section = f"\n\n사용자 명확화 답변:\n{qa_lines}"

    # 재생성(피드백 반영): 직전 분해 결과 + 사용자의 보정 피드백을 함께 제시해
    # 잘못 분석된 부분만 고쳐 다시 생성하도록 유도한다.
    feedback_section = ""
    if feedback_log:
        prev_summary = json.dumps(
            {"strategicDiff": prev_strategic or {}, "tacticalDiff": prev_tactical or []},
            ensure_ascii=False,
        )
        fb_lines = "\n".join(f"- {e.get('feedback', '')}" for e in feedback_log if e.get("feedback"))
        feedback_section = (
            f"\n\n이전 분석 결과:\n{prev_summary}"
            f"\n\n사용자 피드백(재생성):\n{fb_lines}"
            "\n\n위 피드백을 최우선으로 반영해 분해 결과를 다시 생성하세요. "
            "피드백이 지적하지 않은 부분은 이전 결과를 유지하고, 가능하면 명확화 질문 없이 action:\"done\"으로 반환하세요."
        )

    return (
        f"Proposal ID: {proposal_id}\n"
        f"scenario: {SkillScenario.SIMPLIFIED_STRATEGIC.value}\n"
        f"원본 프롬프트: {original_prompt}\n\n"
        f"현재 도메인 구성 요소 목록:\n{node_list or '(구성 요소 없음)'}"
        f"{clarify_section}"
        f"{feedback_section}\n\n"
        "위 변경 내용을 **Strategic Diff(Epic/Feature/UserStory/Process)만** 으로 분해하여 JSON으로 출력하세요. "
        "Tactical Diff(Aggregate/Command/Event/VO)와 아키텍처는 이후 Plan 단계에서 다루므로 여기서는 산출하지 마세요."
    )


def _load_intent_inputs(proposal_id: str) -> dict | None:
    """프롬프트 구성에 필요한 Proposal 필드(원본/명확화/피드백/이전 diff)를 한 번에 로드한다."""
    with get_session() as session:
        result = session.run(
            "MATCH (p:Proposal {id: $id}) RETURN p.originalPrompt AS prompt, "
            "p.clarificationLog AS clog, p.intentFeedbackLog AS flog, "
            "p.strategicDiff AS sd, p.tacticalDiff AS td",
            id=proposal_id,
        )
        record = result.single()

    if not record:
        return None

    def _parse(raw, default):
        try:
            return json.loads(raw) if raw else default
        except Exception:
            return default

    return {
        "original_prompt": record["prompt"] or "",
        "clog": _parse(record.get("clog"), []),
        "flog": _parse(record.get("flog"), []),
        "prev_strategic": _parse(record.get("sd"), {}),
        "prev_tactical": _parse(record.get("td"), []),
    }


async def run_intent(proposal_id: str) -> None:
    """
    Strategic Diff 스킬을 실행하고 결과를 Neo4j에 저장한다.
    백그라운드 태스크로 호출.
    """
    SmartLogger.log("INFO", f"intent_start: {proposal_id}",
                    category="proposal_lifecycle.intent.start",
                    params={"proposalId": proposal_id})

    inputs = _load_intent_inputs(proposal_id)
    if not inputs:
        return

    domain_nodes = load_domain_nodes()
    human_prompt = _build_intent_prompt(
        proposal_id, inputs["original_prompt"], domain_nodes,
        inputs["clog"], inputs["flog"], inputs["prev_strategic"], inputs["prev_tactical"],
    )

    result = await run_validated_skill_once(
        skill_name=_SKILL_NAME,
        prompt_builder=lambda feedback: _with_validation_feedback(human_prompt, feedback),
        validator=lambda data: validate_strategic_output(data, allow_clarify=True),
        proposal_id=proposal_id,
        scenario=SkillScenario.SIMPLIFIED_STRATEGIC.value,
        max_retries=retry_count_for_scenario(SkillScenario.SIMPLIFIED_STRATEGIC),
        parse_error_code="INTENT_PARSE_FAILED",
        validation_error_code="INTENT_CONTRACT_INVALID",
        timeout=300,
    )
    if not result.valid:
        SmartLogger.log("WARN", f"intent contract invalid for {proposal_id}",
                        category="proposal_lifecycle.intent.contract_invalid",
                        params={"proposalId": proposal_id, "violations": result.violations},
                        max_inline_chars=0)
        return

    _save_intent_result(proposal_id, result.normalized_output)


def _save_intent_result(proposal_id: str, data: dict) -> None:
    action = data.get("action", "done")

    if action == "clarify":
        questions = data.get("questions", [])
        first_question = questions[0] if questions else {}
        try:
            clog_entry = json.dumps([{"question": first_question.get("text", ""), "options": first_question.get("options", [])}], ensure_ascii=False)
        except Exception:
            clog_entry = "[]"
        with get_session() as session:
            session.run(
                "MATCH (p:Proposal {id: $id}) SET p.clarificationLog = $clog",
                id=proposal_id, clog=clog_entry,
            )
        if first_question:
            proposal_interactions.record_question(
                proposal_id,
                "STRATEGIC_DIFF",
                first_question.get("text", ""),
                first_question.get("options", []),
            )
        SmartLogger.log("INFO", f"Clarification questions saved for {proposal_id}",
                        category="proposal_lifecycle.intent.clarify",
                        params={"proposalId": proposal_id, "questionCount": 1 if first_question else 0})
        return

    # action == "done"
    # 041: Intent 는 Strategic Diff 만 산출한다(FR-006). Tactical/Impact 는 Plan 단계로 이동.
    strategic_diff = data.get("strategicDiff", {})
    journeys = data.get("journeys", [])

    # Strategic Diff 재실행 시 version 을 올려, 기존 plan 을 stale 로 만든다(FR-018).
    inputs = _load_intent_inputs(proposal_id)
    prev_version = 1
    if inputs and isinstance(inputs.get("prev_strategic"), dict):
        prev_version = inputs["prev_strategic"].get("version", 1) or 1
    if isinstance(strategic_diff, dict):
        strategic_diff["version"] = max(prev_version, strategic_diff.get("version", 1) or 1)
        # 이전에 Strategic Diff 가 있었고 내용이 바뀐 재실행이면 버전 증가.
        if inputs and inputs.get("prev_strategic"):
            strategic_diff["version"] = prev_version + 1

    # 제목 자동 추출 (첫 UserStory 제목 또는 originalPrompt 첫 문장)
    auto_title = None
    us_list = strategic_diff.get("userStories", []) if isinstance(strategic_diff, dict) else []
    if us_list:
        auto_title = us_list[0].get("entityTitle") or us_list[0].get("storyTitle")

    with get_session() as session:
        params: dict = {
            "id": proposal_id,
            "strategicDiff": json.dumps(strategic_diff, ensure_ascii=False),
            "journeys": json.dumps(journeys, ensure_ascii=False),
        }
        if auto_title:
            params["title"] = auto_title

        set_parts = ["p.strategicDiff = $strategicDiff", "p.journeys = $journeys"]
        if auto_title:
            set_parts.append("p.title = $title")

        session.run(
            f"MATCH (p:Proposal {{id: $id}}) SET {', '.join(set_parts)}",
            **params,
        )
    proposal_state_service.set_lifecycle(
        proposal_id,
        lifecycle_status="ACTIVE",
        current_phase="SUBMIT",
        clear_pending_question=True,
    )

    SmartLogger.log("INFO", f"Intent done: {proposal_id}",
                    category="proposal_lifecycle.intent.done",
                    params={"proposalId": proposal_id})


async def run_intent_with_clarification(proposal_id: str, answers) -> None:
    """명확화 답변 후 intent 스킬 재실행."""
    await run_intent(proposal_id)


async def stream_intent(proposal_id: str) -> AsyncGenerator[tuple[str, dict], None]:
    """
    인텐트 분해 진행 상황을 SSE 이벤트로 yield한다.
    phase → (clarification_needed | strategic_diff + tactical_diff + impact_map) → done
    """
    yield "phase", {"phase": "intent_decomposition", "message": "자연어 인텐트 분해 중..."}

    inputs = _load_intent_inputs(proposal_id)
    if not inputs:
        yield "error", {"code": "NOT_FOUND", "message": f"Proposal {proposal_id} not found"}
        return

    domain_nodes = load_domain_nodes()
    human_prompt = _build_intent_prompt(
        proposal_id, inputs["original_prompt"], domain_nodes,
        inputs["clog"], inputs["flog"], inputs["prev_strategic"], inputs["prev_tactical"],
    )

    result_data = None
    async for event_type, data in stream_validated_skill_json(
        skill_name=_SKILL_NAME,
        prompt_builder=lambda feedback: _with_validation_feedback(human_prompt, feedback),
        validator=lambda raw: validate_strategic_output(raw, allow_clarify=True),
        proposal_id=proposal_id,
        scenario=SkillScenario.SIMPLIFIED_STRATEGIC.value,
        max_retries=retry_count_for_scenario(SkillScenario.SIMPLIFIED_STRATEGIC),
        parse_error_code="INTENT_PARSE_FAILED",
        validation_error_code="INTENT_CONTRACT_INVALID",
    ):
        if event_type == "result":
            result_data = data
            break
        yield event_type, data
        if event_type == "error":
            return

    if not isinstance(result_data, dict):
        yield "error", {"code": "INTENT_FAILED", "message": "인텐트 분해 실패"}
        return

    action = result_data.get("action", "done")

    if action == "clarify":
        questions = result_data.get("questions", [])
        _save_intent_result(proposal_id, result_data)
        yield "clarification_needed", {"questions": questions}
        yield "done", {"proposalId": proposal_id, "status": "DRAFT"}
        return

    _save_intent_result(proposal_id, result_data)

    # 041: Intent 는 Strategic Diff 만 스트리밍한다. Tactical/Impact 는 Plan 단계로 이동(FR-006).
    if result_data.get("strategicDiff"):
        yield "strategic_diff", {"strategicDiff": result_data["strategicDiff"]}

    yield "done", {"proposalId": proposal_id, "status": "DRAFT", "nextStage": "plan"}


def _with_validation_feedback(prompt: str, feedback: str | None) -> str:
    if not feedback:
        return prompt
    return (
        f"{prompt}\n\n"
        "이전 산출물이 backend validator 계약 검증에 실패했습니다. "
        "아래 violation을 모두 수정해 같은 JSON 계약으로 다시 출력하세요.\n"
        f"{feedback}"
    )
