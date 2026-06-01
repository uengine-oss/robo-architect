"""피보탈 이벤트 / 핫스팟 토글 + 서브도메인 제안 (035 — US2).

기존 Event 노드에 `pivotal`/`hotspot` 불리언 속성을 추가(신규 라벨/관계 0건).
피보탈 이벤트를 경계로 서브도메인(BC 후보)을 제안한다 — 확정은 기존
`POST /api/requirements/bounded-context`(bounded_context_crud)가 담당한다.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from starlette.requests import Request

from api.features.requirements.requirements_contracts import (
    PivotalToggleRequest,
    PivotalToggleResponse,
    SubdomainProposal,
    SubdomainProposeResponse,
)
from api.platform.neo4j import get_session
from api.platform.observability.request_logging import http_context
from api.platform.observability.smart_logger import SmartLogger

router = APIRouter()


@router.post("/pivotal-events/toggle", response_model=PivotalToggleResponse)
async def toggle_pivotal(req: PivotalToggleRequest, request: Request) -> PivotalToggleResponse:
    """Event 노드의 pivotal/hotspot 플래그를 설정한다(부분 갱신)."""
    sets = []
    params: dict = {"id": req.eventId}
    if req.pivotal is not None:
        sets.append("e.pivotal = $pivotal")
        params["pivotal"] = req.pivotal
    if req.hotspot is not None:
        sets.append("e.hotspot = $hotspot")
        params["hotspot"] = req.hotspot
    if not sets:
        raise HTTPException(status_code=422, detail="pivotal 또는 hotspot 중 하나는 지정해야 합니다.")

    query = (
        "MATCH (e:Event {id: $id}) SET "
        + ", ".join(sets)
        + " RETURN coalesce(e.pivotal, false) AS pivotal, coalesce(e.hotspot, false) AS hotspot"
    )
    with get_session() as session:
        rec = session.run(query, **params).single()
    if not rec:
        raise HTTPException(status_code=404, detail=f"Event {req.eventId} not found")

    SmartLogger.log(
        "INFO",
        "Event pivotal/hotspot toggled.",
        category="requirements.pivotal.toggle",
        params={**http_context(request), "event_id": req.eventId,
                "pivotal": rec["pivotal"], "hotspot": rec["hotspot"]},
    )
    return PivotalToggleResponse(eventId=req.eventId, pivotal=rec["pivotal"], hotspot=rec["hotspot"])


@router.get("/pivotal-events/subdomains/propose", response_model=SubdomainProposeResponse)
async def propose_subdomains(request: Request) -> SubdomainProposeResponse:
    """피보탈 이벤트를 경계로 서브도메인(BC 후보)을 제안한다.

    피보탈 이벤트가 없으면 빈 제안을 반환한다. 시퀀스(`sequence`) 순으로 이벤트를
    정렬하고, 피보탈 이벤트 직후를 새 그룹의 시작으로 보아 경계를 자른다.
    """
    query = """
    MATCH (e:Event)
    RETURN e.id AS id, coalesce(e.displayName, e.name) AS name,
           coalesce(e.sequence, 0) AS seq, coalesce(e.pivotal, false) AS pivotal
    ORDER BY seq, name
    """
    with get_session() as session:
        rows = [dict(r) for r in session.run(query)]

    if not any(r["pivotal"] for r in rows):
        return SubdomainProposeResponse(proposals=[])

    # 피보탈 이벤트를 경계로 그룹핑: 피보탈 이벤트는 그 그룹의 마지막으로 본다.
    groups: list[list[dict]] = []
    current: list[dict] = []
    for r in rows:
        current.append(r)
        if r["pivotal"]:
            groups.append(current)
            current = []
    if current:
        groups.append(current)

    proposals = []
    for idx, grp in enumerate(groups, start=1):
        anchor = next((g for g in reversed(grp) if g["pivotal"]), grp[-1])
        proposals.append(
            SubdomainProposal(
                name=f"{anchor['name']} 영역",
                responsibility=f"'{anchor['name']}'까지의 흐름을 책임지는 서브도메인 후보",
                eventIds=[g["id"] for g in grp],
                suggestedClassification="core" if idx == 1 else "supporting",
            )
        )

    SmartLogger.log(
        "INFO",
        f"Proposed {len(proposals)} subdomains from pivotal boundaries.",
        category="requirements.pivotal.subdomains",
        params={**http_context(request), "count": len(proposals)},
    )
    return SubdomainProposeResponse(proposals=proposals)
