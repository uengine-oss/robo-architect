from __future__ import annotations

from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException
from starlette.requests import Request

from api.features.model_modifier.chat_contracts import ConfirmRequest, ConfirmResponse, DraftChange
from api.features.model_modifier.model_change_application import apply_confirmed_changes_atomic
from api.platform.observability.request_logging import http_context, summarize_for_log
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
                "approvedChangeIds": summarize_for_log(list(approved_ids)),
                "drafts": summarize_for_log([d.model_dump() for d in payload.drafts]),
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
            params={**http_context(request), "errors": errors},
        )
    else:
        SmartLogger.log(
            "INFO",
            "Chat confirm applied successfully.",
            category="api.chat.confirm.applied",
            params={**http_context(request), "appliedCount": len(applied)},
        )

    return ConfirmResponse(success=success, appliedChanges=applied, errors=errors)


