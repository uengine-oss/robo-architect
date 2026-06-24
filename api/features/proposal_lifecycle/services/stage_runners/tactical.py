"""042 US2 — Tactical 스테이지(robo-proposal-tactical, extends ddd-starter 08 + plan 전술)."""

from __future__ import annotations

import json
from typing import AsyncGenerator

from api.features.proposal_lifecycle.services import staged_runner
from api.features.proposal_lifecycle.services.stage_runners.base import execute_stage

_SKILL = "robo-proposal-tactical"


def _build_prompt(state: dict) -> str:
    define = (state.get("stageArtifacts") or {}).get("DEFINE", {})
    return (
        f"원본 프롬프트: {state.get('prompt','')}\n\n"
        f"Define(BCC) 산출물(JSON):\n{json.dumps(define, ensure_ascii=False)}\n\n"
        "각 Aggregate 에 대해 ddd-crew Aggregate Design Canvas(v1) 전 항목을 도출하라:\n"
        "- name, description(한 줄 책임), boundaryRationale(함께 변하는가/한 트랜잭션 일관성)\n"
        "- stateTransitions: [{from,to,trigger}]\n"
        "- invariants: Enforced Invariants(2개 이상)\n"
        "- correctivePolicies: 규칙 위반 시 보정 정책\n"
        "- handledCommands / createdEvents\n"
        "- throughput: {commandHandlingRate:{avg,max}, totalClients:{avg,max}, concurrencyConflictChance:{avg,max}}\n"
        "- size: {eventGrowthRate:{avg,max}, lifetime:{avg,max}, eventsPersisted:{avg,max}}\n"
        "Aggregate 는 작게 유지하고 Value Object 는 Aggregate 로 모델링하지 마라.\n"
        '출력: {"TacticalArtifact": {"aggregates":[{"name":"...","description":"...","boundaryRationale":"...",'
        '"stateTransitions":[{"from":"...","to":"...","trigger":"..."}],"invariants":["...","..."],'
        '"correctivePolicies":["..."],"handledCommands":["..."],"createdEvents":["..."],'
        '"throughput":{"commandHandlingRate":{"avg":"","max":""},"totalClients":{"avg":"","max":""},'
        '"concurrencyConflictChance":{"avg":"","max":""}},'
        '"size":{"eventGrowthRate":{"avg":"","max":""},"lifetime":{"avg":"","max":""},'
        '"eventsPersisted":{"avg":"","max":""}}}]}}'
    )


def _has_min_invariants(a: dict) -> bool:
    aggs = a.get("aggregates") or []
    return bool(aggs) and all(len(g.get("invariants") or []) >= 2 for g in aggs)


async def stream(proposal_id: str, feedback: str = None) -> AsyncGenerator[tuple[str, object], None]:
    state = staged_runner.load_state(proposal_id)
    if not state:
        yield "error", {"code": "NOT_FOUND", "message": "Proposal not found"}
        return
    prompt = _build_prompt(state)
    if feedback:
        prompt += f"\n\n사용자 피드백(재생성, 최우선 반영): {feedback}"
    async for ev in execute_stage(
        proposal_id, "TACTICAL", _SKILL, prompt,
        artifact_key="TacticalArtifact", parse_error_code="TACTICAL_PARSE_FAILED",
        validators=[(_has_min_invariants, "invariant 이 2개 미만인 Aggregate 가 있습니다")],
    ):
        yield ev
