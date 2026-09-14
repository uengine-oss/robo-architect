from __future__ import annotations

from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException
from starlette.requests import Request

from api.features.collab import store as collab
from api.features.model_modifier.chat_contracts import ConfirmRequest, ConfirmResponse, DraftChange
from api.features.model_modifier.model_change_application import apply_confirmed_changes_atomic
from api.platform.neo4j_context import get_override
from api.platform.observability.request_logging import http_context
from api.platform.observability.smart_logger import SmartLogger

router = APIRouter()


@router.post("/confirm")
async def confirm_changes(payload: ConfirmRequest, request: Request) -> ConfirmResponse:
    """
    Apply approved draft changes to Neo4j (all-or-nothing).
    """
    if not payload.drafts:
        return ConfirmResponse(success=True, appliedChanges=[], errors=[])

    approved_ids = set(payload.approvedChangeIds or [])
    approved: List[DraftChange] = [d for d in payload.drafts if d.changeId in approved_ids]

    if not approved:
        return ConfirmResponse(success=True, appliedChanges=[], errors=[])

    SmartLogger.log(
        "INFO",
        "Chat confirm requested: applying approved draft changes.",
        category="api.chat.confirm.request",
        params={
            **http_context(request),
            "inputs": {
                "approvedCount": len(approved),
                # Reproducibility: keep raw payload (no summarize/truncation here).
                "approvedChangeIds": list(approved_ids),
                "drafts": [d.model_dump() for d in payload.drafts],
                "approvedDrafts": [d.model_dump() for d in approved],
            },
        },
    )

    try:
        applied, errors = apply_confirmed_changes_atomic([d.model_dump() for d in approved])
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    success = len(errors) == 0
    if not success:
        SmartLogger.log(
            "WARNING",
            "Chat confirm failed: validation/apply errors (no changes applied).",
            category="api.chat.confirm.failed",
            params={**http_context(request), "errors": errors, "approvedDrafts": [d.model_dump() for d in approved]},
        )
    else:
        SmartLogger.log(
            "INFO",
            "Chat confirm applied successfully.",
            category="api.chat.confirm.applied",
            params={**http_context(request), "appliedCount": len(applied), "appliedChanges": applied},
        )

    if success and applied:
        _publish_to_other_windows(request, applied)

    return ConfirmResponse(success=success, appliedChanges=applied, errors=errors)


def _publish_to_other_windows(request: Request, applied: List[Dict[str, Any]]) -> None:
    """같은 프로젝트를 보는 **다른 창**에 무엇이 바뀌었는지 보낸다.

    이 경로 하나가 AI 채팅 수정과 Inspector 저장을 **둘 다** 지난다. 그래서
    여기만 이으면 두 가지가 같이 해결된다.

    자기 창은 이미 응답의 `appliedChanges` 를 `syncAfterChanges` 로 적용한다.
    남의 창은 그동안 아무것도 못 받아 **새로고침해야 보였다.** 같은 목록을
    스트림으로 보내면 같은 길로 제자리 반영된다 — 통째로 다시 읽지 않으므로
    상대가 편집 중이던 화면이 안 깨진다.

    **던지지 않는다.** 알림이 안 되는 것보다 적용된 쓰기가 500 으로 뒤집히는
    쪽이 훨씬 나쁘다.
    """
    try:
        override = get_override()
        graph = getattr(override, "database", None) if override else None
        if not graph:
            # 헤더로 고른 프로젝트가 없으면 `.env` 로 떨어진 요청이다. 그 경우
            # 알릴 대상을 특정할 수 없다.
            return
        claims = getattr(request.state, "auth_claims", None) or {}
        collab.publish(graph, applied, actor_uid=claims.get("sub"))
    except Exception:
        return


