"""040 — 미리보기 편집 라우트.

미리보기 설계 화면의 편집(Inspector 직접 / Chat 자연어)을 **Proposal.tacticalDiff** 에 반영한다.
라이브 디자인 그래프는 절대 변경하지 않는다(쓰기 대상은 :Proposal 노드 자기 속성뿐).
read-only 투영 모듈(proposals_preview.py)과 의도적으로 분리.
"""

from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from starlette.requests import Request

from api.features.proposal_lifecycle.services.preview_edit import (
    reconcile_aggregate_edit, apply_chat_drafts,
)
from api.platform.observability.request_logging import http_context
from api.platform.observability.smart_logger import SmartLogger

router = APIRouter()


class AggregateEditRequest(BaseModel):
    bcId: Optional[str] = None
    name: Optional[str] = None
    displayName: Optional[str] = None
    rootEntity: Optional[str] = None
    properties: Optional[list[dict]] = None
    enumerations: Optional[list[dict]] = None
    valueObjects: Optional[list[dict]] = None
    invariants: Optional[list[Any]] = None


class ChatConfirmRequest(BaseModel):
    bcId: Optional[str] = None
    drafts: list[dict] = Field(default_factory=list)
    approvedChangeIds: list[str] = Field(default_factory=list)


@router.put("/{proposal_id}/preview/aggregate/{node_id}")
async def edit_preview_aggregate(proposal_id: str, node_id: str, body: AggregateEditRequest, request: Request):
    """Inspector 직접 편집을 제안 diff 에 반영. 갱신된 미리보기 트리를 반환(즉시 재렌더)."""
    edited = body.model_dump(exclude_none=True)
    bc_id = edited.pop("bcId", None)
    try:
        tree = reconcile_aggregate_edit(proposal_id, node_id, bc_id, edited)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    SmartLogger.log(
        "INFO", "preview_edit_aggregate",
        category="proposal_lifecycle.preview.edit.aggregate",
        params={**http_context(request), "proposalId": proposal_id, "nodeId": node_id,
                "fields": list(edited.keys())},
    )
    return tree


@router.post("/{proposal_id}/preview/chat-confirm")
async def confirm_preview_chat(proposal_id: str, body: ChatConfirmRequest, request: Request):
    """Chat 수정 초안(승인분)을 제안 diff 에 반영(라이브 무관). 갱신된 미리보기 트리 반환."""
    try:
        tree = apply_chat_drafts(proposal_id, body.drafts, body.approvedChangeIds, body.bcId)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    SmartLogger.log(
        "INFO", "preview_edit_chat_confirm",
        category="proposal_lifecycle.preview.edit.chat",
        params={**http_context(request), "proposalId": proposal_id,
                "drafts": len(body.drafts), "approved": len(body.approvedChangeIds)},
    )
    return tree
