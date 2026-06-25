from __future__ import annotations

import json

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from api.features.proposal_lifecycle.services.constitution_runner import (
    stream_constitution, get_constitution_response,
)
from api.features.proposal_lifecycle.proposal_contracts import ConstitutionAnswerRequest
from api.platform.observability.smart_logger import SmartLogger

router = APIRouter()

# 인터뷰 답변 누적(질문→답)을 메모리에 모았다가 다음 스트림에서 프롬프트로 전달.
_answer_log: dict[str, list[dict]] = {}


@router.get("/{proposal_id}/constitution")
async def get_constitution(proposal_id: str):
    """인터뷰 게이트용 얇은 상태({exists}). 보기/수정은 Design 쪽(/api/constitution)."""
    return get_constitution_response(proposal_id)


@router.get("/{proposal_id}/stream/constitution")
async def stream_constitution_sse(proposal_id: str):
    """Constitution 인터뷰(시드/추천/최소질문)를 SSE 로 스트리밍한다."""

    async def event_stream():
        async for event_type, data in stream_constitution(proposal_id):
            payload = json.dumps(data, ensure_ascii=False)
            yield f"event: {event_type}\ndata: {payload}\n\n"

    SmartLogger.log("INFO", f"SSE constitution stream started: {proposal_id}",
                    category="proposal_lifecycle.constitution.stream_start",
                    params={"proposalId": proposal_id})
    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.post("/{proposal_id}/constitution/answer")
async def answer_constitution(proposal_id: str, body: ConstitutionAnswerRequest):
    """인터뷰 질문에 대한 답을 기록한다(다음 스트림에서 반영)."""
    _answer_log.setdefault(proposal_id, []).append(
        {"questionIndex": body.questionIndex, "answer": body.answer}
    )
    return {"ok": True, "answered": len(_answer_log[proposal_id])}

# NOTE(041): 헌장 보기/수정 PUT 은 여기서 제거됨. 편집은 Design 쪽 /api/constitution
# (프로젝트 루트) 및 /api/bounded-contexts/{bcId}/constitution(BC 오버라이드)에서 한다.
