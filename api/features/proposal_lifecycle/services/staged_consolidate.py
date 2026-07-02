"""042 US2/US6 — 스테이지 산출물 → 표준 Strategic/Tactical Diff 수렴.

Detailed DDD walkthrough 의 산출물을 이후 Plan/Impact/Accept 파이프라인이
공통으로 소비하는 Proposal diff 스키마로 정규화한다.
"""

from __future__ import annotations

import json
import re
from typing import Optional

from api.features.proposal_lifecycle.services import staged_runner
from api.features.proposal_lifecycle.services.proposal_ai_runner import (
    error_payload_from_result,
    run_validated_skill_once,
)
from api.features.proposal_lifecycle.services.proposal_ai_validation import (
    SkillScenario,
    retry_count_for_scenario,
    validate_strategic_output,
    validate_tactical_output,
)
from api.platform.neo4j import get_session
from api.platform.observability.smart_logger import SmartLogger


def _slug(text: str, fallback: str = "item") -> str:
    s = re.sub(r"[^a-zA-Z0-9가-힣]+", "-", (text or "").strip()).strip("-")
    return (s[:48] or fallback)


def _temp(prefix: str, name: str) -> str:
    return f"{prefix}:{_slug(name)}"


def _entry(op, entity_type, title, *, temp_id=None, fields=None, acceptance=None, **extra):
    e = {
        "op": op,
        "entityType": entity_type,
        "entityId": None,
        "entityTitle": title,
    }
    if temp_id:
        e["tempId"] = temp_id
    if fields:
        e["fields"] = fields
    if acceptance:
        e["acceptanceCriteria"] = acceptance
    e.update({k: v for k, v in extra.items() if v is not None})
    return e


def _stage_arts(state: dict) -> dict:
    arts = state.get("stageArtifacts") or {}
    # 사용자가 아직 confirm 하지 않은 마지막 실행 결과도 수렴 미리보기에서 사용할 수 있게 한다.
    draft = state.get("stageDraftArtifacts") or {}
    merged = dict(draft)
    merged.update(arts)
    return merged


def _context_sources(arts: dict) -> list[dict]:
    define = arts.get("DEFINE") or {}
    decompose = arts.get("DECOMPOSE") or {}
    strategize = arts.get("STRATEGIZE") or {}
    classif = {c.get("subDomain"): c.get("kind") for c in (strategize.get("classifications") or [])}

    contexts = define.get("contexts") or []
    if contexts:
        out = []
        for c in contexts:
            if c.get("name"):
                out.append({
                    "name": c.get("name"),
                    "purpose": c.get("purpose"),
                    "classification": c.get("classification") or classif.get(c.get("name")),
                    "source": c,
                })
        return out

    return [
        {
            "name": s.get("name"),
            "purpose": s.get("responsibility") or s.get("purpose"),
            "classification": classif.get(s.get("name")),
            "source": s,
        }
        for s in (decompose.get("subDomains") or [])
        if s.get("name")
    ]


def _parse_prompt_user_stories(prompt: str, contexts: list[dict]) -> list[dict]:
    stories = []
    for line in (prompt or "").splitlines():
        text = line.strip()
        if not text.startswith("-"):
            continue
        action = text.lstrip("-").strip()
        if not action:
            continue
        bc_name = _match_context(action, contexts)
        stories.append({
            "role": "고객",
            "action": action,
            "benefit": "온라인 쇼핑몰 주문 관리 목표를 달성한다",
            "bcName": bc_name,
        })
    return stories


def _match_context(text: str, contexts: list[dict]) -> str | None:
    names = [c.get("name") for c in contexts if c.get("name")]
    for name in names:
        if name and name in text:
            return name
    for name in names:
        if name and ("주문" in text and "주문" in name):
            return name
    return names[0] if names else None


