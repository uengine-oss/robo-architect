"""042 US2/US6 — 스테이지 산출물 → 표준 Strategic/Tactical Diff 수렴.

Detailed DDD walkthrough 의 산출물을 이후 Plan/Impact/Accept 파이프라인이
공통으로 소비하는 Proposal diff 스키마로 정규화한다.
"""

from __future__ import annotations

import json
import re
from typing import Optional

from api.platform.neo4j import get_session
from api.platform.observability.smart_logger import SmartLogger
from api.features.proposal_lifecycle.services import staged_runner


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


def _refs(*sources) -> list[dict] | None:
    """스테이지 산출물 요소들이 실어온 legacyRefs 를 nodeId 기준 dedupe 해 합친다.

    수렴이 요소를 재구성하며 근거를 떨어뜨리지 않기 위한 운반 헬퍼(evlink SPEC2 T2-1).
    근거가 하나도 없으면 None — 키를 생략해 저장 관문(enforce)의 REFS_MISSING 폴백에
    맡긴다(스킬 계약 미확장 산출물과의 호환).
    """
    merged: list[dict] = []
    seen: set[str] = set()
    for source in sources:
        refs = source.get("legacyRefs") if isinstance(source, dict) else None
        if not isinstance(refs, list):
            continue
        for ref in refs:
            if isinstance(ref, str):
                ref = {"nodeId": ref}
            node_id = ref.get("nodeId") if isinstance(ref, dict) else None
            if node_id and node_id not in seen:
                seen.add(node_id)
                merged.append(ref)
    return merged or None


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
        bc_refs = _refs(bc, bc.get("source"))
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
                legacyRefs=bc_refs,
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
                legacyRefs=bc_refs,
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
    discover_events = [e for e in (discover.get("events") or []) if isinstance(e, dict) and e.get("name")]
    events = [e.get("name") for e in discover_events]
    if events:
        proc_title = "주문 관리 프로세스"
        if proc_title not in seen_processes:
            strategic["processes"].append(_entry(
                "CREATE",
                "Process",
                proc_title,
                temp_id=_temp("process", proc_title),
                fields={"description": " → ".join(events[:8])},
                legacyRefs=_refs(*discover_events),
            ))

    return strategic


def _build_tactical(arts: dict) -> list[dict]:
    tactical_art = arts.get("TACTICAL") or {}
    contexts = _context_sources(arts)
    aggregate_to_bc = _aggregate_context_map(tactical_art, contexts)
    out: list[dict] = []

    def _named(value):
        """스킬 산출물의 Command/Event 는 이름 문자열 또는 {name, legacyRefs} 객체 양쪽을 수용."""
        if isinstance(value, dict):
            return value.get("name"), value
        return value, None

    for agg in tactical_art.get("aggregates", []) or []:
        name = agg.get("name")
        if not name:
            continue
        bc_name = aggregate_to_bc.get(name)
        agg_ref = _temp("agg", name)
        agg_refs = _refs(agg)
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
            legacy_refs=agg_refs,
        ))

        for cmd in agg.get("handledCommands", []) or []:
            cmd_name, cmd_src = _named(cmd)
            if not cmd_name:
                continue
            out.append(_tactical_item(
                "Command",
                cmd_name,
                bounded_context=bc_name,
                aggregate_id=agg_ref,
                temp_id=_temp("cmd", cmd_name),
                reason=f"{name} Aggregate가 처리하는 Command",
                legacy_refs=_refs(cmd_src) if cmd_src else None,
            ))
        first_cmd, _ = _named((agg.get("handledCommands") or [None])[0])
        for evt in agg.get("createdEvents", []) or []:
            evt_name, evt_src = _named(evt)
            if not evt_name:
                continue
            out.append(_tactical_item(
                "Event",
                evt_name,
                bounded_context=bc_name,
                command_id=_temp("cmd", first_cmd) if first_cmd else None,
                temp_id=_temp("evt", evt_name),
                reason=f"{name} Aggregate에서 발행되는 Event",
                legacy_refs=_refs(evt_src) if evt_src else None,
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
                   command_id=None, temp_id=None, fields=None, invariants=None, reason="",
                   legacy_refs=None) -> dict:
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
    if legacy_refs:
        item["legacyRefs"] = legacy_refs
    return item


def _validate_tactical(items: list[dict]) -> None:
    required = ("nodeLabel", "nodeTitle", "changeType")
    for idx, item in enumerate(items):
        missing = [k for k in required if not item.get(k)]
        if missing:
            raise ValueError(f"tacticalDiff[{idx}] missing required fields: {', '.join(missing)}")


def consolidate(proposal_id: str) -> Optional[dict]:
    state = staged_runner.load_state(proposal_id)
    if not state:
        return {"reason": "not_found", "message": "Proposal not found"}

    arts = _stage_arts(state)
    if not arts:
        return None

    try:
        strategic = _build_strategic(state, arts)
        tactical = _build_tactical(arts)
    except ValueError as e:
        return {"reason": "invalid_staged_diff", "message": str(e)}

    # evlink: Detailed DDD 수렴 저장도 legacyRefs 관문을 지난다.
    from api.features.proposal_lifecycle.services.legacy_element_refs import enforce_proposal_refs
    enforce_proposal_refs(proposal_id, strategic_diff=strategic, tactical_diff=tactical)

    with get_session() as session:
        session.run(
            """
            MATCH (p:Proposal {id:$id})
            SET p.strategicDiff=$sd,
                p.tacticalDiff=$td
            """,
            id=proposal_id,
            sd=json.dumps(strategic, ensure_ascii=False),
            td=json.dumps(tactical, ensure_ascii=False),
        )
    SmartLogger.log("INFO", f"staged consolidated: {proposal_id}",
                    category="proposal_lifecycle.staged.consolidate",
                    params={
                        "proposalId": proposal_id,
                        "epics": len(strategic["epics"]),
                        "features": len(strategic["features"]),
                        "userStories": len(strategic["userStories"]),
                        "processes": len(strategic["processes"]),
                        "tactical": len(tactical),
                    })
    return None
