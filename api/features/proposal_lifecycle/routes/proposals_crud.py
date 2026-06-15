from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from starlette.requests import Request

from pydantic import ValidationError

from api.features.proposal_lifecycle.proposal_contracts import (
    CreateProposalRequest,
    ProposalResponse,
    StrategicDiff,
    SubmitProposalRequest,
    AnswerClarificationRequest,
    UpdateDiffRequest,
    IntentFeedbackRequest,
    append_status_history,
    extract_title_from_prompt,
)
from api.features.proposal_lifecycle.services.proposal_id_generator import next_proposal_id
from api.platform.neo4j import get_session
from api.platform.observability.request_logging import http_context
from api.platform.observability.smart_logger import SmartLogger

router = APIRouter()


def _get_proposal_row(proposal_id: str) -> dict | None:
    with get_session() as session:
        result = session.run(
            "MATCH (p:Proposal {id: $id}) RETURN p {.*} AS p",
            id=proposal_id,
        )
        record = result.single()
    return record["p"] if record else None


def _parse_effects(raw_effects: list) -> list:
    items = []
    for e in raw_effects:
        if not e.get("nodeId"):
            continue
        items.append({
            "nodeId": str(e["nodeId"]),
            "nodeLabel": str(e.get("nodeLabel", "")),
            "nodeTitle": str(e.get("nodeTitle", "")),
            "reason": str(e.get("reason", "")),
            "impactLevel": e.get("impactLevel", "LOW"),
            "changeType": e.get("changeType", "MODIFY"),
        })
    return items


# ---------------------------------------------------------------------------
# POST /api/proposals/  — Proposal 생성
# ---------------------------------------------------------------------------

@router.post("/", response_model=ProposalResponse, status_code=201)
async def create_proposal(body: CreateProposalRequest, request: Request):
    """Proposal 생성 (DRAFT). 백그라운드에서 인텐트 분해 시작."""
    proposal_id = next_proposal_id()
    actor = getattr(getattr(request.state, "actor", None), "email", "anonymous")
    created_at = datetime.now(timezone.utc)
    auto_title = body.title or extract_title_from_prompt(body.originalPrompt)

    with get_session() as session:
        session.run(
            """
            CREATE (p:Proposal {
                id: $id,
                title: $title,
                originalPrompt: $originalPrompt,
                author: $author,
                createdAt: datetime($createdAt),
                status: 'DRAFT',
                statusHistory: '[]',
                clarificationLog: '[]'
            })
            """,
            id=proposal_id,
            title=auto_title,
            originalPrompt=body.originalPrompt,
            author=actor,
            createdAt=created_at.isoformat(),
        )

    SmartLogger.log("INFO", f"Proposal created: {proposal_id}",
                    category="proposal_lifecycle.create",
                    params={**http_context(request), "proposalId": proposal_id})

    row = _get_proposal_row(proposal_id)
    return ProposalResponse.from_neo4j(row, [])


# ---------------------------------------------------------------------------
# GET /api/proposals/  — 목록 조회
# ---------------------------------------------------------------------------

@router.get("/", response_model=list[ProposalResponse])
async def list_proposals(
    request: Request,
    status: Optional[list[str]] = Query(default=None),
    author: Optional[str] = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
):
    """Proposal 목록 조회 (상태·작성자 필터, 페이징)."""
    conditions = []
    params: dict = {"limit": limit, "offset": offset}

    if status:
        conditions.append("p.status IN $statuses")
        params["statuses"] = status
    if author:
        conditions.append("p.author = $author")
        params["author"] = author

    where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

    query = f"""
    MATCH (p:Proposal)
    {where_clause}
    RETURN p {{.*}} AS p
    ORDER BY p.createdAt DESC
    SKIP $offset LIMIT $limit
    """

    with get_session() as session:
        result = session.run(query, **params)
        rows = [r["p"] for r in result.data()]

    return [ProposalResponse.from_neo4j(r, []) for r in rows]


# ---------------------------------------------------------------------------
# GET /api/proposals/{id}  — 상세 조회
# ---------------------------------------------------------------------------

@router.get("/{proposal_id}", response_model=ProposalResponse)
async def get_proposal(proposal_id: str, request: Request):
    """Proposal 단건 조회 (EFFECT 포함)."""
    query = """
    MATCH (p:Proposal {id: $id})
    OPTIONAL MATCH (p)-[e:EFFECT]->(t)
    RETURN p {.*} AS p,
           collect({
               nodeId: t.id,
               nodeLabel: labels(t)[0],
               nodeTitle: COALESCE(t.title, t.name, t.action, ''),
               reason: e.reason,
               impactLevel: e.impactLevel,
               changeType: e.changeType
           }) AS effects
    """
    with get_session() as session:
        result = session.run(query, id=proposal_id)
        record = result.single()

    if not record:
        raise HTTPException(status_code=404, detail=f"Proposal {proposal_id} not found")

    return ProposalResponse.from_neo4j(record["p"], _parse_effects(record["effects"]))


