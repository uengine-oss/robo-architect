from __future__ import annotations

import json

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from starlette.requests import Request

from api.features.proposal_lifecycle.proposal_contracts import (
    AcceptProposalRequest,
    DestroyProposalRequest,
    RevokeProposalRequest,
    ProposalResponse,
    append_status_history,
)
from api.features.proposal_lifecycle.services.dual_merge import execute_dual_merge, execute_revoke
from api.features.proposal_lifecycle.services.sandbox_manager import SandboxManager
from api.platform.neo4j import get_session
from api.platform.observability.request_logging import http_context
from api.platform.observability.smart_logger import SmartLogger

router = APIRouter()

_sandbox = SandboxManager()


def _actor_role(request: Request) -> str:
    """현재 actor의 역할. 인증 미들웨어가 역할을 싣지 않으면 **기본 PO**로 간주한다.
    (정책: 기본적으로 PO 역할 부여 — 자기 자신이 작성한 Proposal도 Accept 가능.)
    """
    role = getattr(getattr(request.state, "actor", None), "role", None)
    return role or "PO"


def _get_proposal_row(proposal_id: str) -> dict | None:
    with get_session() as session:
        result = session.run(
            "MATCH (p:Proposal {id: $id}) RETURN p {.*} AS p",
            id=proposal_id,
        )
        record = result.single()
    return record["p"] if record else None


@router.post("/{proposal_id}/accept", response_model=ProposalResponse)
async def accept_proposal(proposal_id: str, body: AcceptProposalRequest, request: Request):
    """PO Accept → Dual Merge 실행."""
    row = _get_proposal_row(proposal_id)
    if not row:
        raise HTTPException(status_code=404, detail=f"Proposal {proposal_id} not found")

    actor = getattr(getattr(request.state, "actor", None), "email", "anonymous")

    # Accept 권한: PO 역할 필요. 인증·역할 시스템 미도입 상태에서는 actor를 기본 PO로
    # 간주한다(기본 PO 정책). PO는 본인이 작성한 Proposal도 Accept할 수 있다(자기 승인 허용).
    if _actor_role(request) != "PO":
        raise HTTPException(status_code=403, detail="Accept 권한이 없습니다. PO 역할이 필요합니다.")

    # 검증을 통과·완료하지 않았더라도, 구현이 완료(TESTING)되었으면 PO가 Accept를
    # 결정할 수 있다. PENDING_ACCEPTANCE는 검증까지 마친 정상 흐름.
    if row.get("status") not in ("TESTING", "PENDING_ACCEPTANCE"):
        raise HTTPException(
            status_code=409,
            detail=f"Proposal must be TESTING or PENDING_ACCEPTANCE to accept (current: {row.get('status')})",
        )

    # 테스트 실패 항목 확인
    if not body.forceAcceptWithFailures:
        raw_test = row.get("testResults")
        if raw_test:
            try:
                test_data = json.loads(raw_test) if isinstance(raw_test, str) else raw_test
                if test_data.get("failed", 0) > 0:
                    raise HTTPException(
                        status_code=400,
                        detail=f"{test_data['failed']} test(s) failed. Set forceAcceptWithFailures=true to override.",
                    )
            except HTTPException:
                raise
            except Exception:
                pass

    SmartLogger.log("INFO", f"Accept started: {proposal_id}",
                    category="proposal_lifecycle.accept.start",
                    params={**http_context(request), "proposalId": proposal_id})

    try:
        await execute_dual_merge(proposal_id, actor, comment=body.comment)
    except Exception as e:
        SmartLogger.log("ERROR", f"Dual merge failed: {proposal_id}: {e}",
                        category="proposal_lifecycle.merge.failed",
                        params={"proposalId": proposal_id, "error": str(e)})
        raise HTTPException(status_code=500, detail=f"Dual merge failed: {e}")

    updated = _get_proposal_row(proposal_id)
    return ProposalResponse.from_neo4j(updated, [])


