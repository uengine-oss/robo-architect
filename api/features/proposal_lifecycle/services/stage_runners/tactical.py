"""042 US2 — Tactical 스테이지(robo-proposal-tactical, extends ddd-starter 08 + plan 전술)."""

from __future__ import annotations

import json
from typing import AsyncGenerator

from api.features.proposal_lifecycle.services import staged_runner
from api.features.proposal_lifecycle.services.stage_runners.base import execute_stage
from api.features.proposal_lifecycle.services.legacy_evidence import (
    build_evidence_packet,
    evidence_prompt_block,
    gwt_evidence_ref_errors,
    tactical_evidence_ref_errors,
    ungrounded_gwt_values,
)

_SKILL = "robo-proposal-tactical"


def _build_prompt(state: dict) -> str:
    define = (state.get("stageArtifacts") or {}).get("DEFINE", {})
    packet = build_evidence_packet(state.get("legacyReferences"))
    story_ids = [
        story.get("id")
        for context in define.get("contexts") or []
        for story in context.get("userStories") or []
        if isinstance(story, dict) and story.get("id")
    ]
    return (
        "[TASK]\nDefine의 UserStory를 구현하는 Aggregate/Command/Event와 근거 기반 GWT를 생성한다.\n\n"
        f"[ORIGINAL REQUIREMENT]\n{state.get('prompt','')}\n\n"
        f"[DEFINE BCC + USER STORIES]\n{json.dumps(define, ensure_ascii=False)}\n\n"
        f"[ALLOWED USER STORY IDS]\n{json.dumps(story_ids, ensure_ascii=False)}\n"
        "각 Command.userStoryRefs는 위 ID 중 의미상 구현하는 항목을 1개 이상 사용한다. 새 ID를 만들지 않는다.\n\n"
        f"[INSPECTED LEGACY EVIDENCE — nodeId 중복 제거]\n{evidence_prompt_block(packet)}\n"
        "packet에 있는 nodeId는 재조회하지 않는다. 필요한 함수가 없거나 근거 상태가 부족할 때만 MCP로 갭을 조회한다.\n\n"
        "[DECISION RULES]\n"
        "- packet의 ordered_flow와 RULE condition/effects를 먼저 연결해 입력→검증→분기→CALL/RW→"
        "반환/상태변화→transaction 순서로 이해한다. semantic frame은 Analyzer가 검증한 최종 의미 근거이며 "
        "절대 줄 좌표와 missing_context로 구조의 모호함을 드러내고 profile 사실을 우선한다.\n"
        "- Then은 분기 중간 대입값이 아니라 공통 후처리·clamp·rollback/commit까지 적용한 최종 결과다. "
        "범위 조건만으로 최종 상수 반환을 일반화하지 않는다.\n"
        "- GWT fieldValues는 slot/profile RULE/실제 sample에 있는 필드와 값만 사용한다. 근거가 없으면 빈 맵이다.\n"
        "- 범위 조건을 보여주려고 대표 숫자/코드를 만들지 않는다. 실측 sample/RULE 상수가 없으면 "
        "조건은 name에 쓰고 fieldValues는 비운다. Command당 시나리오는 2~4개다.\n"
        "- 한 실제 필드의 여러 값은 합성 suffix 필드를 만들지 말고 별도 시나리오로 나눈다. "
        "이름 없는 반환값에 ret/result 필드도 만들지 않는다.\n"
        "- RET_INVALID/RET_FAIL 같은 함수 반환값을 cnt/status 등 다른 필드에 넣지 않는다. 동일 필드 "
        "대입 근거가 없으면 then.name으로만 반환을 표현한다.\n"
        "- 예시의 Pending/Requested 같은 설계 상태나 임의 날짜·건수·ID를 복사하지 않는다.\n"
        "- TABLE/COLUMN 이름은 번역하지 않고, 샘플 한 행을 제약이나 전체 분포로 일반화하지 않는다.\n"
        "- 반환 문자열의 괄호·공백·대소문자를 원문 그대로 보존한다.\n\n"
        "- 각 GWT scenario.evidenceRefs에 실제 사용한 exact evidence_id를 넣고 RULE을 최소 1개 포함한다. "
        "값·호출·TABLE sample을 사용하면 대응 SYMBOL/CALL/TABLE evidence_id도 함께 넣는다. 같은 함수의 "
        "다른 분기나 전체 원문을 포괄 근거처럼 인용하지 않는다.\n"
        "- 각 Command.legacyRefs에 근거 함수 nodeId, 그 함수의 실제 RULE evidenceId·ruleId·text 1개 이상, packet.tables의 "
        "직접 TABLE id 전부를 access에 맞는 reads/writes role로 붙인다. TABLE 이름을 바꾸지 않는다.\n\n"
        "각 Aggregate 에 대해 ddd-crew Aggregate Design Canvas(v1) 전 항목을 도출하라:\n"
        "- name, description(한 줄 책임), boundaryRationale(함께 변하는가/한 트랜잭션 일관성)\n"
        "- stateTransitions: [{from,to,trigger}]\n"
        "- invariants: Enforced Invariants(2개 이상)\n"
        "- correctivePolicies: 규칙 위반 시 보정 정책\n"
        "- handledCommands: 각 Command의 fields.inputSchema/properties/userStoryRefs/GWT(정상+경계·실패)\n"
        "- createdEvents: 각 Event의 fields.payload/properties\n"
        "- throughput: {commandHandlingRate:{avg,max}, totalClients:{avg,max}, concurrencyConflictChance:{avg,max}}\n"
        "- size: {eventGrowthRate:{avg,max}, lifetime:{avg,max}, eventsPersisted:{avg,max}}\n"
        "Aggregate 는 작게 유지하고 Value Object 는 Aggregate 로 모델링하지 마라.\n"
        '출력: {"TacticalArtifact": {"aggregates":[{"name":"...","description":"...","boundaryRationale":"...",'
        '"stateTransitions":[{"from":"...","to":"...","trigger":"..."}],"invariants":["...","..."],'
        '"correctivePolicies":["..."],"handledCommands":[{"name":"...","fields":{"inputSchema":{}},'
        '"properties":[],"userStoryRefs":["us:<allowed-id>"],"gwt":[{"scenario":"...",'
        '"evidenceRefs":["<exact RULE evidence_id>"],"given":{"name":"Aggregate: ...",'
        '"fieldValues":{}},"when":{"name":"Command: ...","fieldValues":{}},"then":{"name":"Event: ...",'
        '"fieldValues":{}}}],"legacyRefs":[]}],"createdEvents":[{"name":"...","fields":{"payload":{}},'
        '"properties":[],"legacyRefs":[]}],'
        '"throughput":{"commandHandlingRate":{"avg":"","max":""},"totalClients":{"avg":"","max":""},'
        '"concurrencyConflictChance":{"avg":"","max":""}},'
        '"size":{"eventGrowthRate":{"avg":"","max":""},"lifetime":{"avg":"","max":""},'
        '"eventsPersisted":{"avg":"","max":""}}}]}}'
    )


