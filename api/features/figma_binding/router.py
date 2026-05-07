"""FastAPI router for /api/figma-binding/* endpoints.

Thin wrappers around service.py. Every endpoint emits a SmartLogger event;
the request_id middleware in api/main.py provides correlation IDs.
"""

from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse

from api.platform.observability.smart_logger import SmartLogger

from . import service
from .plugin_messages import router as plugin_messages_router
from .schemas import (
    BindingHistoryResponse,
    ConnectRequest,
    FigmaBindingResponse,
    StoryboardListItem,
    SyncStoryboardsResponse,
)


router = APIRouter(prefix="/api/figma-binding", tags=["figma-binding"])


def _actor_from_request(req: Request) -> str:
    """Best-effort actor resolution.

    The project does not currently have an auth model; clients may opt-in to
    pass `X-User-Email` / `X-Actor` headers. Otherwise we fall back to the
    request's source IP, then to "unknown".
    """
    h = req.headers
    return (
        h.get("x-user-email")
        or h.get("x-actor")
        or h.get("x-forwarded-for")
        or (req.client.host if req.client else None)
        or "unknown"
    )


# ─── Lifecycle ───────────────────────────────────────────────────────────


@router.get("", response_model=FigmaBindingResponse)
async def get_binding() -> dict[str, Any]:
    b = service.get_active_binding_response()
    if not b:
        raise HTTPException(status_code=404, detail="바인딩된 Figma 다큐먼트가 없습니다.")
    return b


@router.post("/connect", response_model=FigmaBindingResponse)
async def post_connect(req: ConnectRequest, request: Request) -> dict[str, Any]:
    actor = _actor_from_request(request)
    return await service.connect_binding(
        figma_file_key=req.figmaFileKey,
        api_token=req.apiToken,
        actor=actor,
    )


@router.delete("", status_code=204)
async def delete_binding(request: Request) -> None:
    actor = _actor_from_request(request)
    service.disconnect_binding(actor=actor)


@router.post("/replace", response_model=FigmaBindingResponse)
async def post_replace(req: ConnectRequest, request: Request) -> dict[str, Any]:
    actor = _actor_from_request(request)
    return await service.replace_binding(
        figma_file_key=req.figmaFileKey,
        api_token=req.apiToken,
        actor=actor,
    )


@router.get("/history", response_model=BindingHistoryResponse)
async def get_history(limit: int = 50) -> dict[str, Any]:
    items = service.get_history(limit=limit)
    return {"items": items}


# ─── Storyboards (read-only listing) ────────────────────────────────────


@router.get("/storyboards", response_model=list[StoryboardListItem])
async def get_storyboards() -> list[dict[str, Any]]:
    return service.list_storyboards()


# ─── Sync storyboards (US2: T031, T032) ──────────────────────────────────


def _normalize_sync_summary(summary: dict[str, Any]) -> dict[str, Any]:
    """Adapt service.sync_storyboards' output to the SyncStoryboardsResponse
    schema shape. Service emits richer per-item payloads (figmaPageId etc.);
    schema strips down to (commandId, reason / from / to)."""
    return {
        "created": [
            {"commandId": c["commandId"], "figmaPageId": c["figmaPageId"], "figmaPageName": c["figmaPageName"]}
            for c in summary.get("created", [])
        ],
        "reused": [
            {"commandId": c["commandId"], "figmaPageId": c["figmaPageId"], "figmaPageName": c["figmaPageName"]}
            for c in summary.get("reused", [])
        ],
        "renamed": [
            {"commandId": c["commandId"], "from": c.get("oldName") or "", "to": c.get("figmaPageName") or ""}
            for c in summary.get("renamed", [])
        ],
        "archived": [
            {"commandId": cid, "reason": "entry_command_removed"} for cid in summary.get("archived", [])
        ],
        "unreachable": [
            {"commandId": u["commandId"], "reason": u.get("error") or "unknown"}
            for u in summary.get("unreachable", [])
        ],
    }


@router.post("/sync-storyboards", response_model=SyncStoryboardsResponse)
async def post_sync_storyboards(request: Request) -> dict[str, Any]:
    actor = _actor_from_request(request)
    summary = await service.sync_storyboards(actor=actor)
    return _normalize_sync_summary(summary)


