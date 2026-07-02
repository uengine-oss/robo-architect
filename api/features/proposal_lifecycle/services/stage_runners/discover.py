"""042 US2 — Discover 스테이지(robo-proposal)."""

from __future__ import annotations

import json
from typing import AsyncGenerator

from api.features.proposal_lifecycle.services import staged_runner
from api.features.proposal_lifecycle.services.stage_runners.base import (
    execute_stage, domain_node_lines,
)

_SKILL = "robo-proposal"


def _build_prompt(state: dict) -> str:
    return (
        "mode: DETAILED_DDD\n"
        "phase: STRATEGIC_DDD\n"
        "stage: DISCOVER\n"
        f"원본 프롬프트: {state.get('prompt','')}\n\n"
        f"현재 도메인 노드:\n{domain_node_lines()}\n\n"
        "이 변경이 도입/영향을 주는 도메인 이벤트(과거형)를 시간 순으로 펼치고, "
        "Pivotal Event 와 Hotspot(각각 resolve-now/defer 분류), 외부 시스템, 액터를 식별하라.\n"
        '출력: {"DiscoverArtifact": {"events":[{"name":"...","actor":"...","external":false}], '
        '"pivotalEvents":["..."], "hotspots":[{"text":"...","disposition":"RESOLVE_NOW"}]}}'
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
        proposal_id, "DISCOVER", _SKILL, prompt,
        artifact_key="DiscoverArtifact", parse_error_code="DISCOVER_PARSE_FAILED",
        validators=[(lambda a: bool(a.get("events")), "이벤트가 비어 있습니다")],
    ):
        yield ev
