"""Plugin protocol message helpers for figma_binding (016).

Wire format defined in specs/016-figma-document-binding/contracts/plugin-protocol.md.
Transport reuses the existing 009 polling-based channel
(`api.features.ingestion.figma_plugin_ws.queue_update_for_plugin`).

The plugin polls `/api/figma-plugin/poll`, receives the message, performs the
op, and replies via the new ack endpoints in this module:

  POST /api/figma-plugin/create-page-ack
  POST /api/figma-plugin/create-frame-in-page-ack

The backend correlates ack with request via `requestId` using in-memory Futures.
"""

from __future__ import annotations

import asyncio
import uuid
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel

from api.features.ingestion.figma_plugin_ws import (
    queue_update_for_plugin,
    is_plugin_connected,
    is_polling_active,
    send_to_plugin,
)
from api.platform.observability.smart_logger import SmartLogger


# ── In-memory request → Future correlator ───────────────────────────────

_pending: dict[str, asyncio.Future] = {}
_pending_lock = asyncio.Lock()


async def _register(request_id: str) -> asyncio.Future:
    fut: asyncio.Future = asyncio.get_event_loop().create_future()
    async with _pending_lock:
        _pending[request_id] = fut
    return fut


async def _resolve(request_id: str, payload: dict[str, Any]) -> bool:
    async with _pending_lock:
        fut = _pending.pop(request_id, None)
    if fut is None or fut.done():
        return False
    fut.set_result(payload)
    return True


# ── Public send-and-wait API ────────────────────────────────────────────


async def send_and_wait(
    file_key: str, message: dict[str, Any], timeout_sec: float
) -> dict[str, Any]:
    """Send a message to the plugin and wait for its ack (correlated by requestId).

    Returns the ack payload as a dict. Raises:
      - PluginNotConnectedError if no plugin/poll path exists for the file_key
        (we still queue, but ack-needing operations refuse to wait without a
        live channel — see contracts/plugin-protocol.md).
      - asyncio.TimeoutError on timeout.
    """
    request_id = message.get("requestId") or str(uuid.uuid4())
    message["requestId"] = request_id

    # Refuse to wait if the plugin has never announced itself for this
    # file_key (neither via websocket REGISTER nor via /announce-support).
    # Otherwise the user would block on an op that can never resolve.
    # Callers (service.py) translate PluginNotConnectedError into a 503.
    if not is_polling_active(file_key):
        raise PluginNotConnectedError(file_key)

    fut = await _register(request_id)
    try:
        # Try websocket first (instant); otherwise queue for polling.
        if is_plugin_connected(file_key):
            sent = await send_to_plugin(file_key, message)
            if not sent:
                await queue_update_for_plugin(file_key, message)
        else:
            await queue_update_for_plugin(file_key, message)
        return await asyncio.wait_for(fut, timeout=timeout_sec)
    except asyncio.TimeoutError:
        async with _pending_lock:
            _pending.pop(request_id, None)
        raise


# ── Errors ──────────────────────────────────────────────────────────────


class PluginNotConnectedError(RuntimeError):
    def __init__(self, file_key: str):
        super().__init__(f"Figma plugin not connected for file_key={file_key}")
        self.file_key = file_key


# ── Message builders ─────────────────────────────────────────────────────


def build_create_page(name: str) -> dict[str, Any]:
    return {"type": "CREATE_PAGE", "requestId": str(uuid.uuid4()), "name": name}


def build_create_frame_in_page(
    figma_page_id: str, frame_name: str, scene_graph: dict[str, Any]
) -> dict[str, Any]:
    return {
        "type": "CREATE_FRAME_IN_PAGE",
        "requestId": str(uuid.uuid4()),
        "figmaPageId": figma_page_id,
        "frameName": frame_name,
        "sceneGraph": scene_graph,
    }


# ── Ack endpoints (the plugin POSTs here when it finishes) ──────────────

router = APIRouter(tags=["figma-plugin"])


class CreatePageAckBody(BaseModel):
    requestId: str
    ok: bool
    figmaPageId: str | None = None
    figmaPageName: str | None = None
    error: str | None = None


@router.post("/api/figma-plugin/create-page-ack")
async def create_page_ack(req: CreatePageAckBody) -> dict[str, Any]:
    delivered = await _resolve(req.requestId, req.dict())
    if not delivered:
        SmartLogger.log(
            "WARN",
            f"CREATE_PAGE_ACK for unknown/expired requestId {req.requestId}",
            category="figma_binding.plugin.ack_orphan",
        )
    return {"ok": True}


class CreateFrameInPageAckBody(BaseModel):
    requestId: str
    ok: bool
    figmaPageId: str | None = None
    figmaNodeId: str | None = None
    figmaFrameName: str | None = None
    nodesCreated: int | None = None  # plugin's report from buildFrameFromSceneGraph
    nodesFailed: int | None = None
    renderErrors: list[str] | None = None  # 024: per-node failure reasons
    buildId: str | None = None  # 024: spec024 plugin build identifier (e.g. "v5")
    error: str | None = None


@router.post("/api/figma-plugin/create-frame-in-page-ack")
async def create_frame_in_page_ack(req: CreateFrameInPageAckBody) -> dict[str, Any]:
    delivered = await _resolve(req.requestId, req.dict())
    if not delivered:
        SmartLogger.log(
            "WARN",
            f"CREATE_FRAME_IN_PAGE_ACK for unknown/expired requestId {req.requestId}",
            category="figma_binding.plugin.ack_orphan",
        )
    return {"ok": True}


# ── Bidirectional sync acks (UPDATE_FRAME, EXPORT_FRAME_BY_ID) ──


class UpdateFrameAckBody(BaseModel):
    requestId: str
    ok: bool
    figmaNodeId: str | None = None
    figmaFrameName: str | None = None
    nodesCreated: int | None = None
    nodesFailed: int | None = None
    error: str | None = None


@router.post("/api/figma-plugin/update-frame-ack")
async def update_frame_ack(req: UpdateFrameAckBody) -> dict[str, Any]:
    delivered = await _resolve(req.requestId, req.dict())
    if not delivered:
        SmartLogger.log(
            "WARN",
            f"UPDATE_FRAME_RESULT for unknown/expired requestId {req.requestId}",
            category="figma_binding.plugin.ack_orphan",
        )
    return {"ok": True}


class ExportFrameByIdAckBody(BaseModel):
    requestId: str
    ok: bool
    figmaNodeId: str | None = None
    figmaFrameName: str | None = None
    frameData: dict[str, Any] | None = None
    error: str | None = None


@router.post("/api/figma-plugin/export-frame-by-id-ack")
async def export_frame_by_id_ack(req: ExportFrameByIdAckBody) -> dict[str, Any]:
    delivered = await _resolve(req.requestId, req.dict())
    if not delivered:
        SmartLogger.log(
            "WARN",
            f"EXPORT_FRAME_BY_ID_RESULT for unknown/expired requestId {req.requestId}",
            category="figma_binding.plugin.ack_orphan",
        )
    return {"ok": True}


# Message builders for bidirectional ops.


def build_update_frame(figma_node_id: str, scene_graph: dict[str, Any]) -> dict[str, Any]:
    return {
        "type": "UPDATE_FRAME_FROM_SCENE_GRAPH",
        "requestId": str(uuid.uuid4()),
        "figmaNodeId": figma_node_id,
        "sceneGraph": scene_graph,
    }


def build_export_frame_by_id(figma_node_id: str) -> dict[str, Any]:
    return {
        "type": "EXPORT_FRAME_BY_ID",
        "requestId": str(uuid.uuid4()),
        "figmaNodeId": figma_node_id,
    }