@router.post("/{proposal_id}/destroy", response_model=ProposalResponse)
async def destroy_proposal(proposal_id: str, body: DestroyProposalRequest, request: Request):
    """PO Destroy → DESTROYED 상태 전환 + Worktree 정리."""
    row = _get_proposal_row(proposal_id)
    if not row:
        raise HTTPException(status_code=404, detail=f"Proposal {proposal_id} not found")

    if row.get("status") == "ACCEPTED":
        raise HTTPException(status_code=423, detail="ACCEPTED proposals cannot be destroyed.")

    actor = getattr(getattr(request.state, "actor", None), "email", "anonymous")

    # Worktree 정리 (대상 프로젝트 projectRoot 기준)
    if (row.get("sandboxWorktreePath") or row.get("sandboxBranch")) and row.get("projectRoot"):
        try:
            _sandbox.remove_worktree(proposal_id, row.get("projectRoot"))
        except Exception as e:
            SmartLogger.log("WARN", f"Worktree cleanup failed for {proposal_id}: {e}",
                            category="proposal_lifecycle.destroy.worktree_cleanup_warn",
                            params={"proposalId": proposal_id, "error": str(e)})

    from datetime import datetime, timezone
    now = datetime.now(timezone.utc).isoformat()
    new_history = append_status_history(
        row.get("statusHistory", "[]"),
        row.get("status", ""),
        "DESTROYED",
        actor,
        body.reason,
    )

    with get_session() as session:
        session.run(
            """
            MATCH (p:Proposal {id: $id})
            SET p.status = 'DESTROYED',
                p.destroyedAt = datetime($at),
                p.statusHistory = $history,
                p.sandboxStatus = 'DESTROYED'
            """,
            id=proposal_id,
            at=now,
            history=new_history,
        )

    SmartLogger.log("INFO", f"Proposal destroyed: {proposal_id}",
                    category="proposal_lifecycle.destroy.done",
                    params={**http_context(request), "proposalId": proposal_id})

    updated = _get_proposal_row(proposal_id)
    return ProposalResponse.from_neo4j(updated, [])


@router.post("/{proposal_id}/revoke", response_model=ProposalResponse)
async def revoke_proposal(proposal_id: str, body: RevokeProposalRequest, request: Request):
    """ACCEPTED Proposal 수거(revoke) → 그래프(+선택적 코드) 되돌림 + PENDING_ACCEPTANCE 복귀."""
    row = _get_proposal_row(proposal_id)
    if not row:
        raise HTTPException(status_code=404, detail=f"Proposal {proposal_id} not found")

    if _actor_role(request) != "PO":
        raise HTTPException(status_code=403, detail="수거 권한이 없습니다. PO 역할이 필요합니다.")

    if row.get("status") != "ACCEPTED":
        raise HTTPException(
            status_code=409,
            detail=f"Proposal must be ACCEPTED to revoke (current: {row.get('status')})",
        )

    actor = getattr(getattr(request.state, "actor", None), "email", "anonymous")

    SmartLogger.log("INFO", f"Revoke started: {proposal_id}",
                    category="proposal_lifecycle.revoke.request",
                    params={**http_context(request), "proposalId": proposal_id, "revertCode": body.revertCode})

    try:
        await execute_revoke(proposal_id, actor, body.revertCode, comment=body.comment)
    except Exception as e:
        SmartLogger.log("ERROR", f"Revoke failed: {proposal_id}: {e}",
                        category="proposal_lifecycle.revoke.failed",
                        params={"proposalId": proposal_id, "error": str(e)})
        raise HTTPException(status_code=500, detail=f"Revoke failed: {e}")

    updated = _get_proposal_row(proposal_id)
    return ProposalResponse.from_neo4j(updated, [])


@router.post("/{proposal_id}/retry-merge")
async def retry_merge(proposal_id: str, request: Request):
    """MERGE_FAILED → Dual Merge 재시도 (SSE)."""
    row = _get_proposal_row(proposal_id)
    if not row:
        raise HTTPException(status_code=404, detail=f"Proposal {proposal_id} not found")
    if row.get("status") != "MERGE_FAILED":
        raise HTTPException(
            status_code=409,
            detail=f"Proposal must be MERGE_FAILED to retry (current: {row.get('status')})",
        )

    actor = getattr(getattr(request.state, "actor", None), "email", "anonymous")

    async def event_stream():
        yield f"event: merge_retry_start\ndata: {json.dumps({'proposalId': proposal_id})}\n\n"
        try:
            await execute_dual_merge(proposal_id, actor)
            yield f"event: merge_done\ndata: {json.dumps({'proposalId': proposal_id, 'status': 'ACCEPTED'})}\n\n"
        except Exception as e:
            yield f"event: merge_failed\ndata: {json.dumps({'proposalId': proposal_id, 'error': str(e)})}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")