# ---------------------------------------------------------------------------
# PUT /api/proposals/{id}/diff  — Diff 수정
# ---------------------------------------------------------------------------

def _validate_diff_payload(strategic: Optional[dict], tactical: Optional[list]) -> None:
    """직접 수정(JSON 편집)으로 들어온 diff 구조를 저장 전에 검증한다.

    깨진 strategicDiff 는 읽기 경로(ProposalResponse.from_neo4j)에서 조용히 None 으로
    소실되고, 깨진 tacticalDiff 항목은 dual-merge(proposal_apply)의 item.get(...) 에서
    크래시를 낸다. 둘 다 저장 자체를 422 로 막아 다운스트림을 보호한다.
    (tacticalDiff 의 'list of object' 는 요청 모델에서 이미 강제되지만, 명확한
    한국어 사유를 위해 항목 단위로도 한번 더 확인한다.)
    """
    if strategic is not None:
        try:
            StrategicDiff(**strategic)
        except ValidationError as e:
            err = e.errors()[0]
            loc = ".".join(str(x) for x in err.get("loc", ()))
            where = f" (위치: {loc})" if loc else ""
            raise HTTPException(status_code=422, detail=f"strategicDiff 형식 오류: {err.get('msg')}{where}")
    if tactical is not None:
        for i, item in enumerate(tactical):
            if not isinstance(item, dict):
                raise HTTPException(status_code=422, detail=f"tacticalDiff[{i}] 는 객체(JSON object)여야 합니다.")


@router.put("/{proposal_id}/diff", response_model=ProposalResponse)
async def update_diff(proposal_id: str, body: UpdateDiffRequest, request: Request):
    """Strategic/Tactical Diff 수동 수정."""
    row = _get_proposal_row(proposal_id)
    if not row:
        raise HTTPException(status_code=404, detail=f"Proposal {proposal_id} not found")
    if row.get("status") == "ACCEPTED":
        raise HTTPException(status_code=423, detail="ACCEPTED proposals cannot be modified.")

    # 깨진 구조가 저장돼 조용히 소실/크래시되는 것을 막는다(직접 수정 보완).
    _validate_diff_payload(body.strategicDiff, body.tacticalDiff)

    updates = {}
    if body.strategicDiff is not None:
        updates["strategicDiff"] = json.dumps(body.strategicDiff, ensure_ascii=False)
    if body.tacticalDiff is not None:
        updates["tacticalDiff"] = json.dumps(body.tacticalDiff, ensure_ascii=False)

    if updates:
        set_clause = ", ".join(f"p.{k} = ${k}" for k in updates)
        with get_session() as session:
            session.run(f"MATCH (p:Proposal {{id: $id}}) SET {set_clause}", id=proposal_id, **updates)

    updated = _get_proposal_row(proposal_id)
    return ProposalResponse.from_neo4j(updated, [])


# ---------------------------------------------------------------------------
# POST /api/proposals/{id}/clarify  — 명확화 답변
# ---------------------------------------------------------------------------

@router.post("/{proposal_id}/clarify", response_model=ProposalResponse)
async def answer_clarification(proposal_id: str, body: AnswerClarificationRequest, request: Request):
    """명확화 질문 답변 제출. intent_runner 재호출로 Diff 확정."""
    row = _get_proposal_row(proposal_id)
    if not row:
        raise HTTPException(status_code=404, detail=f"Proposal {proposal_id} not found")

    # clarificationLog에 답변 추가
    try:
        clog = json.loads(row.get("clarificationLog", "[]") or "[]")
    except Exception:
        clog = []

    for ans in body.answers:
        clog.append({"questionIndex": ans.questionIndex, "answer": ans.answer,
                     "at": datetime.now(timezone.utc).isoformat()})

    clog_str = json.dumps(clog, ensure_ascii=False)

    with get_session() as session:
        session.run(
            "MATCH (p:Proposal {id: $id}) SET p.clarificationLog = $clog",
            id=proposal_id, clog=clog_str,
        )

    # 백그라운드로 intent 재실행
    from api.features.proposal_lifecycle.services.intent_runner import run_intent_with_clarification
    asyncio.create_task(run_intent_with_clarification(proposal_id, body.answers))

    updated = _get_proposal_row(proposal_id)
    return ProposalResponse.from_neo4j(updated, [])


