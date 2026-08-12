"""042 US2 — Define 스테이지(robo-proposal-define, extends ddd-starter 07)."""

from __future__ import annotations

import json
from typing import AsyncGenerator

from api.features.constitution.services import constitution_store as cstore
from api.features.proposal_lifecycle.services import staged_runner
from api.features.proposal_lifecycle.services.stage_runners.base import execute_stage
from api.features.proposal_lifecycle.services.legacy_evidence import (
    build_evidence_packet,
    evidence_prompt_block,
)

_SKILL = "robo-proposal-define"


def _build_prompt(state: dict) -> str:
    arts = state.get("stageArtifacts") or {}
    memory = cstore.get_project_strategic_memory() or {}
    packet = build_evidence_packet(state.get("legacyReferences"))
    return (
        "[TASK]\n영향 Bounded Context의 책임·언어·업무결정과 구현할 UserStory를 정의한다.\n\n"
        f"[ORIGINAL REQUIREMENT]\n{state.get('prompt','')}\n\n"
        f"Strategize/Connect 산출물(JSON):\n"
        f"{json.dumps({'STRATEGIZE': arts.get('STRATEGIZE'), 'CONNECT': arts.get('CONNECT')}, ensure_ascii=False)}\n\n"
        f"[INSPECTED LEGACY EVIDENCE — nodeId 중복 제거]\n"
        f"{evidence_prompt_block(packet)}\n"
        "이미 packet에 있는 nodeId는 재조회하지 않는다. 의미 판단에 필수인 근거가 없을 때만 MCP로 갭을 조회한다.\n\n"
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
        "- userStories: 이 BC에서 실제 구현할 사용자/시스템 목표. 각 항목은 고유 id, role, action, "
        "benefit, acceptanceCriteria, legacyRefs를 가진다. acceptanceCriteria의 값·분기·반환은 위 근거만 사용한다.\n"
        "예시의 상태/숫자를 복사하지 말고, 근거가 없는 상태 전이는 만들지 않는다.\n"
        '출력: {"DefineArtifact": {"contexts":[{"name":"...","purpose":"...","classification":"CORE",'
        '"businessModel":["revenue"],"evolution":"custom_built","domainRoles":["execution"],'
        '"inbound":[{"collaborator":"...","message":"...","type":"Command"}],'
        '"outbound":[{"collaborator":"...","message":"...","type":"Event"}],'
        '"ubiquitousLanguage":[{"term":"...","definition":"..."}],"businessDecisions":["..."],'
        '"assumptions":["..."],"verificationMetrics":["..."],"openQuestions":["..."],"languageClashes":["..."],'
        '"userStories":[{"id":"us:<stable-id>","role":"...","action":"...","benefit":"...",'
        '"acceptanceCriteria":["Given ... When ... Then ..."],"legacyRefs":[]}]}]}}'
    )


def _has_min_language(a: dict) -> bool:
    ctxs = a.get("contexts") or []
    return bool(ctxs) and all(len(c.get("ubiquitousLanguage") or []) >= 5 for c in ctxs)


def _has_complete_user_stories(a: dict) -> bool:
    contexts = a.get("contexts") or []
    if not contexts:
        return False
    ids: set[str] = set()
    for context in contexts:
        stories = context.get("userStories") or []
        if not stories:
            return False
        for story in stories:
            if not isinstance(story, dict):
                return False
            story_id = str(story.get("id") or "").strip()
            if not story_id or story_id in ids:
                return False
            ids.add(story_id)
            if not all(story.get(key) for key in ("role", "action", "benefit")):
                return False
            if not isinstance(story.get("acceptanceCriteria"), list) or not story["acceptanceCriteria"]:
                return False
            if not isinstance(story.get("legacyRefs"), list):
                return False
    return True


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
        blocking_validators=[(
            _has_complete_user_stories,
            "모든 context에 고유 id·role·action·benefit·acceptanceCriteria·legacyRefs를 가진 userStories가 필요합니다",
        )],
        detect_conflicts=True,
    ):
        yield ev