def _build_strategic(state: dict, arts: dict) -> dict:
    existing = state.get("strategic") or {}
    strategic = {
        "version": existing.get("version", 1),
        "epics": list(existing.get("epics", []) or []),
        "features": list(existing.get("features", []) or []),
        "userStories": list(existing.get("userStories", []) or []),
        "processes": list(existing.get("processes", []) or []),
    }
    seen_epics = {e.get("entityTitle") for e in strategic["epics"]}
    seen_features = {e.get("entityTitle") for e in strategic["features"]}
    seen_stories = {e.get("entityTitle") for e in strategic["userStories"]}
    seen_processes = {e.get("entityTitle") for e in strategic["processes"]}

    contexts = _context_sources(arts)
    for bc in contexts:
        name = bc.get("name")
        if not name:
            continue
        bc_temp = _temp("bc", name)
        if name not in seen_epics:
            seen_epics.add(name)
            strategic["epics"].append(_entry(
                "CREATE",
                "BoundedContext",
                name,
                temp_id=bc_temp,
                fields={
                    "purpose": bc.get("purpose"),
                    "classification": bc.get("classification"),
                },
            ))

        feature_title = f"{name} 관리"
        feat_temp = _temp("feature", feature_title)
        if feature_title not in seen_features:
            seen_features.add(feature_title)
            strategic["features"].append(_entry(
                "CREATE",
                "Feature",
                feature_title,
                temp_id=feat_temp,
                epicId=bc_temp,
                boundedContextId=bc_temp,
                fields={"description": bc.get("purpose") or feature_title},
            ))

    for story in _parse_prompt_user_stories(state.get("prompt") or "", contexts):
        bc_name = story.get("bcName")
        if not bc_name:
            continue
        feature_title = f"{bc_name} 관리"
        title = f"{story['role']}: {story['action']}"
        if title in seen_stories:
            continue
        seen_stories.add(title)
        strategic["userStories"].append(_entry(
            "CREATE",
            "UserStory",
            title,
            temp_id=_temp("us", title),
            featureId=_temp("feature", feature_title),
            boundedContextId=_temp("bc", bc_name),
            role=story["role"],
            action=story["action"],
            benefit=story["benefit"],
            acceptance=[
                f"{story['action']} 시나리오가 성공한다",
                "실패/예외 상황은 사용자에게 명확히 전달된다",
            ],
            fields={
                "role": story["role"],
                "action": story["action"],
                "benefit": story["benefit"],
            },
        ))

    discover = arts.get("DISCOVER") or {}
    events = [e.get("name") for e in (discover.get("events") or []) if e.get("name")]
    if events:
        proc_title = "주문 관리 프로세스"
        if proc_title not in seen_processes:
            strategic["processes"].append(_entry(
                "CREATE",
                "Process",
                proc_title,
                temp_id=_temp("process", proc_title),
                fields={"description": " → ".join(events[:8])},
            ))

    return strategic


def _build_tactical(arts: dict) -> list[dict]:
    tactical_art = arts.get("TACTICAL") or {}
    contexts = _context_sources(arts)
    aggregate_to_bc = _aggregate_context_map(tactical_art, contexts)
    out: list[dict] = []

    for agg in tactical_art.get("aggregates", []) or []:
        name = agg.get("name")
        if not name:
            continue
        bc_name = aggregate_to_bc.get(name)
        agg_ref = _temp("agg", name)
        out.append(_tactical_item(
            "Aggregate",
            name,
            bounded_context=bc_name,
            temp_id=agg_ref,
            fields={
                "description": agg.get("description") or agg.get("boundaryRationale"),
                "stateTransitions": agg.get("stateTransitions", []),
            },
            invariants=agg.get("invariants", []),
            reason=f"{bc_name or '미지정 BC'}의 Aggregate 생성",
        ))

        for cmd in agg.get("handledCommands", []) or []:
            out.append(_tactical_item(
                "Command",
                cmd,
                bounded_context=bc_name,
                aggregate_id=agg_ref,
                temp_id=_temp("cmd", cmd),
                reason=f"{name} Aggregate가 처리하는 Command",
            ))
        first_cmd = (agg.get("handledCommands") or [None])[0]
        for evt in agg.get("createdEvents", []) or []:
            out.append(_tactical_item(
                "Event",
                evt,
                bounded_context=bc_name,
                command_id=_temp("cmd", first_cmd) if first_cmd else None,
                temp_id=_temp("evt", evt),
                reason=f"{name} Aggregate에서 발행되는 Event",
            ))

    _validate_tactical(out)
    return out


def _aggregate_context_map(tactical_art: dict, contexts: list[dict]) -> dict[str, str]:
    by_name = {}
    context_names = [c.get("name") for c in contexts if c.get("name")]
    for agg in tactical_art.get("aggregates", []) or []:
        name = agg.get("name")
        if not name:
            continue
        explicit = agg.get("boundedContextName") or agg.get("bcName") or agg.get("boundedContext") or agg.get("contextName")
        if explicit:
            by_name[name] = explicit
            agg.setdefault("bcName", explicit)
            continue
        matched = _match_context(name, contexts)
        if not matched and len(context_names) == 1:
            matched = context_names[0]
        by_name[name] = matched or "미지정 BC"
        agg.setdefault("bcName", by_name[name])
    return by_name


