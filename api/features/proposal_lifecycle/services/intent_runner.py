"""
robo-proposal-intent 스킬 호출 서비스.
자연어 → Strategic Diff + Tactical Diff 분해 + 명확화 질문.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import AsyncGenerator

from api.platform.neo4j import get_session
from api.platform.neo4j_helpers import load_domain_nodes
from api.platform.observability.smart_logger import SmartLogger
from api.platform.skill_runner import run_skill_once, run_skill_lines, extract_json
from api.features.proposal_lifecycle.services.legacy_provenance import (
    MARK_QUERY,
    ProvenanceCollector,
    is_marker as is_provenance_marker,
)

_SKILL_ROOT = "robo-proposals"
_SKILL_NAME = "robo-proposal-intent"


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
        f"원본 프롬프트: {original_prompt}\n\n"
        f"현재 도메인 구성 요소 목록:\n{node_list or '(구성 요소 없음)'}"
        f"{clarify_section}"
        f"{feedback_section}\n\n"
        "위 변경 내용을 **Strategic Diff(Epic/Feature/UserStory/Process)만** 으로 분해하여 JSON으로 출력하세요. "
        "Tactical Diff(Aggregate/Command/Event/VO)와 아키텍처는 이후 Plan 단계에서 다루므로 여기서는 산출하지 마세요."
    )


def _build_reverse_prompt(brief_text: str) -> str:
    """047 — 레거시 코드분석 브리프 → 요구사항 도출(역방향). _build_intent_prompt 대응·수정.

    입력이 "변경 요청(자연어)"이 아니라 "테이블 앵커 브리프(코드분석 무손실)"이며,
    지시를 "변경 분해"에서 "코드분석 → 요구사항 도출"로 바꾼다. 출력 형식은 동일한
    Strategic Diff 라 하류(plan/tasks/implement)를 그대로 재사용한다.
    """
    return (
        "다음은 레거시 시스템의 코드 분석 결과다 — 하나의 데이터(Aggregate 후보 테이블)를 중심으로,\n"
        "그 테이블을 변경하는 오퍼레이션들의 비즈니스 규칙과 시나리오(GWT)를 코드 그래프에서 무손실 추출한 것이다.\n\n"
        f"--- 코드 분석 결과 ---\n{brief_text}\n--- 끝 ---\n\n"
        "현재 도메인 구성 요소 목록:\n(없음 — 신규 도출)\n\n"
        "위 분석 결과로부터 이 시스템이 '무엇을 하는지' 사용자/업무 관점의 요구사항을 도출하라. "
        "코드 구현 세부가 아니라 요구사항으로 재구성하고, 각 규칙·시나리오가 UserStory/GWT 에 반영되게 하라. "
        "위 내용을 Strategic Diff(BoundedContext/Feature/UserStory/Process)로 분해하여 JSON 으로 출력하세요. "
        "Tactical Diff/아키텍처는 산출하지 마세요."
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
    robo-proposal-intent 스킬을 실행하고 결과를 Neo4j에 저장한다.
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

    raw = await run_skill_once(_SKILL_ROOT, _SKILL_NAME, human_prompt, timeout=300)
    if not raw:
        SmartLogger.log("WARN", f"intent skill returned nothing for {proposal_id}",
                        category="proposal_lifecycle.intent.empty", params={"proposalId": proposal_id})
        return

    result_data = extract_json(raw)
    if not result_data or not isinstance(result_data, dict):
        SmartLogger.log("WARN", f"intent skill no JSON for {proposal_id}",
                        category="proposal_lifecycle.intent.no_json", params={"proposalId": proposal_id})
        return

    _save_intent_result(proposal_id, result_data)


def _save_intent_result(proposal_id: str, data: dict) -> None:
    action = data.get("action", "done")

    if action == "clarify":
        questions = data.get("questions", [])
        try:
            clog_entry = json.dumps([{"question": q.get("text", ""), "options": q.get("options", [])} for q in questions], ensure_ascii=False)
        except Exception:
            clog_entry = "[]"
        with get_session() as session:
            session.run(
                "MATCH (p:Proposal {id: $id}) SET p.clarificationLog = $clog",
                id=proposal_id, clog=clog_entry,
            )
        SmartLogger.log("INFO", f"Clarification questions saved for {proposal_id}",
                        category="proposal_lifecycle.intent.clarify",
                        params={"proposalId": proposal_id, "questionCount": len(questions)})
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

    output_lines: list[str] = []
    # narration(분석 서술)만 사용자에게 보여주고, raw JSON 블록은 파싱용으로만 수집.
    # SKILL.md가 narration 뒤 ```json 펜스로 JSON을 출력하므로 펜스/여는 중괄호를
    # 만나는 순간부터 log_line 방출을 멈춘다.
    suppress_log = False
    provenance = ProvenanceCollector()   # spec 052 — 이 스테이지의 레거시 참조 결정론 기록
    async for line in run_skill_lines(_SKILL_ROOT, _SKILL_NAME, human_prompt):
        if is_provenance_marker(line):
            entry = provenance.feed(line)
            if line.startswith(MARK_QUERY):
                try:
                    q = str(json.loads(line[len(MARK_QUERY):]).get("query", "")).strip()
                except ValueError:
                    q = ""
                if q:
                    yield "log_line", {"text": f"🔍 레거시 그래프 검색: \"{q}\""}
            if entry is not None:
                yield "legacy_ref", entry
                yield "log_line", {"text": f"   → 레거시 함수 {len(entry['nodes'])}개 · "
                                           f"규칙 {sum(n['rulesCount'] for n in entry['nodes'])}개 참조됨 ⛓"}
            continue
        if line.startswith("TOOL:"):
            parts = line[5:].split(":", 1)
            yield "tool_use", {"tool": parts[0].strip(), "path": parts[1].strip() if len(parts) > 1 else ""}
            yield "log_line", {"text": f"[tool] {parts[0].strip()} {parts[1].strip() if len(parts) > 1 else ''}"}
            continue

        output_lines.append(line)  # 파싱용으로는 항상 수집

        stripped = line.strip()
        # ```json 펜스 또는 최상위 여는 중괄호/대괄호 → 이후는 JSON 페이로드
        if stripped.startswith("```") or (not suppress_log and stripped in ("{", "[")):
            suppress_log = True
            continue
        if not suppress_log:
            yield "log_line", {"text": line}

    raw = "\n".join(output_lines)
    if not raw.strip():
        yield "error", {"code": "INTENT_FAILED", "message": "인텐트 분해 실패"}
        return

    result_data = extract_json(raw)
    if not result_data or not isinstance(result_data, dict):
        yield "error", {"code": "INTENT_PARSE_FAILED", "message": "인텐트 분해 결과 파싱 실패"}
        return

    action = result_data.get("action", "done")

    if action == "clarify":
        questions = result_data.get("questions", [])
        _save_intent_result(proposal_id, result_data)
        provenance.save(proposal_id, "INTENT")   # spec 052 — clarify 여도 검색 기록은 보존
        yield "clarification_needed", {"questions": questions}
        yield "done", {"proposalId": proposal_id, "status": "DRAFT"}
        return

    _save_intent_result(proposal_id, result_data)
    provenance.save(proposal_id, "INTENT")       # spec 052

    # 041: Intent 는 Strategic Diff 만 스트리밍한다. Tactical/Impact 는 Plan 단계로 이동(FR-006).
    if result_data.get("strategicDiff"):
        yield "strategic_diff", {"strategicDiff": result_data["strategicDiff"]}

    yield "done", {"proposalId": proposal_id, "status": "DRAFT", "nextStage": "plan"}
