"""042 US2 — Decompose 스테이지(robo-proposal-strategic-ddd)."""

from __future__ import annotations

import json
from typing import AsyncGenerator

from api.features.proposal_lifecycle.services import staged_runner
from api.features.proposal_lifecycle.services.stage_runners.base import execute_stage

_SKILL = "robo-proposal-strategic-ddd"


def _build_prompt(state: dict) -> str:
    discover = (state.get("stageArtifacts") or {}).get("DISCOVER", {})
    return (
        "stage: DECOMPOSE\n"
        f"원본 프롬프트: {state.get('prompt','')}\n\n"
        f"Discover 산출물(JSON):\n{json.dumps(discover, ensure_ascii=False)}\n\n"
        "영향 이벤트를 도메인 용어 서브도메인(기술 용어 금지)으로 묶고, 각 서브도메인에 한 줄 책임과 "
        "인접 관계를 부여하라. 느슨한 결합 점검(자율 변경 가능/언어 일관/적정 크기)을 메모하라.\n"
        '출력: {"DecomposeArtifact": {"subDomains":[{"name":"...","responsibility":"...","eventRefs":["..."]}], '
        '"adjacency":[{"from":"...","to":"..."}], "couplingNotes":["..."]}}'
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
        proposal_id, "DECOMPOSE", _SKILL, prompt,
        artifact_key="DecomposeArtifact", parse_error_code="DECOMPOSE_PARSE_FAILED",
        validators=[(lambda a: bool(a.get("subDomains")), "서브도메인이 비어 있습니다")],
    ):
        yield ev
