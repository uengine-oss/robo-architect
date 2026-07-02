"""042 US2 — Define 스테이지(robo-proposal)."""

from __future__ import annotations

import json
from typing import AsyncGenerator

from api.features.constitution.services import constitution_store as cstore
from api.features.proposal_lifecycle.services import staged_runner
from api.features.proposal_lifecycle.services.stage_runners.base import execute_stage

_SKILL = "robo-proposal"


def _build_prompt(state: dict) -> str:
    arts = state.get("stageArtifacts") or {}
    memory = cstore.get_project_strategic_memory() or {}
    return (
        "mode: DETAILED_DDD\n"
        "phase: TACTICAL_DDD\n"
        "stage: DEFINE\n"
        f"원본 프롬프트: {state.get('prompt','')}\n\n"
        f"Strategize/Connect 산출물(JSON):\n"
        f"{json.dumps({'STRATEGIZE': arts.get('STRATEGIZE'), 'CONNECT': arts.get('CONNECT')}, ensure_ascii=False)}\n\n"
        f"기존 전략 메모리(이미 정의된 BC 의 유비쿼터스 언어/비즈니스 결정은 재사용):\n"
        f"{json.dumps(memory.get('contexts', {}), ensure_ascii=False)}\n\n"
        "각 영향 BC 에 대해 ddd-crew Bounded Context Canvas(v5) 전 항목을 작성하라:\n"
        "- purpose: 비즈니스 관점의 책임/제공 가치\n"
        "- classification: 도메인 분류 CORE|SUPPORTING|GENERIC (Strategize 결과 일치)\n"
        "- businessModel: revenue|engagement|compliance|cost_reduction 중 해당되는 것(복수)\n"
        "- evolution: genesis|custom_built|product|commodity 중 하나\n"
        "- domainRoles: draft|execution|analysis|gateway|other context 중 해당 역할\n"
        "- inbound/outbound: {collaborator, message, type:Query|Command|Event}\n"
        "- ubiquitousLanguage(5개 이상): {term, definition}\n"
        "- businessDecisions: 핵심 비즈니스 규칙/정책/결정\n"
        "- assumptions: 검증되지 않은 설계 가정\n"
        "- verificationMetrics: 이 BC 구조를 (in)validate 할 지표\n"
        "- openQuestions: 미해결 질문\n"
        "- languageClashes: 다른 컨텍스트와 같은 단어가 다른 의미인 용어\n"
        '출력: {"DefineArtifact": {"contexts":[{"name":"...","purpose":"...","classification":"CORE",'
        '"businessModel":["revenue"],"evolution":"custom_built","domainRoles":["execution"],'
        '"inbound":[{"collaborator":"...","message":"...","type":"Command"}],'
        '"outbound":[{"collaborator":"...","message":"...","type":"Event"}],'
        '"ubiquitousLanguage":[{"term":"...","definition":"..."}],"businessDecisions":["..."],'
        '"assumptions":["..."],"verificationMetrics":["..."],"openQuestions":["..."],"languageClashes":["..."]}]}}'
    )


def _has_min_language(a: dict) -> bool:
    ctxs = a.get("contexts") or []
    return bool(ctxs) and all(len(c.get("ubiquitousLanguage") or []) >= 5 for c in ctxs)


async def stream(proposal_id: str, feedback: str = None) -> AsyncGenerator[tuple[str, object], None]:
    state = staged_runner.load_state(proposal_id)
    if not state:
        yield "error", {"code": "NOT_FOUND", "message": "Proposal not found"}
        return
    prompt = _build_prompt(state)
    if feedback:
        prompt += f"\n\n사용자 피드백(재생성, 최우선 반영): {feedback}"
    async for ev in execute_stage(
        proposal_id, "DEFINE", _SKILL, prompt,
        artifact_key="DefineArtifact", parse_error_code="DEFINE_PARSE_FAILED",
        validators=[(_has_min_language, "유비쿼터스 언어가 5개 미만인 컨텍스트가 있습니다")],
        detect_conflicts=True,
    ):
        yield ev