def _has_min_invariants(a: dict) -> bool:
    aggs = a.get("aggregates") or []
    return bool(aggs) and all(len(g.get("invariants") or []) >= 2 for g in aggs)


def _has_complete_commands(artifact: dict, allowed_story_ids: set[str]) -> bool:
    commands = [
        command
        for aggregate in artifact.get("aggregates") or []
        for command in aggregate.get("handledCommands") or []
        if isinstance(command, dict)
    ]
    if not commands:
        return False
    for command in commands:
        refs = command.get("userStoryRefs")
        if not isinstance(refs, list) or not refs or any(ref not in allowed_story_ids for ref in refs):
            return False
        scenarios = command.get("gwt")
        if not isinstance(scenarios, list) or not 2 <= len(scenarios) <= 4:
            return False
        for scenario in scenarios:
            if not isinstance(scenario, dict) or not scenario.get("scenario"):
                return False
            if not isinstance(scenario.get("evidenceRefs"), list) or not scenario["evidenceRefs"]:
                return False
            for phase in ("given", "when", "then"):
                value = scenario.get(phase)
                if not isinstance(value, dict) or not value.get("name"):
                    return False
                if not isinstance(value.get("fieldValues"), dict):
                    return False
    return True


async def stream(proposal_id: str, feedback: str = None) -> AsyncGenerator[tuple[str, object], None]:
    state = staged_runner.load_state(proposal_id)
    if not state:
        yield "error", {"code": "NOT_FOUND", "message": "Proposal not found"}
        return
    prompt = _build_prompt(state)
    allowed_story_ids = {
        story.get("id")
        for context in ((state.get("stageArtifacts") or {}).get("DEFINE", {}).get("contexts") or [])
        for story in context.get("userStories") or []
        if isinstance(story, dict) and story.get("id")
    }
    evidence_packet = build_evidence_packet(state.get("legacyReferences"))
    if feedback:
        prompt += f"\n\n사용자 피드백(재생성, 최우선 반영): {feedback}"
    async for ev in execute_stage(
        proposal_id, "TACTICAL", _SKILL, prompt,
        artifact_key="TacticalArtifact", parse_error_code="TACTICAL_PARSE_FAILED",
        validators=[(_has_min_invariants, "invariant 이 2개 미만인 Aggregate 가 있습니다")],
        blocking_validators=[(
            lambda artifact: _has_complete_commands(artifact, allowed_story_ids),
            "모든 Command에 허용된 userStoryRefs와 정상+경계/실패 구조화 GWT가 필요합니다",
        ), (
            lambda artifact: not gwt_evidence_ref_errors(
                [
                    {"nodeLabel": "Command", "nodeTitle": command.get("name"), **command}
                    for aggregate in artifact.get("aggregates") or []
                    for command in aggregate.get("handledCommands") or []
                    if isinstance(command, dict)
                ],
                evidence_packet,
            ),
            "각 GWT scenario가 정확한 RULE/사용 근거 evidenceRefs를 가져야 합니다",
        ), (
            lambda artifact: not ungrounded_gwt_values(
                [
                    {"nodeLabel": "Command", "nodeTitle": command.get("name"), **command}
                    for aggregate in artifact.get("aggregates") or []
                    for command in aggregate.get("handledCommands") or []
                    if isinstance(command, dict)
                ],
                evidence_packet,
                (state.get("stageArtifacts") or {}).get("DEFINE", {}),
            ),
            "GWT fieldValues에 실제 legacy evidence/Define 입력에 없는 scalar가 있습니다",
        ), (
            lambda artifact: not tactical_evidence_ref_errors(
                [
                    {"nodeLabel": "Command", "nodeTitle": command.get("name"), **command}
                    for aggregate in artifact.get("aggregates") or []
                    for command in aggregate.get("handledCommands") or []
                    if isinstance(command, dict)
                ],
                evidence_packet,
            ),
            "Command legacyRefs에 정확한 RULE 또는 직접 TABLE READ/WRITE 근거가 누락됐습니다",
        )],
    ):
        yield ev
