"""042 US2/US6 — 스테이지 산출물 → 표준 Strategic/Tactical Diff 수렴(FR-007/FR-023).

Detailed walkthrough 의 산출물을 Simplified 모드와 동일한 strategicDiff/tacticalDiff 형태로
접어 넣어, 이후 impact/plan/tasks/implement 가 모드와 무관하게 동작하게 한다.
전술 정교화(아키텍처 결정 등)는 이후 기존 plan 단계가 수행한다 — 여기서는 형태 수렴만.
"""

from __future__ import annotations

import json
from typing import Optional

from api.platform.neo4j import get_session
from api.platform.observability.smart_logger import SmartLogger
from api.features.proposal_lifecycle.services import staged_runner


def _entry(op, entity_type, title, fields=None, acceptance=None):
    e = {"op": op, "entityType": entity_type, "entityId": None, "entityTitle": title}
    if fields:
        e["fields"] = fields
    if acceptance:
        e["acceptanceCriteria"] = acceptance
    return e


def consolidate(proposal_id: str) -> Optional[dict]:
    state = staged_runner.load_state(proposal_id)
    if not state:
        return {"reason": "not_found", "message": "Proposal not found"}

    arts = state.get("stageArtifacts") or {}
    if not arts:
        # Simplified 등 스테이지 산출물이 없으면 no-op(이미 strategicDiff 가 있음).
        return None

    # 기존 strategicDiff(업그레이드/시드된 경우)를 보존하고 BC(epics)만 보강.
    existing = state.get("strategic") or {}
    strategic = {
        "version": (existing.get("version", 1)),
        "epics": list(existing.get("epics", []) or []),
        "features": list(existing.get("features", []) or []),
        "userStories": list(existing.get("userStories", []) or []),
        "processes": list(existing.get("processes", []) or []),
    }
    seen_epics = {e.get("entityTitle") for e in strategic["epics"]}

    define = arts.get("DEFINE") or {}
    decompose = arts.get("DECOMPOSE") or {}
    strategize = arts.get("STRATEGIZE") or {}
    classif = {c.get("subDomain"): c.get("kind")
               for c in (strategize.get("classifications") or [])}

    # BoundedContext(=Epic): Define contexts 우선, 없으면 Decompose subDomains.
    bc_sources = define.get("contexts") or [
        {"name": s.get("name"), "purpose": s.get("responsibility")}
        for s in (decompose.get("subDomains") or [])
    ]
    for bc in bc_sources:
        title = bc.get("name")
        if not title or title in seen_epics:
            continue
        seen_epics.add(title)
        strategic["epics"].append(_entry(
            "CREATE", "BoundedContext", title,
            fields={"purpose": bc.get("purpose"),
                    "classification": bc.get("classification") or classif.get(title)},
        ))

    # Tactical artifact → tacticalDiff (Aggregate/Command/Event 시드).
    tactical_art = arts.get("TACTICAL") or {}
    tactical: list[dict] = []
    for agg in tactical_art.get("aggregates", []) or []:
        name = agg.get("name")
        if not name:
            continue
        tactical.append({"op": "CREATE", "entityType": "Aggregate", "entityTitle": name,
                         "fields": {"invariants": agg.get("invariants", []),
                                    "stateTransitions": agg.get("stateTransitions", [])}})
        for cmd in agg.get("handledCommands", []) or []:
            tactical.append({"op": "CREATE", "entityType": "Command", "entityTitle": cmd,
                             "fields": {"aggregate": name}})
        for evt in agg.get("createdEvents", []) or []:
            tactical.append({"op": "CREATE", "entityType": "Event", "entityTitle": evt,
                             "fields": {"aggregate": name}})

    # currentStage 는 오케스트레이터가 관리(전략 수렴 후엔 다음 전술 단계가 남아 있을 수 있음).
    # 전술이 비면(전략만 수렴) 기존 tacticalDiff 를 보존한다.
    set_parts = "p.strategicDiff=$sd"
    params = {"id": proposal_id, "sd": json.dumps(strategic, ensure_ascii=False)}
    if tactical:
        set_parts += ", p.tacticalDiff=$td"
        params["td"] = json.dumps(tactical, ensure_ascii=False)
    with get_session() as session:
        session.run(f"MATCH (p:Proposal {{id:$id}}) SET {set_parts}", **params)
    SmartLogger.log("INFO", f"staged consolidated: {proposal_id}",
                    category="proposal_lifecycle.staged.consolidate",
                    params={"proposalId": proposal_id,
                            "epics": len(strategic["epics"]), "tactical": len(tactical)})
    return None