def _tactical_item(label: str, title: str, *, bounded_context=None, aggregate_id=None,
                   command_id=None, temp_id=None, fields=None, invariants=None, reason="") -> dict:
    item = {
        "changeType": "CREATE",
        "nodeLabel": label,
        "nodeTitle": title,
        "nodeId": temp_id,
        "impactLevel": "MEDIUM",
        "reason": reason,
        "semanticDiff": {"ops": []},
    }
    if bounded_context:
        item["boundedContextId"] = _temp("bc", bounded_context)
        item["boundedContextName"] = bounded_context
    if aggregate_id:
        item["aggregateId"] = aggregate_id
    if command_id:
        item["commandId"] = command_id
    if fields:
        item["fields"] = {k: v for k, v in fields.items() if v is not None}
    if invariants:
        item["invariants"] = [
            inv if isinstance(inv, dict) else {"declaration": str(inv)}
            for inv in invariants
            if inv
        ]
    return item


def _validate_tactical(items: list[dict]) -> None:
    required = ("nodeLabel", "nodeTitle", "changeType")
    for idx, item in enumerate(items):
        missing = [k for k in required if not item.get(k)]
        if missing:
            raise ValueError(f"tacticalDiff[{idx}] missing required fields: {', '.join(missing)}")


def _has_any(arts: dict, stages: tuple[str, ...]) -> bool:
    return any(isinstance(arts.get(stage), dict) and arts.get(stage) for stage in stages)


def _strategic_prompt(proposal_id: str, state: dict, arts: dict, feedback: str | None = None) -> str:
    selected = {stage: arts.get(stage) for stage in ("DISCOVER", "DECOMPOSE", "STRATEGIZE")}
    feedback_block = (
        "\n\n이전 Strategic Diff 산출물이 backend validator 계약 검증에 실패했습니다. "
        "아래 violation을 모두 수정해 같은 JSON 계약으로 다시 출력하세요.\n"
        f"{feedback}"
        if feedback else ""
    )
    return (
        f"Proposal ID: {proposal_id}\n"
        f"scenario: {SkillScenario.DETAILED_STRATEGIC_FROM_DDD.value}\n"
        f"원본 프롬프트:\n{state.get('prompt') or ''}\n\n"
        f"확정된 앞 3단계 DDD 산출물(JSON):\n```json\n{json.dumps(selected, ensure_ascii=False)}\n```\n\n"
        f"기존 Strategic Diff(JSON, 있으면 보존/보강):\n```json\n{json.dumps(state.get('strategic') or {}, ensure_ascii=False)}\n```\n\n"
        "Discover/Decompose/Strategize 산출물을 근거로 Strategic Diff를 생성하세요. "
        "최종 JSON은 {\"action\":\"done\",\"strategicDiff\":{...},\"journeys\":[...]} 형태여야 합니다. "
        "BoundedContext(=epics), Feature, UserStory, Process는 tempId와 부모 참조를 포함해야 합니다."
        f"{feedback_block}"
    )


def _tactical_prompt(proposal_id: str, state: dict, arts: dict, feedback: str | None = None) -> str:
    selected = {stage: arts.get(stage) for stage in ("CONNECT", "DEFINE", "TACTICAL")}
    feedback_block = (
        "\n\n이전 Tactical Diff 산출물이 backend validator 계약 검증에 실패했습니다. "
        "아래 violation을 모두 수정해 canonical tacticalDiff로 다시 출력하세요.\n"
        f"{feedback}"
        if feedback else ""
    )
    return (
        f"Proposal ID: {proposal_id}\n"
        f"scenario: {SkillScenario.DETAILED_TACTICAL_FROM_DDD.value}\n"
        f"원본 프롬프트:\n{state.get('prompt') or ''}\n\n"
        f"승인된 Strategic Diff(JSON):\n```json\n{json.dumps(state.get('strategic') or {}, ensure_ascii=False)}\n```\n\n"
        f"확정된 뒤 3단계 DDD 산출물(JSON):\n```json\n{json.dumps(selected, ensure_ascii=False)}\n```\n\n"
        "Connect/Define/Tactical 산출물의 메시지 흐름, Bounded Context Canvas, Aggregate 후보, "
        "이벤트, 정책, 속성 단서를 근거로 빈 노드 없는 Tactical Diff를 보강 생성하세요. "
        "최종 JSON은 {\"tacticalDiff\":[...]} 형태여야 하며 canonical field만 사용합니다."
        f"{feedback_block}"
    )


