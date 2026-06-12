from __future__ import annotations

import json
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException
from starlette.requests import Request

from api.features.requirement_changes.requirement_changes_contracts import (
    ApproveChangeRequest,
    ChangeResponse,
    ChangeStatus,
    RejectChangeRequest,
)
from api.platform.neo4j import get_session
from api.platform.observability.request_logging import http_context
from api.platform.observability.smart_logger import SmartLogger

router = APIRouter()


def _get_change_row(change_id: str) -> dict | None:
    with get_session() as session:
        result = session.run(
            "MATCH (n:RequirementChange {id: $id}) RETURN n {.*} AS n",
            id=change_id,
        )
        record = result.single()
    return record["n"] if record else None


def _is_self(row: dict, actor_email: str) -> bool:
    return row.get("author") == actor_email


def _check_self_approval(row: dict, actor) -> None:
    """자기 승인 검사. ProductOwner 역할이면 자기 승인 허용."""
    if _is_self(row, actor.email) and not actor.has_role("ProductOwner"):
        raise HTTPException(
            status_code=403,
            detail="자기 승인은 ProductOwner 권한이 있는 경우에만 가능합니다.",
        )


def _check_self_reject(row: dict, actor) -> None:
    """자기 반려 검사. ProductOwner 역할이면 자기 반려 허용."""
    if _is_self(row, actor.email) and not actor.has_role("ProductOwner"):
        raise HTTPException(
            status_code=403,
            detail="자기 반려는 ProductOwner 권한이 있는 경우에만 가능합니다.",
        )


def _append_status_history(change_id: str, from_status: str, to_status: str, actor: str, comment: str | None) -> None:
    row = _get_change_row(change_id)
    if not row:
        return
    try:
        hist = json.loads(row.get("statusHistory") or "[]")
    except Exception:
        hist = []
    hist.append({
        "fromStatus": from_status,
        "toStatus": to_status,
        "at": datetime.now(timezone.utc).isoformat(),
        "actor": actor,
        "comment": comment,
    })
    with get_session() as session:
        session.run(
            "MATCH (n:RequirementChange {id: $id}) SET n.status = $status, n.statusHistory = $hist",
            id=change_id,
            status=to_status,
            hist=json.dumps(hist),
        )


@router.post("/{change_id}/submit", response_model=ChangeResponse)
async def submit_change(change_id: str, request: Request):
    """DRAFT → SUBMITTED. 작성자 본인만 가능."""
    actor = getattr(getattr(request.state, "actor", None), "email", "anonymous")
    row = _get_change_row(change_id)
    if not row:
        raise HTTPException(status_code=404, detail=f"Change {change_id} not found")
    if row["status"] != ChangeStatus.DRAFT.value:
        raise HTTPException(status_code=400, detail=f"Change must be DRAFT to submit (current: {row['status']})")
    if row.get("author") != actor:
        raise HTTPException(status_code=403, detail="작성자 본인만 제출할 수 있습니다.")

    _append_status_history(change_id, "DRAFT", "SUBMITTED", actor, None)
    SmartLogger.log("INFO", f"Change submitted: {change_id}", category="requirement_changes.submit",
                    params={**http_context(request), "changeId": change_id, "actor": actor})
    return ChangeResponse.from_neo4j(_get_change_row(change_id), [])


@router.post("/{change_id}/approve", response_model=ChangeResponse)
async def approve_change(change_id: str, body: ApproveChangeRequest, request: Request):
    """SUBMITTED → PLAN_APPROVED (1차 승인). ProductOwner면 자기 승인 가능."""
    actor = getattr(request.state, "actor", None)
    actor_email = getattr(actor, "email", "anonymous")
    row = _get_change_row(change_id)
    if not row:
        raise HTTPException(status_code=404, detail=f"Change {change_id} not found")
    if row["status"] != ChangeStatus.SUBMITTED.value:
        raise HTTPException(
            status_code=400,
            detail=f"1차 승인은 SUBMITTED 상태에서만 가능합니다 (현재: {row['status']})",
        )
    _check_self_approval(row, actor)

    _append_status_history(change_id, "SUBMITTED", "PLAN_APPROVED", actor_email, body.comment)
    SmartLogger.log("INFO", f"Change plan approved (1st): {change_id}",
                    category="requirement_changes.approve.plan",
                    params={**http_context(request), "changeId": change_id, "actor": actor_email})
    return ChangeResponse.from_neo4j(_get_change_row(change_id), [])


@router.post("/{change_id}/approve-impl", response_model=ChangeResponse)
async def approve_impl(change_id: str, body: ApproveChangeRequest, request: Request):
    """DESIGN_APPLIED → APPROVED (2차 승인). ProductOwner면 자기 승인 가능."""
    actor = getattr(request.state, "actor", None)
    actor_email = getattr(actor, "email", "anonymous")
    row = _get_change_row(change_id)
    if not row:
        raise HTTPException(status_code=404, detail=f"Change {change_id} not found")
    if row["status"] != ChangeStatus.DESIGN_APPLIED.value:
        raise HTTPException(
            status_code=400,
            detail=f"2차 승인은 DESIGN_APPLIED 상태에서만 가능합니다 (현재: {row['status']})",
        )
    _check_self_approval(row, actor)

    _append_status_history(change_id, "DESIGN_APPLIED", "APPROVED", actor_email, body.comment)
    SmartLogger.log("INFO", f"Change impl approved (2nd): {change_id}",
                    category="requirement_changes.approve.impl",
                    params={**http_context(request), "changeId": change_id, "actor": actor_email})
    return ChangeResponse.from_neo4j(_get_change_row(change_id), [])


@router.post("/{change_id}/reject", response_model=ChangeResponse)
async def reject_change(change_id: str, body: RejectChangeRequest, request: Request):
    """SUBMITTED | DESIGN_APPLIED → REJECTED. ProductOwner면 자기 반려 가능."""
    actor = getattr(request.state, "actor", None)
    actor_email = getattr(actor, "email", "anonymous")
    row = _get_change_row(change_id)
    if not row:
        raise HTTPException(status_code=404, detail=f"Change {change_id} not found")

    rejectable = {ChangeStatus.SUBMITTED.value, ChangeStatus.DESIGN_APPLIED.value}
    if row["status"] not in rejectable:
        raise HTTPException(
            status_code=400,
            detail=f"반려는 SUBMITTED 또는 DESIGN_APPLIED 상태에서만 가능합니다 (현재: {row['status']})",
        )
    _check_self_reject(row, actor)

    _append_status_history(change_id, row["status"], "REJECTED", actor_email, body.comment)
    SmartLogger.log("INFO", f"Change rejected: {change_id}", category="requirement_changes.reject",
                    params={**http_context(request), "changeId": change_id, "actor": actor_email})
    return ChangeResponse.from_neo4j(_get_change_row(change_id), [])
