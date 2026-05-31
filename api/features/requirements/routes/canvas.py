"""Bounded Context Canvas & Aggregate Design Canvas (035 — US3/US5).

진실의 원천=그래프. GET=노드 속성/관계 투영, PATCH=속성만 SET(관계 보존) +
낙관적 버전(If-Match, contexts classification 패턴). 자동생성 초안은 기존
`ddd_spec`(`/api/ddd-spec/generate-bounded-context|generate-aggregate`)을 재사용한다.

문자열 리스트(domainRoles/ubiquitousLanguage/...)는 Neo4j의 native list<string>
속성으로 저장한다(신규 노드 라벨/관계 0건).
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Header, HTTPException
from starlette.requests import Request

from api.features.requirements.requirements_contracts import (
    AggregateCanvasDTO,
    AggregateCanvasPatchRequest,
    BcCanvasDTO,
    BcCanvasPatchRequest,
    BcMessageFlow,
)
from api.platform.neo4j import get_session
from api.platform.observability.request_logging import http_context
from api.platform.observability.smart_logger import SmartLogger

router = APIRouter()


def _as_list(value) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(v) for v in value]
    return [str(value)]


def _check_version(if_match: Optional[str], actual: int) -> None:
    if if_match is None:
        return
    try:
        expected = int(if_match)
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="If-Match header must be an integer version")
    if expected != actual:
        raise HTTPException(
            status_code=412,
            detail={"code": "VERSION_MISMATCH", "expected": expected, "actual": actual},
        )


# ── Bounded Context Canvas (US3) ─────────────────────────────────────────


@router.get("/bounded-context/{bc_id}/canvas", response_model=BcCanvasDTO)
async def get_bc_canvas(bc_id: str, request: Request) -> BcCanvasDTO:
    """BC 노드 속성/관계를 캔버스 뷰로 투영한다."""
    query = """
    MATCH (bc:BoundedContext {id: $id})
    RETURN bc.id AS id, coalesce(bc.displayName, bc.name) AS name,
           bc.purpose AS purpose, bc.classification AS classification,
           bc.domainRoles AS domainRoles, bc.ubiquitousLanguage AS ubiquitousLanguage,
           bc.businessDecisions AS businessDecisions, bc.assumptions AS assumptions,
           coalesce(bc.version, 0) AS version
    """
    with get_session() as session:
        rec = session.run(query, id=bc_id).single()
        if not rec:
            raise HTTPException(status_code=404, detail=f"Bounded context {bc_id} not found")
        # 아웃바운드: 이 BC의 Command가 발행한 Event를 다른 BC의 Policy가 소비(TRIGGERED_BY).
        out_rows = session.run(
            """
            MATCH (bc:BoundedContext {id:$id})-[:HAS_AGGREGATE]->(:Aggregate)
                  -[:HAS_COMMAND]->(:Command)-[:EMITS]->(e:Event)
            OPTIONAL MATCH (e)<-[:TRIGGERED_BY]-(p:Policy)<-[:HAS_POLICY]-(obc:BoundedContext)
            WHERE obc.id <> $id
            RETURN coalesce(obc.displayName, obc.name) AS other,
                   coalesce(e.displayName, e.name) AS msg
            LIMIT 50
            """,
            id=bc_id,
        )
        outbound = [
            BcMessageFlow(otherBcName=r["other"] or "", message=r["msg"] or "")
            for r in out_rows
            if r["other"]
        ]

    return BcCanvasDTO(
        bcId=rec["id"],
        name=rec["name"] or "",
        purpose=rec["purpose"],
        classification=rec["classification"],
        domainRoles=_as_list(rec["domainRoles"]),
        ubiquitousLanguage=_as_list(rec["ubiquitousLanguage"]),
        businessDecisions=_as_list(rec["businessDecisions"]),
        assumptions=_as_list(rec["assumptions"]),
        inbound=[],
        outbound=outbound,
        version=int(rec["version"] or 0),
    )


@router.patch("/bounded-context/{bc_id}/canvas", response_model=BcCanvasDTO)
async def patch_bc_canvas(
    bc_id: str,
    req: BcCanvasPatchRequest,
    request: Request,
    if_match: Optional[str] = Header(default=None, alias="If-Match"),
) -> BcCanvasDTO:
    """BC 캔버스 속성만 갱신(관계 보존) + 버전 증가."""
    with get_session() as session:
        cur = session.run(
            "MATCH (bc:BoundedContext {id:$id}) RETURN coalesce(bc.version,0) AS v", id=bc_id
        ).single()
        if not cur:
            raise HTTPException(status_code=404, detail=f"Bounded context {bc_id} not found")
        _check_version(if_match, int(cur["v"] or 0))

        sets = ["bc.version = coalesce(bc.version, 0) + 1"]
        params: dict = {"id": bc_id}
        for field in ("purpose", "domainRoles", "ubiquitousLanguage", "businessDecisions", "assumptions"):
            val = getattr(req, field)
            if val is not None:
                sets.append(f"bc.{field} = ${field}")
                params[field] = val
        session.run(f"MATCH (bc:BoundedContext {{id:$id}}) SET {', '.join(sets)}", **params)

    SmartLogger.log(
        "INFO",
        "BC canvas updated.",
        category="requirements.bc_canvas.patch",
        params={**http_context(request), "bc_id": bc_id},
    )
    return await get_bc_canvas(bc_id, request)


# ── Aggregate Design Canvas (US5) ────────────────────────────────────────


@router.get("/aggregate/{aggregate_id}/canvas", response_model=AggregateCanvasDTO)
async def get_aggregate_canvas(aggregate_id: str, request: Request) -> AggregateCanvasDTO:
    """Aggregate 노드 속성/관계를 캔버스 뷰로 투영한다."""
    query = """
    MATCH (a:Aggregate {id: $id})
    OPTIONAL MATCH (a)-[:HAS_COMMAND]->(c:Command)
    OPTIONAL MATCH (c)-[:EMITS]->(e:Event)
    OPTIONAL MATCH (a)-[:HAS_INVARIANT]->(i:Invariant)
    RETURN coalesce(a.displayName, a.name) AS name, a.description AS description,
           a.stateTransitions AS stateTransitions, a.correctivePolicies AS correctivePolicies,
           a.throughput AS throughput, a.invariants AS invProp,
           coalesce(a.version, 0) AS version,
           collect(DISTINCT coalesce(c.displayName, c.name)) AS commands,
           collect(DISTINCT coalesce(e.displayName, e.name)) AS events,
           collect(DISTINCT coalesce(i.name, i.description)) AS invNodes
    """
    with get_session() as session:
        rec = session.run(query, id=aggregate_id).single()
    if not rec:
        raise HTTPException(status_code=404, detail=f"Aggregate {aggregate_id} not found")

    invariants = [x for x in (rec["invNodes"] or []) if x] or _as_list(rec["invProp"])
    return AggregateCanvasDTO(
        aggregateId=aggregate_id,
        name=rec["name"] or "",
        description=rec["description"],
        stateTransitions=rec["stateTransitions"],
        commands=[c for c in (rec["commands"] or []) if c],
        events=[e for e in (rec["events"] or []) if e],
        invariants=invariants,
        correctivePolicies=_as_list(rec["correctivePolicies"]),
        throughput=rec["throughput"],
        version=int(rec["version"] or 0),
    )


@router.patch("/aggregate/{aggregate_id}/canvas", response_model=AggregateCanvasDTO)
async def patch_aggregate_canvas(
    aggregate_id: str,
    req: AggregateCanvasPatchRequest,
    request: Request,
    if_match: Optional[str] = Header(default=None, alias="If-Match"),
) -> AggregateCanvasDTO:
    """Aggregate 캔버스 속성만 갱신(관계 보존) + 버전 증가."""
    with get_session() as session:
        cur = session.run(
            "MATCH (a:Aggregate {id:$id}) RETURN coalesce(a.version,0) AS v", id=aggregate_id
        ).single()
        if not cur:
            raise HTTPException(status_code=404, detail=f"Aggregate {aggregate_id} not found")
        _check_version(if_match, int(cur["v"] or 0))

        sets = ["a.version = coalesce(a.version, 0) + 1"]
        params: dict = {"id": aggregate_id}
        for field in ("description", "stateTransitions", "correctivePolicies", "throughput", "invariants"):
            val = getattr(req, field)
            if val is not None:
                sets.append(f"a.{field} = ${field}")
                params[field] = val
        session.run(f"MATCH (a:Aggregate {{id:$id}}) SET {', '.join(sets)}", **params)

    SmartLogger.log(
        "INFO",
        "Aggregate canvas updated.",
        category="requirements.aggregate_canvas.patch",
        params={**http_context(request), "aggregate_id": aggregate_id},
    )
    return await get_aggregate_canvas(aggregate_id, request)