@router.get("/sync-storyboards/stream")
async def get_sync_storyboards_stream(request: Request) -> StreamingResponse:
    """SSE variant. Emits one event per page operation as it completes,
    finishing with a `done` event carrying the full summary."""
    actor = _actor_from_request(request)

    async def _gen():
        try:
            async for name, payload in service.sync_storyboards_stream(actor=actor):
                if name == "done":
                    payload = _normalize_sync_summary(payload)
                yield f"event: {name}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"
        except Exception as e:  # noqa: BLE001
            yield f"event: error\ndata: {json.dumps({'detail': str(e)}, ensure_ascii=False)}\n\n"

    return StreamingResponse(_gen(), media_type="text/event-stream")


# ─── Retry sync (FR-020 / T087) ───────────────────────────────────────────


from pydantic import BaseModel  # noqa: E402

from . import bulk_sync  # noqa: E402


class RetrySyncRequest(BaseModel):
    uiIds: list[str] | None = None  # null/missing → retry every :UI {figmaSyncStatus:'failed'}


@router.post("/retry-sync")
async def post_retry_sync(req: RetrySyncRequest, request: Request) -> dict[str, Any]:
    """Re-run the Figma push for selected UIs (or every failed-sync UI when
    uiIds is null/missing). Synchronous v1: waits for all pushes to complete
    and returns the summary. SSE streaming variant (T088) is deferred until
    Group D's frontend surfaces are wired and need progress updates.
    """
    actor = _actor_from_request(request)

    # Resolve UI ids: explicit list, or every failed-sync UI.
    if req.uiIds is None:
        from . import repository as _repo
        failed = _repo.list_failed_sync_uis()
        ui_ids = [r["uiId"] for r in failed]
    else:
        ui_ids = req.uiIds

    if not ui_ids:
        return {"sessionId": None, "queuedCount": 0, "syncedCount": 0, "failedCount": 0, "message": "재시도할 UI가 없습니다."}

    SmartLogger.log(
        "INFO",
        f"figma_binding.retry.requested actor={actor} count={len(ui_ids)}",
        category="figma_binding.retry.requested",
        params={"actor": actor, "uiIds": ui_ids[:50], "count": len(ui_ids)},
    )

    import uuid as _uuid
    session_id = _uuid.uuid4().hex[:12]

    events: list[dict[str, Any]] = []
    def _capture(name: str, payload: dict[str, Any]) -> None:
        events.append({"name": name, **payload})

    summary = await bulk_sync.sync_batch(
        session_id=session_id,
        ui_ids=ui_ids,
        on_event=_capture,
    )

    SmartLogger.log(
        "INFO",
        f"figma_binding.retry.done session={session_id} synced={summary.get('syncedCount')} failed={summary.get('failedCount')}",
        category="figma_binding.retry.done",
        params={"sessionId": session_id, **summary},
    )

    return {
        "sessionId": session_id,
        "queuedCount": len(ui_ids),
        "syncedCount": summary.get("syncedCount", 0),
        "failedCount": summary.get("failedCount", 0),
        "events": events,
        "summary": summary,
    }


# ─── Bidirectional sync (RA ↔ Figma per UI) ───────────────────────────────


@router.post("/update-frame/{ui_id}")
async def post_update_frame(ui_id: str, request: Request) -> dict[str, Any]:
    """RA → Figma: push the UI's current sceneGraph as an in-place update
    of its linked Figma frame. Frame must already exist (UI.figmaNodeId set).
    """
    actor = _actor_from_request(request)
    SmartLogger.log(
        "INFO",
        f"figma_binding.update_frame.start ui={ui_id} actor={actor}",
        category="figma_binding.update_frame",
    )
    result = await service.update_frame_for_ui(ui_id)
    if not result.get("ok"):
        raise HTTPException(status_code=502, detail=result.get("errorKo") or "Figma 프레임 업데이트 실패")
    return result


@router.post("/pull-frame/{ui_id}")
async def post_pull_frame(ui_id: str, request: Request) -> dict[str, Any]:
    """Figma → RA: pull the linked Figma frame's current state via the
    plugin, convert to sceneGraph, persist on the UI node. No Figma API
    token needed (plugin reads in-process).
    """
    actor = _actor_from_request(request)
    SmartLogger.log(
        "INFO",
        f"figma_binding.pull_frame.start ui={ui_id} actor={actor}",
        category="figma_binding.pull_frame",
    )
    result = await service.pull_frame_via_plugin(ui_id)
    if not result.get("ok"):
        raise HTTPException(status_code=502, detail=result.get("errorKo") or "Figma 프레임 pull 실패")
    return result


# Mount the plugin ack endpoints (CREATE_PAGE_ACK / CREATE_FRAME_IN_PAGE_ACK).
# These live under /api/figma-plugin/* because the plugin already speaks that prefix.
# Importing here keeps the wiring local to feature 016.
__all__ = ["router", "plugin_messages_router"]