# ---------------------------------------------------------------------------
# POST /api/proposals/{id}/intent/feedback  — 인텐트 재생성용 피드백 등록
# ---------------------------------------------------------------------------

@router.post("/{proposal_id}/intent/feedback", response_model=ProposalResponse)
async def submit_intent_feedback(proposal_id: str, body: IntentFeedbackRequest, request: Request):
    """인텐트 분해 결과가 잘못됐을 때 보정 피드백을 등록한다(DRAFT 한정).

    저장만 하고 재분해는 트리거하지 않는다 — 프런트가 응답 후 인텐트 SSE를
    다시 구독하면 intent_runner가 이 피드백+이전 diff를 프롬프트에 실어 재생성한다.
    """
    feedback = (body.feedback or "").strip()
    if not feedback:
        raise HTTPException(status_code=400, detail="feedback must not be empty.")

    row = _get_proposal_row(proposal_id)
    if not row:
        raise HTTPException(status_code=404, detail=f"Proposal {proposal_id} not found")
    if row.get("status") != "DRAFT":
        raise HTTPException(
            status_code=409,
            detail=f"Intent can only be regenerated while DRAFT (current: {row.get('status')})",
        )

    try:
        flog = json.loads(row.get("intentFeedbackLog", "[]") or "[]")
    except Exception:
        flog = []
    flog.append({"feedback": feedback, "at": datetime.now(timezone.utc).isoformat()})

    with get_session() as session:
        session.run(
            "MATCH (p:Proposal {id: $id}) SET p.intentFeedbackLog = $flog",
            id=proposal_id, flog=json.dumps(flog, ensure_ascii=False),
        )

    SmartLogger.log("INFO", f"Intent feedback registered: {proposal_id}",
                    category="proposal_lifecycle.intent.feedback",
                    params={**http_context(request), "proposalId": proposal_id})

    updated = _get_proposal_row(proposal_id)
    return ProposalResponse.from_neo4j(updated, [])


# ---------------------------------------------------------------------------
# POST /api/proposals/{id}/submit  — DRAFT → SUBMITTED
# ---------------------------------------------------------------------------

@router.post("/{proposal_id}/submit", response_model=ProposalResponse)
async def submit_proposal(proposal_id: str, body: SubmitProposalRequest, request: Request):
    """DRAFT → SUBMITTED. Diff 없으면 400. 동일 노드 IMPLEMENTING 중이면 409."""
    row = _get_proposal_row(proposal_id)
    if not row:
        raise HTTPException(status_code=404, detail=f"Proposal {proposal_id} not found")
    if row.get("status") != "DRAFT":
        raise HTTPException(
            status_code=409,
            detail=f"Proposal must be DRAFT to submit (current: {row.get('status')})",
        )

    if not row.get("strategicDiff") and not row.get("tacticalDiff"):
        raise HTTPException(
            status_code=400,
            detail="strategicDiff or tacticalDiff must be set before submitting.",
        )

    # 충돌 감지: 동일 그래프 노드를 수정하는 IMPLEMENTING 중인 Proposal
    conflict_check = _check_concurrent_conflicts(proposal_id)
    if conflict_check:
        raise HTTPException(
            status_code=409,
            detail=f"Conflicting proposals in IMPLEMENTING state: {conflict_check}",
        )

    actor = getattr(getattr(request.state, "actor", None), "email", "anonymous")
    new_history = append_status_history(
        row.get("statusHistory", "[]"), "DRAFT", "SUBMITTED", actor
    )

    with get_session() as session:
        session.run(
            "MATCH (p:Proposal {id: $id}) SET p.status = 'SUBMITTED', p.statusHistory = $history",
            id=proposal_id, history=new_history,
        )

    SmartLogger.log("INFO", f"Proposal submitted: {proposal_id}",
                    category="proposal_lifecycle.submit",
                    params={**http_context(request), "proposalId": proposal_id})

    updated = _get_proposal_row(proposal_id)
    return ProposalResponse.from_neo4j(updated, [])


def _check_concurrent_conflicts(proposal_id: str) -> list[str]:
    """동일 노드를 수정하는 IMPLEMENTING 중인 Proposal ID 목록을 반환한다."""
    query = """
    MATCH (p:Proposal {id: $id})-[:EFFECT]->(n)
    MATCH (other:Proposal)-[:EFFECT]->(n)
    WHERE other.id <> $id AND other.status = 'IMPLEMENTING'
    RETURN DISTINCT other.id AS conflictId
    """
    with get_session() as session:
        result = session.run(query, id=proposal_id)
        return [r["conflictId"] for r in result.data()]
