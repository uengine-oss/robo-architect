"""042 US2 — Connect 스테이지(robo-proposal-tactical-ddd)."""

from __future__ import annotations

import json
from typing import AsyncGenerator

from api.features.constitution.services import constitution_store as cstore
from api.features.proposal_lifecycle.services import staged_runner
from api.features.proposal_lifecycle.services.stage_runners.base import execute_stage

_SKILL = "robo-proposal-tactical-ddd"


def _build_prompt(state: dict) -> str:
    arts = state.get("stageArtifacts") or {}
    memory = cstore.get_project_strategic_memory() or {}
    posture = (memory.get("couplingPosture") or {}).get("default", "PUBSUB")
    return (
        "stage: CONNECT\n"
        f"원본 프롬프트: {state.get('prompt','')}\n\n"
        f"Decompose/Strategize 산출물(JSON):\n"
        f"{json.dumps({'DECOMPOSE': arts.get('DECOMPOSE'), 'STRATEGIZE': arts.get('STRATEGIZE')}, ensure_ascii=False)}\n\n"
        f"프로젝트 기본 결합 posture: {posture} (특별한 동기 요구가 없으면 이 기본을 유지)\n\n"
        "컨텍스트 간 상호작용을 Event(pub/sub)/Command/Query 로 분류하라. 기본은 이벤트 드리븐 pub/sub, "
        "즉시 응답이 꼭 필요할 때만 sync. 결합 점검(양방향 동기 금지, 동기 체인 깊이≤3, 한 컨텍스트가 "
        "5개 이상과 통신하면 경고)을 수행하고 메시징 채널을 명시하라(기본 Kafka).\n"
        '출력: {"ConnectArtifact": {"interactions":[{"from":"...","to":"...","message":"...",'
        '"kind":"EVENT","sync":false,"rationale":"..."}], "couplingWarnings":["..."], "messagingChannel":"Kafka"}}'
    )


async def stream(proposal_id: str, feedback: str = None) -> AsyncGenerator[tuple[str, object], None]:
    state = staged_runner.load_state(proposal_id)
    if not state:
        yield "error", {"code": "NOT_FOUND", "message": "Proposal not found"}
        return
    prompt = _build_prompt(state)
    if feedback:
        prompt += f"\n\n사용자 피드백(재생성, 최우선 반영): {feedback}"
    async for ev in execute_stage(
        proposal_id, "CONNECT", _SKILL, prompt,
        artifact_key="ConnectArtifact", parse_error_code="CONNECT_PARSE_FAILED",
        validators=[(lambda a: bool(a.get("interactions")), "상호작용이 비어 있습니다")],
        detect_conflicts=True,
    ):
        yield ev
