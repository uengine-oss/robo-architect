"""047 — 코드에서 요구사항 역추출(Reverse Intent) 라우트.

sources(분석 그래프 목록) + create(REVERSE_INTENT Proposal) + stream(SSE 역추출).
결과 strategicDiff 는 기존 Proposal 노드 속성에 저장 → 하류(plan/tasks/implement) 재사용.
analyzer 그래프는 읽기 전용(pipeline).
"""
from __future__ import annotations

import json
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from starlette.requests import Request

from api.features.proposal_lifecycle.proposal_contracts import (
    CreateReverseProposalRequest, ProposalResponse,
)
from api.features.proposal_lifecycle.services import reverse_source
from api.features.proposal_lifecycle.services.proposal_id_generator import next_proposal_id
from api.features.proposal_lifecycle.services.reverse_intent import pipeline
from api.platform.neo4j import get_session
from api.platform.observability.smart_logger import SmartLogger

router = APIRouter()


def _load_proposal(proposal_id: str) -> ProposalResponse:
    with get_session() as s:
        rec = s.run("MATCH (p:Proposal {id:$id}) RETURN p {.*} AS p", id=proposal_id).single()
    if not rec:
        raise HTTPException(status_code=404, detail="Proposal not found")
    return ProposalResponse.from_neo4j(rec["p"], [])


# --- 분석 그래프 목록 (FR-003) ---------------------------------------------

@router.get("/reverse/sources")
async def reverse_sources():
    return {"sources": reverse_source.list_sources()}


# --- 역추출 Proposal 생성 ---------------------------------------------------

@router.post("/reverse", response_model=ProposalResponse, status_code=201)
async def create_reverse_proposal(body: CreateReverseProposalRequest, request: Request):
    valid = {s["db"] for s in reverse_source.list_sources()}
    if not body.db or body.db not in valid:
        raise HTTPException(status_code=400, detail={
            "reason": "invalid_source",
            "message": f"'{body.db}' 는 분석된 그래프가 아닙니다."})

    proposal_id = next_proposal_id()
    actor = getattr(getattr(request.state, "actor", None), "email", "anonymous")
    created_at = datetime.now(timezone.utc)
    title = body.title or f"[역추출] {body.db}"

    with get_session() as s:
        s.run(
            """
            CREATE (p:Proposal {
                id: $id, title: $title, originalPrompt: $prompt, author: $author,
                createdAt: datetime($createdAt), status: 'DRAFT',
                statusHistory: '[]', clarificationLog: '[]',
                decompositionMode: 'REVERSE_INTENT', reverseScope: $scope
            })
            """,
            id=proposal_id, title=title, prompt=f"역방향 도출: {body.db}",
            author=actor, createdAt=created_at.isoformat(),
            scope=json.dumps({"db": body.db}, ensure_ascii=False),
        )
    SmartLogger.log("INFO", f"Reverse proposal created: {proposal_id} db={body.db}",
                    category="proposal_lifecycle.reverse.create",
                    params={"proposalId": proposal_id, "db": body.db})
    return _load_proposal(proposal_id)


# --- 역추출 실행(SSE) -------------------------------------------------------

def _save_strategic(proposal_id: str, strategic: dict) -> None:
    """최종 strategicDiff 를 Proposal 노드에 저장(+첫 UserStory 로 title 보정)."""
    title = None
    us = strategic.get("userStories") or []
    if us and isinstance(us[0], dict):
        title = us[0].get("entityTitle") or us[0].get("name")
    sd = json.dumps(strategic, ensure_ascii=False)
    with get_session() as s:
        if title:
            s.run("MATCH (p:Proposal {id:$id}) SET p.strategicDiff=$sd, p.title=$title",
                  id=proposal_id, sd=sd, title=title)
        else:
            s.run("MATCH (p:Proposal {id:$id}) SET p.strategicDiff=$sd", id=proposal_id, sd=sd)


def _proposal_db(proposal_id: str) -> str:
    """Proposal 의 reverseScope.db 를 반환(없으면 404/400)."""
    with get_session() as s:
        rec = s.run("MATCH (p:Proposal {id:$id}) RETURN p.reverseScope AS scope",
                    id=proposal_id).single()
    if not rec:
        raise HTTPException(status_code=404, detail="Proposal not found")
    try:
        scope = json.loads(rec["scope"]) if rec["scope"] else {}
    except Exception:
        scope = {}
    db = scope.get("db")
    if not db:
        raise HTTPException(status_code=400, detail="reverseScope.db 가 없습니다")
    return db


@router.get("/{proposal_id}/reverse/groups")
async def reverse_groups(proposal_id: str):
    """선택용 그룹 카드 미리보기(LLM 없이, FR-004)."""
    db = _proposal_db(proposal_id)
    try:
        return {"groups": pipeline.preview_groups(db)}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"그룹 미리보기 실패: {e}")


@router.get("/{proposal_id}/stream/reverse")
async def stream_reverse(proposal_id: str, groups: str | None = None):
    db = _proposal_db(proposal_id)
    # groups = 쉼표로 이은 선택 그룹 table 키(URL 인코딩). 없으면 전체(FR-005).
    selected = None
    if groups:
        from urllib.parse import unquote
        selected = [unquote(g) for g in groups.split(",") if g.strip()]

    async def event_stream():
        async for ev, data in pipeline.stream_reverse(db, selected):
            if ev == "strategic_diff":
                _save_strategic(proposal_id, data.get("strategicDiff") or {})
                yield f"event: strategic_diff\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"
                yield ("event: done\ndata: "
                       f"{json.dumps({'proposalId': proposal_id, 'status': 'DRAFT', 'nextStage': 'plan'}, ensure_ascii=False)}\n\n")
            else:
                yield f"event: {ev}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")
