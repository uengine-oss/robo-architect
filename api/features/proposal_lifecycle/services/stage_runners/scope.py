"""042 US3 — 스코프 분류 → 스테이지 플랜(robo-proposal-scope).

원본 프롬프트 + 현재 도메인 노드 + 기존 전략 메모리를 입력으로,
어떤 DDD 스테이지가 적용/생략되는지(applies/recommendSkip/reason) 제안한다(FR-009).
"""

from __future__ import annotations

import json
from typing import AsyncGenerator

from api.platform.neo4j_helpers import load_domain_nodes
from api.features.constitution.services import constitution_store as cstore
from api.features.proposal_lifecycle.proposal_contracts import DDD_STAGE_ORDER
from api.features.proposal_lifecycle.services import staged_runner
from api.features.proposal_lifecycle.services.stage_runners.base import stream_skill_json

_SKILL = "robo-proposal-scope"


def _build_prompt(state: dict, domain_nodes: list[dict]) -> str:
    node_list = "\n".join(
        f"- id: {n['id']}, type: {n.get('label','')}, name: {n.get('name','')}"
        for n in (domain_nodes or [])[:120]
    )
    memory = cstore.get_project_strategic_memory() or {}
    return (
        f"원본 프롬프트(자연어 요구사항): {state.get('prompt','')}\n\n"
        f"현재 도메인 구성 요소 목록:\n{node_list or '(없음)'}\n\n"
        f"기존 전략 메모리(JSON):\n{json.dumps(memory, ensure_ascii=False)}\n\n"
        "이 Proposal 의 영향 범위를 분류하고, 아래 6개 DDD 스테이지 각각에 대해 "
        "적용/생략 권고와 한 줄 사유를 담은 stagePlan 을 JSON 으로 출력하라. "
        "규칙: 단일 BC 한정이면 cross-context(CONNECT, 다중 DECOMPOSE) 생략 권고, "
        "전략적 설계 변경만이면 TACTICAL 생략 권고, 마이크로/국지적이면 최소 경로 권고. "
        "단, DISCOVER 는 행위 변경이면 완전 생략을 권고하지 말 것(brief 확인은 허용).\n"
        f"스테이지: {', '.join(DDD_STAGE_ORDER)}\n"
        '출력: {"stagePlan": {"version":1, "classifiedReach":"...", '
        '"stages":[{"stage":"DISCOVER","applies":true,"recommendSkip":false,"reason":"..."}, ...]}}'
    )


def _fallback_plan() -> dict:
    """스킬 파싱 실패 시 안전한 풀-스테이지 플랜(아무 것도 생략 안 함)."""
    return {"version": 1, "classifiedReach": None,
            "stages": [{"stage": s, "applies": True, "recommendSkip": False,
                        "skipped": False, "reason": ""} for s in DDD_STAGE_ORDER]}


async def stream_scope(proposal_id: str) -> AsyncGenerator[tuple[str, object], None]:
    state = staged_runner.load_state(proposal_id)
    if not state:
        yield "error", {"code": "NOT_FOUND", "message": f"Proposal {proposal_id} not found"}
        return

    yield "phase", {"phase": "scope", "message": "범위 분류 및 스테이지 플랜 작성 중..."}
    staged_runner.log_stage(proposal_id, "SCOPE", "start")

    prompt = _build_prompt(state, load_domain_nodes())
    plan = None
    async for ev, data in stream_skill_json(_SKILL, prompt, "SCOPE_PARSE_FAILED"):
        if ev == "json":
            plan = data.get("stagePlan") if isinstance(data, dict) else None
        elif ev == "error":
            # 파싱 실패 시 풀 플랜으로 폴백(사용자가 직접 조정 가능).
            plan = _fallback_plan()
        else:
            yield ev, data

    if not plan or not plan.get("stages"):
        plan = _fallback_plan()
    # skipped 기본값 = recommendSkip(사용자가 확정 단계에서 뒤집을 수 있음).
    for item in plan.get("stages", []):
        item.setdefault("skipped", bool(item.get("recommendSkip")))

    yield "stage_plan", {"stagePlan": plan}
