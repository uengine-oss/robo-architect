"""Deletion history + recovery routes (034 — option B snapshot).

Lists :DeletionRecord batches written by the Epic/Feature/UserStory delete
routes, and restores or permanently purges a batch. Restore re-creates the
snapshotted nodes (by natural id) and re-links their relationships to whichever
endpoints survive — neighbours deleted in the same batch are re-created too.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from starlette.requests import Request

from api.features.requirements import deletion_archive as da
from api.features.requirements.requirements_contracts import (
    DeletionRecordDTO,
    DeletionRecordListResponse,
    RestoreResponse,
)
from api.platform.neo4j import get_session
from api.platform.observability.request_logging import http_context
from api.platform.observability.smart_logger import SmartLogger

router = APIRouter()


@router.get("/deletion-records", response_model=DeletionRecordListResponse)
async def list_deletion_records() -> DeletionRecordListResponse:
    """All recoverable deletion batches, most recent first."""
    with get_session() as session:
        records = [DeletionRecordDTO(**r) for r in da.list_records(session)]
    return DeletionRecordListResponse(records=records)


@router.post("/deletion-records/{batch_id}/restore", response_model=RestoreResponse)
async def restore_deletion(batch_id: str, request: Request) -> RestoreResponse:
    """Re-create a deleted requirement subtree from its snapshot."""
    with get_session() as session:
        result = da.restore(session, batch_id)
    if not result["restored"] and result.get("reason") == "not_found":
        raise HTTPException(status_code=404, detail=f"Deletion record {batch_id} not found")
    SmartLogger.log(
        "INFO",
        "Deletion restored." if result["restored"] else "Deletion restore skipped.",
        category="requirements.deletion.restore",
        params={**http_context(request), "batch_id": batch_id, **result},
    )
    return RestoreResponse(**result)


@router.delete("/deletion-records/{batch_id}", response_model=RestoreResponse)
async def purge_deletion(batch_id: str, request: Request) -> RestoreResponse:
    """Permanently drop a deletion record (no recovery afterward)."""
    with get_session() as session:
        ok = da.purge(session, batch_id)
    if not ok:
        raise HTTPException(status_code=404, detail=f"Deletion record {batch_id} not found")
    SmartLogger.log(
        "INFO",
        "Deletion record purged.",
        category="requirements.deletion.purge",
        params={**http_context(request), "batch_id": batch_id},
    )
    return RestoreResponse(restored=False, reason="purged")
