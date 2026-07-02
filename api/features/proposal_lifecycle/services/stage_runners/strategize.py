"""042 US2 — Strategize 스테이지(robo-proposal).

기존 전략 메모리(Core/Supporting/Generic)를 주입해 재질문 대신 confirm/amend 로 진행(FR-018),
로컬 분류가 메모리와 어긋나면 conflicts SSE(FR-019).
"""

from __future__ import annotations

import json
from typing import AsyncGenerator

from api.features.constitution.services import constitution_store as cstore
from api.features.proposal_lifecycle.services import staged_runner
from api.features.proposal_lifecycle.services.stage_runners.base import execute_stage

_SKILL = "robo-proposal"


def _build_prompt(state: dict) -> str:
    decompose = (state.get("stageArtifacts") or {}).get("DECOMPOSE", {})
    memory = cstore.get_project_strategic_memory() or {}
    return (
        "mode: DETAILED_DDD\n"
        "phase: STRATEGIC_DDD\n"
        "stage: STRATEGIZE\n"
        f"원본 프롬프트: {state.get('prompt','')}\n\n"
        f"Decompose 산출물(JSON):\n{json.dumps(decompose, ensure_ascii=False)}\n\n"
        f"기존 전략 메모리(JSON, 이미 분류된 BC 는 재질문 말고 그대로 사용):\n"
        f"{json.dumps(memory, ensure_ascii=False)}\n\n"
        "각 영향 서브도메인을 Core/Supporting/Generic 으로 분류하라. 모호하면 차별성 질문"
        "('고객이 직접 구축 vs 외부 구매의 차이를 느끼는가') 과 시장 성숙도 질문('좋은 외부 솔루션이 "
        "있는가')을 적용하라. Generic 이면 build-vs-buy 후보를 적어라.\n"
        '출력: {"StrategizeArtifact": {"classifications":[{"subDomain":"...","kind":"CORE",'
        '"rationale":"...","buildVsBuy":null}]}}'
    )


def _all_classified(a: dict) -> bool:
    cls = a.get("classifications") or []
    return bool(cls) and all(c.get("kind") in ("CORE", "SUPPORTING", "GENERIC") for c in cls)


async def stream(proposal_id: str, feedback: str = None) -> AsyncGenerator[tuple[str, object], None]:
    state = staged_runner.load_state(proposal_id)
    if not state:
        yield "error", {"code": "NOT_FOUND", "message": "Proposal not found"}
        return
    prompt = _build_prompt(state)
    if feedback:
        prompt += f"\n\n사용자 피드백(재생성, 최우선 반영): {feedback}"
    async for ev in execute_stage(
        proposal_id, "STRATEGIZE", _SKILL, prompt,
        artifact_key="StrategizeArtifact", parse_error_code="STRATEGIZE_PARSE_FAILED",
        validators=[(_all_classified, "분류(kind)가 비었거나 잘못되었습니다")],
        detect_conflicts=True,
    ):
        yield ev
