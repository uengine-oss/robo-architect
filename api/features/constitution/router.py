"""041 — Constitution 관리 API (Design 쪽). 프로젝트 루트 + BC별 오버라이드."""

from __future__ import annotations

from typing import Optional

import json

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from api.features.constitution.services import constitution_store as store
from api.features.constitution.services import constitution_interview as interview

router = APIRouter(tags=["constitution"])


class UpsertConstitutionRequest(BaseModel):
    raw: str
    fields: Optional[dict] = None
    strategicMemory: Optional[dict] = None   # 042


class ConstitutionAnswerRequest(BaseModel):
    field: Optional[str] = None
    questionIndex: Optional[int] = None
    answer: str


class UpsertBcConstitutionRequest(BaseModel):
    raw: Optional[str] = None
    fields: Optional[dict] = None
    strategicMemory: Optional[dict] = None   # 042


# --- 프로젝트 루트 헌장 ---

@router.get("/api/constitution")
async def get_project_constitution():
    c = store.get_project_constitution()
    if not c:
        return {"exists": False, "scope": "PROJECT"}
    return {"exists": True, **c}


@router.put("/api/constitution")
async def put_project_constitution(body: UpsertConstitutionRequest):
    h = store.upsert_project_constitution(body.raw, body.fields, body.strategicMemory)
    return {"constitutionHash": h}


@router.put("/api/constitution/strategic-memory")
async def put_project_strategic_memory(body: dict):
    """042 — 프로젝트 전략 메모리만 갱신(Design 쪽 편집). 수정 시 plan staleness 유발(FR-021)."""
    h = store.upsert_project_strategic_memory(body or {})
    return {"constitutionHash": h}


# 041 — 인터뷰로 프로젝트 루트 헌장 작성(Claude Code 스킬 호출, SSE). LLM 키 불필요.
# fresh=true 면 새 인터뷰(이전 세션 답변 초기화). 답변 후 이어가기는 fresh 생략.
@router.get("/api/constitution/stream")
async def stream_project_constitution(fresh: bool = False):
    if fresh:
        interview.reset_answers()

    async def event_stream():
        async for event_type, data in interview.stream_project_constitution():
            yield f"event: {event_type}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"
    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.post("/api/constitution/answer")
async def answer_project_constitution(body: ConstitutionAnswerRequest):
    # 게이팅 결정은 field 키로 누적한다(index 가 아니라).
    key = body.field or (f"q{body.questionIndex}" if body.questionIndex is not None else "")
    interview.record_answer(key, body.answer)
    return {"ok": True, "answers": interview.answers_snapshot()}


# --- 결정적 인터뷰 네비게이션(질문은 즉시; 스킬은 합성 단계에서만) ---

@router.post("/api/constitution/interview/start")
async def interview_start():
    interview.reset_answers()
    return {"question": interview.next_question(), "answers": {}}


# Plan 게이트 진입 — Claude Code 가 제안(proposal)을 먼저 분석해 추천을 만들고 첫 질문을
# 낸다(SSE, 진행 로그 포함). 이후 answer/stream 은 이 분석 컨텍스트(_recs/_proposal_ctx)를 쓴다.
@router.get("/api/constitution/interview/analyze")
async def interview_analyze(proposalId: str):
    interview.set_proposal_context(proposalId)

    async def event_stream():
        async for event_type, data in interview.analyze_proposal():
            yield f"event: {event_type}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"
    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.post("/api/constitution/interview/answer")
async def interview_answer(body: ConstitutionAnswerRequest):
    """답을 기록하고(상위 변경 시 하위 폐기) 다음 질문 또는 완료 신호를 반환."""
    interview.record_answer(body.field or "", body.answer)
    q = interview.next_question()
    return {"question": q, "complete": q is None, "answers": interview.answers_snapshot()}


@router.get("/api/constitution/interview/state")
async def interview_state():
    q = interview.next_question()
    return {"answers": interview.answers_snapshot(), "nextQuestion": q, "complete": q is None}


# --- BC별 오버라이드 헌장 + 유효(effective) 헌장 ---

@router.get("/api/bounded-contexts/{bc_id}/constitution")
async def get_bc_constitution(bc_id: str):
    return {
        "override": store.get_bc_override(bc_id),
        "effective": store.effective_for_bc(bc_id),
    }


@router.put("/api/bounded-contexts/{bc_id}/constitution")
async def put_bc_constitution(bc_id: str, body: UpsertBcConstitutionRequest):
    h = store.upsert_bc_override(bc_id, body.raw, body.fields)
    if body.strategicMemory is not None:
        store.upsert_bc_strategic_memory(bc_id, body.strategicMemory)
    return {"constitutionHash": h}


@router.delete("/api/bounded-contexts/{bc_id}/constitution")
async def delete_bc_constitution(bc_id: str):
    store.delete_bc_override(bc_id)
    return {"ok": True}