async def consolidate(proposal_id: str) -> Optional[dict]:
    state = staged_runner.load_state(proposal_id)
    if not state:
        return {"reason": "not_found", "message": "Proposal not found"}

    arts = _stage_arts(state)
    if not arts:
        return None

    updates: dict[str, str] = {}
    strategic = state.get("strategic") or {}
    if _has_any(arts, ("DISCOVER", "DECOMPOSE", "STRATEGIZE")):
        scenario = SkillScenario.DETAILED_STRATEGIC_FROM_DDD
        SmartLogger.log("INFO", f"staged strategic diff generation: {proposal_id}",
                        category="proposal_lifecycle.staged.consolidate.strategic_start",
                        params={"proposalId": proposal_id, "skillName": "robo-proposal",
                                "scenario": scenario.value,
                                "artifactStages": [s for s in ("DISCOVER", "DECOMPOSE", "STRATEGIZE") if arts.get(s)]})
        result = await run_validated_skill_once(
            skill_name="robo-proposal",
            prompt_builder=lambda feedback: _strategic_prompt(proposal_id, state, arts, feedback),
            validator=lambda raw: validate_strategic_output(raw, allow_clarify=False),
            proposal_id=proposal_id,
            scenario=scenario.value,
            max_retries=retry_count_for_scenario(scenario),
            parse_error_code="DETAILED_STRATEGIC_PARSE_FAILED",
            validation_error_code="DETAILED_STRATEGIC_CONTRACT_INVALID",
            timeout=900,
        )
        if not result.valid:
            return {
                "reason": "detailed_strategic_contract_invalid",
                **error_payload_from_result("DETAILED_STRATEGIC_CONTRACT_INVALID", result),
            }
        strategic = result.normalized_output.get("strategicDiff") or {}
        updates["strategicDiff"] = json.dumps(strategic, ensure_ascii=False)

    if _has_any(arts, ("CONNECT", "DEFINE", "TACTICAL")):
        scenario = SkillScenario.DETAILED_TACTICAL_FROM_DDD
        state_for_tactical = dict(state)
        state_for_tactical["strategic"] = strategic
        SmartLogger.log("INFO", f"staged tactical diff generation: {proposal_id}",
                        category="proposal_lifecycle.staged.consolidate.tactical_start",
                        params={"proposalId": proposal_id, "skillName": "robo-proposal",
                                "scenario": scenario.value,
                                "artifactStages": [s for s in ("CONNECT", "DEFINE", "TACTICAL") if arts.get(s)]})
        result = await run_validated_skill_once(
            skill_name="robo-proposal",
            prompt_builder=lambda feedback: _tactical_prompt(proposal_id, state_for_tactical, arts, feedback),
            validator=validate_tactical_output,
            proposal_id=proposal_id,
            scenario=scenario.value,
            max_retries=retry_count_for_scenario(scenario),
            parse_error_code="DETAILED_TACTICAL_PARSE_FAILED",
            validation_error_code="DETAILED_TACTICAL_CONTRACT_INVALID",
            timeout=900,
        )
        if not result.valid:
            return {
                "reason": "detailed_tactical_contract_invalid",
                **error_payload_from_result("DETAILED_TACTICAL_CONTRACT_INVALID", result),
            }
        updates["tacticalDiff"] = json.dumps(result.normalized_output.get("tacticalDiff") or [], ensure_ascii=False)

    if not updates:
        return None

    with get_session() as session:
        set_clause = ", ".join(f"p.{key}=${key}" for key in updates)
        session.run(f"MATCH (p:Proposal {{id:$id}}) SET {set_clause}", id=proposal_id, **updates)
    SmartLogger.log("INFO", f"staged consolidated: {proposal_id}",
                    category="proposal_lifecycle.staged.consolidate",
                    params={
                        "proposalId": proposal_id,
                        "skillName": "robo-proposal",
                        "updatedFields": list(updates.keys()),
                        "strategicArtifactStages": [s for s in ("DISCOVER", "DECOMPOSE", "STRATEGIZE") if arts.get(s)],
                        "tacticalArtifactStages": [s for s in ("CONNECT", "DEFINE", "TACTICAL") if arts.get(s)],
                    })
    return None
