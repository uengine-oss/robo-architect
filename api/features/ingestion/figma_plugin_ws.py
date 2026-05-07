"""
WebSocket bridge for Figma Plugin ↔ RoboArchitect.

The Figma plugin connects via WebSocket and receives node update commands.
InspectorPanel/other frontends send updates via the REST API,
which are relayed to the connected plugin.
"""

from __future__ import annotations

import asyncio
import json
import uuid
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException
from pydantic import BaseModel

from api.platform.neo4j import get_session
from api.platform.observability.smart_logger import SmartLogger

router = APIRouter(tags=["figma-plugin"])

# ── Connected plugins registry (file_key → WebSocket) ──
_connections: dict[str, WebSocket] = {}
_lock = asyncio.Lock()

# ── Plugin metadata (feature 016): supported message set per file_key ──
# Populated either by REGISTER (websocket) or by POST /announce-support (polling).
_plugin_metadata: dict[str, dict[str, Any]] = {}


def is_message_supported(file_key: str, msg_type: str) -> bool:
    """True if the connected plugin announced support for the given message type.
    Returns True if no metadata is recorded yet (legacy plugin pre-016 — assume
    only 009-era messages are supported; figma_binding callers gate on this
    explicitly before invoking newer ops)."""
    meta = _plugin_metadata.get(file_key)
    if not meta:
        return False
    msgs = meta.get("supportedMessages") or []
    return msg_type in msgs


def get_plugin_metadata(file_key: str) -> dict[str, Any] | None:
    return _plugin_metadata.get(file_key)


def is_polling_active(file_key: str) -> bool:
    """True if we have any signal (websocket or recent supportedMessages
    announcement) that a plugin is reachable for this file key."""
    return file_key in _connections or file_key in _plugin_metadata


async def _register(file_key: str, ws: WebSocket) -> None:
    async with _lock:
        # Close existing connection for same file
        old = _connections.get(file_key)
        if old:
            try:
                await old.close()
            except Exception:
                pass
        _connections[file_key] = ws
    SmartLogger.log("INFO", f"Figma plugin registered: {file_key}", category="figma_plugin.register")


async def _unregister(file_key: str) -> None:
    async with _lock:
        _connections.pop(file_key, None)
    SmartLogger.log("INFO", f"Figma plugin disconnected: {file_key}", category="figma_plugin.disconnect")


async def send_to_plugin(file_key: str, message: dict) -> bool:
    """Send a message to the connected Figma plugin for a specific file."""
    ws = _connections.get(file_key)
    if not ws:
        return False
    try:
        await ws.send_json(message)
        return True
    except Exception as e:
        SmartLogger.log("ERROR", f"Failed to send to plugin {file_key}: {e}", category="figma_plugin.send")
        await _unregister(file_key)
        return False


def is_plugin_connected(file_key: str) -> bool:
    return file_key in _connections


# ── WebSocket endpoint ──

@router.websocket("/ws/figma-plugin")
async def figma_plugin_ws(ws: WebSocket):
    """
    WebSocket endpoint for Figma plugin connection.
    Plugin sends REGISTER message with fileKey, then listens for UPDATE commands.
    """
    await ws.accept()
    file_key: str | None = None

    # Check query param for file_key
    qp = ws.query_params.get("file_key")
    if qp:
        file_key = qp
        await _register(file_key, ws)

    try:
        while True:
            data = await ws.receive_text()
            try:
                msg = json.loads(data)
            except json.JSONDecodeError:
                continue

            msg_type = msg.get("type")

            if msg_type == "REGISTER":
                fk = msg.get("fileKey")
                if fk:
                    file_key = fk
                    await _register(file_key, ws)
                    # Record plugin metadata (feature 016 protocol versioning)
                    supported = msg.get("supportedMessages") or []
                    _plugin_metadata[file_key] = {
                        "supportedMessages": list(supported),
                        "transport": "websocket",
                    }
                    await ws.send_json({"type": "REGISTERED", "fileKey": file_key})

            elif msg_type == "PONG":
                pass  # Keepalive response

            elif msg_type == "SELECTION":
                # Plugin reports selection change — could be used for sync UI
                SmartLogger.log(
                    "DEBUG",
                    f"Plugin selection: {len(msg.get('nodes', []))} nodes",
                    category="figma_plugin.selection",
                )

            elif msg_type == "UPDATE_COMPLETE":
                SmartLogger.log(
                    "INFO",
                    f"Plugin update complete: {msg.get('updated')}/{msg.get('total')} nodes",
                    category="figma_plugin.update_complete",
                )

            elif isinstance(msg_type, str) and msg_type.endswith("_ACK"):
                # Feature 016 (US2 / US3): the plugin's response to a
                # plugin_messages.send_and_wait(...) call. Correlated by
                # requestId. Forward to the figma_binding correlator.
                request_id = msg.get("requestId")
                if request_id:
                    try:
                        from api.features.figma_binding.plugin_messages import _resolve  # noqa: PLC0415
                        await _resolve(request_id, msg)
                    except Exception as e:
                        SmartLogger.log(
                            "WARN",
                            f"Failed to resolve websocket ack {msg_type} {request_id}: {e}",
                            category="figma_plugin.ack.error",
                        )

    except WebSocketDisconnect:
        pass
    except Exception as e:
        SmartLogger.log("ERROR", f"Plugin WebSocket error: {e}", category="figma_plugin.error")
    finally:
        if file_key:
            await _unregister(file_key)


# ── REST API for sending updates to plugin ──

class PluginNodeUpdate(BaseModel):
    file_key: str
    node_updates: list[dict[str, Any]]  # [{ nodeId, props }]


class PluginTextUpdate(BaseModel):
    file_key: str
    node_id: str
    text: str


@router.post("/api/figma-plugin/update-nodes")
async def push_node_updates(req: PluginNodeUpdate) -> dict[str, Any]:
    """Send node property updates to the Figma plugin (WebSocket or polling queue)."""
    msg = {"type": "UPDATE_NODES", "nodeUpdates": req.node_updates}

    # Try WebSocket first, fall back to polling queue
    if is_plugin_connected(req.file_key):
        sent = await send_to_plugin(req.file_key, msg)
        if sent:
            return {"ok": True, "nodeCount": len(req.node_updates), "delivery": "websocket"}

    # Queue for polling
    await queue_update_for_plugin(req.file_key, msg)
    return {"ok": True, "nodeCount": len(req.node_updates), "delivery": "queued"}


@router.post("/api/figma-plugin/update-text")
async def push_text_update(req: PluginTextUpdate) -> dict[str, Any]:
    """Send a text content update to a specific node in Figma."""
    msg = {"type": "UPDATE_TEXT", "nodeId": req.node_id, "text": req.text}

    if is_plugin_connected(req.file_key):
        sent = await send_to_plugin(req.file_key, msg)
        if sent:
            return {"ok": True, "nodeId": req.node_id, "delivery": "websocket"}

    await queue_update_for_plugin(req.file_key, msg)
    return {"ok": True, "nodeId": req.node_id, "delivery": "queued"}


# ── Polling-based alternative (for Figma plugin iframe sandbox) ──
_pending_updates: dict[str, list[dict]] = {}  # file_key → [messages]
_pending_lock = asyncio.Lock()


async def queue_update_for_plugin(file_key: str, message: dict) -> None:
    """Queue an update message for a plugin to pick up via polling."""
    async with _pending_lock:
        if file_key not in _pending_updates:
            _pending_updates[file_key] = []
        _pending_updates[file_key].append(message)
        # Keep max 100 pending messages
        if len(_pending_updates[file_key]) > 100:
            _pending_updates[file_key] = _pending_updates[file_key][-100:]


class AnnounceSupportRequest(BaseModel):
    file_key: str
    supportedMessages: list[str]


@router.post("/api/figma-plugin/announce-support")
async def announce_support(req: AnnounceSupportRequest) -> dict[str, Any]:
    """Polling-mode plugin announces its supported message set on connect.
    Feature 016 uses this to detect old plugins lacking CREATE_PAGE / CREATE_FRAME_IN_PAGE.
    """
    _plugin_metadata[req.file_key] = {
        "supportedMessages": list(req.supportedMessages),
        "transport": "polling",
    }
    SmartLogger.log(
        "INFO",
        f"Plugin support announced: {req.file_key} → {req.supportedMessages}",
        category="figma_plugin.support",
    )
    return {"ok": True}


# Default supportedMessages for plugins that have not (yet) called
# /announce-support. v1.2 plugins always announce the full set on connect,
# but the backend's in-memory `_plugin_metadata` is wiped on every uvicorn
# reload — so by the time bulk-with-binding fires, the plugin's announcement
# may have been lost even though it is actively polling. Treating any
# /poll caller as a v1.2 plugin is safe because that is the only plugin
# version that exists in this codebase, and the alternative (PluginNotConnectedError
# during bulk_sync) is much worse for the user.
_DEFAULT_SUPPORTED_MESSAGES = [
    "UPDATE_NODES",
    "UPDATE_TEXT",
    "SYNC_FRAME",
    "CREATE_PAGE",
    "CREATE_FRAME_IN_PAGE",
]


@router.get("/api/figma-plugin/poll")
async def poll_updates(file_key: str = "") -> dict[str, Any]:
    """Plugin polls this endpoint to get pending update commands.

    Side effect: lazy-registers the plugin's metadata if missing. This
    survives backend reloads where `_plugin_metadata` would otherwise be
    empty until the plugin happens to reconnect.
    """
    if not file_key:
        return {"updates": []}

    if file_key not in _plugin_metadata:
        _plugin_metadata[file_key] = {
            "supportedMessages": list(_DEFAULT_SUPPORTED_MESSAGES),
            "transport": "polling",
            "inferred": True,  # marker: came from /poll, not /announce-support
        }
        SmartLogger.log(
            "INFO",
            f"Plugin metadata inferred from /poll: {file_key}",
            category="figma_plugin.support.inferred",
        )

    async with _pending_lock:
        updates = _pending_updates.pop(file_key, [])

    return {"updates": updates, "count": len(updates)}


# NOTE: The polling-mode REST ack endpoints live in
# `api/features/figma_binding/plugin_messages.py` as type-specific routes
# (`/create-page-ack`, `/create-frame-in-page-ack`). The websocket branch
# above (msg_type.endswith("_ACK")) reuses the same correlator via direct
# import so both transports share one source of truth.


class RegisterFrameRequest(BaseModel):
    file_key: str
    figma_node_id: str
    frame_name: str


@router.post("/api/figma-plugin/register-frame")
async def register_figma_frame(req: RegisterFrameRequest) -> dict[str, Any]:
    """
    Save the Figma node ID for a UI node matched by frame name.
    Called by the plugin when it creates a new frame in Figma.
    """
    with get_session() as session:
        # Find UI node by name (displayName or name)
        result = session.run(
            """
            MATCH (ui:UI)
            WHERE ui.displayName = $name OR ui.name = $name
            SET ui.figmaFileKey = $file_key,
                ui.figmaNodeId = $figma_node_id,
                ui.updatedAt = datetime()
            RETURN ui.id as id, ui.name as name
            LIMIT 1
            """,
            name=req.frame_name,
            file_key=req.file_key,
            figma_node_id=req.figma_node_id,
        ).single()

        if not result:
            return {"ok": False, "detail": f"UI node '{req.frame_name}' not found in Neo4j"}

    SmartLogger.log(
        "INFO",
        f"Registered Figma frame: {req.figma_node_id} → UI '{result['name']}' ({result['id']})",
        category="figma_plugin.register_frame",
    )

    return {"ok": True, "uiNodeId": result["id"], "figmaNodeId": req.figma_node_id}


# ── Plugin result handshake (Plugin reports → Frontend polls) ──
_sync_results: dict[str, dict] = {}  # "fileKey:frameName" → result
_results_lock = asyncio.Lock()


class PluginSyncResult(BaseModel):
    file_key: str
    frame_name: str
    frame_id: str
    is_new_frame: bool = False
    updated: int = 0
    failed: int = 0
    message: str = ""
    ui_node_id: str | None = None


@router.post("/api/figma-plugin/report-result")
async def report_sync_result(req: PluginSyncResult) -> dict[str, Any]:
    """Plugin reports SYNC_FRAME result. Backend saves figmaNodeId and queues for frontend."""
    # Save figmaNodeId to Neo4j if ui_node_id is provided
    if req.ui_node_id and req.frame_id:
        try:
            with get_session() as session:
                session.run(
                    """
                    MATCH (ui:UI {id: $ui_id})
                    SET ui.figmaNodeId = $fid, ui.figmaFileKey = $fk, ui.updatedAt = datetime()
                    """,
                    ui_id=req.ui_node_id,
                    fid=req.frame_id,
                    fk=req.file_key,
                )
            SmartLogger.log("INFO", f"Saved figmaNodeId {req.frame_id} for UI {req.ui_node_id}", category="figma_plugin.save_id")
        except Exception as e:
            SmartLogger.log("ERROR", f"Failed to save figmaNodeId: {e}", category="figma_plugin.save_id")

    # Queue result for frontend polling
    key = f"{req.file_key}:{req.frame_name}"
    async with _results_lock:
        _sync_results[key] = {
            "frameId": req.frame_id,
            "frameName": req.frame_name,
            "isNewFrame": req.is_new_frame,
            "updated": req.updated,
            "failed": req.failed,
            "message": req.message,
        }

    return {"ok": True}


@router.get("/api/figma-plugin/get-result")
async def get_sync_result(file_key: str = "", frame_name: str = "") -> dict[str, Any]:
    """Frontend polls for Plugin sync result."""
    key = f"{file_key}:{frame_name}"
    async with _results_lock:
        result = _sync_results.pop(key, None)
    return {"result": result}


# ── Export result: Plugin sends frame data → backend converts to SceneGraph ──

class ExportResultRequest(BaseModel):
    file_key: str
    frame_id: str
    frame_name: str
    frame_data: dict | None = None
    ui_node_id: str | None = None
    success: bool = False
    error: str = ""


@router.post("/api/figma-plugin/export-result")
async def receive_export_result(req: ExportResultRequest) -> dict[str, Any]:
    """
    Receive exported frame data from Plugin, convert to SceneGraph
    via wireframe service, and save to Neo4j.
    """
    if not req.success or not req.frame_data:
        return {"ok": False, "detail": req.error or "No frame data"}

    # Extract component instances from the Figma node tree
    children = req.frame_data.get("children", [])
    components: list[dict] = []
    for child in children:
        child_type = child.get("type", "")
        child_name = child.get("name", "")
        if child_type in ("INSTANCE", "FRAME", "COMPONENT", "GROUP"):
            overrides = _extract_text_overrides_from_export(child)
            components.append({"component": child_name, "overrides": overrides})

    # Normalize component names: "header-main=back" → "header-main"
    for comp in components:
        name = comp.get("component", "")
        if "=" in name:
            comp["component"] = name.split("=")[0]

    SmartLogger.log(
        "INFO",
        f"Export components: {[(c['component'], c.get('overrides',{})) for c in components[:5]]}",
        category="figma_plugin.export.components",
    )

    scene_graph = None
    if components:
            try:
                import httpx as _httpx
                import os as _os2
                ws_url = _os2.getenv("WIREFRAME_SERVICE_URL", "http://localhost:7610")
                async with _httpx.AsyncClient(timeout=60.0) as client:
                    resp = await client.post(
                        f"{ws_url}/render",
                        json={
                            "name": req.frame_name,
                            "width": round(req.frame_data.get("width", 375)),
                            "height": round(req.frame_data.get("height", 812)),
                            "components": components,
                        },
                    )
                    if resp.status_code == 200:
                        scene_graph = resp.json()
            except Exception as e:
                SmartLogger.log("WARN", f"Wireframe render fallback failed: {e}", category="figma_plugin.export")

    # Fallback: direct node tree conversion (preserves structure but no component styling)
    if not scene_graph or len(scene_graph.get("nodes", {})) < 3:
        scene_graph = _figma_export_to_scene_graph(req.frame_data)

    if not scene_graph:
        return {"ok": False, "detail": "Failed to convert frame to SceneGraph"}

    # Save to Neo4j — find by ui_node_id or by frame name
    import json as _json
    sg_str = _json.dumps(scene_graph, ensure_ascii=False)
    with get_session() as session:
        if req.ui_node_id:
            session.run(
                """
                MATCH (ui:UI {id: $uid})
                SET ui.sceneGraph = $sg, ui.figmaNodeId = $fid,
                    ui.figmaFileKey = $fk, ui.updatedAt = datetime()
                """,
                uid=req.ui_node_id, sg=sg_str, fid=req.frame_id, fk=req.file_key,
            )
        elif req.frame_name:
            session.run(
                """
                MATCH (ui:UI)
                WHERE ui.displayName = $name OR ui.name = $name
                SET ui.sceneGraph = $sg, ui.figmaNodeId = $fid,
                    ui.figmaFileKey = $fk, ui.updatedAt = datetime()
                """,
                name=req.frame_name, sg=sg_str, fid=req.frame_id, fk=req.file_key,
            )

    # Queue result for frontend polling
    key = f"{req.file_key}:{req.frame_name}"
    async with _results_lock:
        _sync_results[key] = {
            "frameId": req.frame_id,
            "frameName": req.frame_name,
            "sceneGraph": sg_str,
            "nodeCount": len(scene_graph.get("nodes", {})),
            "message": f"Figma에서 가져옴 ({len(components)}개 컴포넌트)",
        }

    return {"ok": True, "nodeCount": len(scene_graph.get("nodes", {}))}


def _figma_export_to_scene_graph(frame_data: dict) -> dict:
    """
    Convert Plugin's serialized Figma node tree directly to a SceneGraph JSON.
    No wireframe service needed — just maps Figma nodes to SceneNode format.
    """
    nodes = {}
    root_id = "0:0"
    page_id = "0:1"
    _counter = [2]

    def next_id():
        _counter[0] += 1
        return f"0:{_counter[0]}"

    # Default field set shared by root + page so the open-pencil deserializer
    # finds every key it expects (even on nodes that are essentially empty).
    def _empty_defaults() -> dict[str, Any]:
        return {
            "x": 0, "y": 0, "width": 0, "height": 0, "rotation": 0,
            "fills": [], "strokes": [], "effects": [], "opacity": 1,
            "cornerRadius": 0,
            "topLeftRadius": 0, "topRightRadius": 0,
            "bottomLeftRadius": 0, "bottomRightRadius": 0,
            "independentCorners": False, "cornerSmoothing": 0,
            "visible": True, "locked": False, "clipsContent": False,
            "layoutMode": "NONE", "itemSpacing": 0,
            "paddingTop": 0, "paddingRight": 0, "paddingBottom": 0, "paddingLeft": 0,
            "primaryAxisSizing": "FIXED", "counterAxisSizing": "FIXED",
            "primaryAxisAlign": "MIN", "counterAxisAlign": "MIN",
            "layoutWrap": "NO_WRAP", "layoutGrow": 0, "layoutAlignSelf": "AUTO",
            "layoutPositioning": "AUTO", "blendMode": "PASS_THROUGH",
            "text": "", "fontSize": 14, "fontFamily": "Inter", "fontWeight": 400,
            "italic": False, "textAlignHorizontal": "LEFT", "textAlignVertical": "TOP",
            "letterSpacing": 0, "lineHeight": None,
            "textAutoResize": "NONE", "textCase": "ORIGINAL", "textDecoration": "NONE",
            "styleRuns": [],
            "boundVariables": {}, "overrides": {}, "componentId": None,
            "pluginData": [], "sharedPluginData": [], "pluginRelaunchData": [],
            "vectorNetwork": None, "arcData": None,
            "fillGeometry": [], "strokeGeometry": [],
            "isMask": False, "maskType": "ALPHA", "expanded": True,
            "horizontalConstraint": "MIN", "verticalConstraint": "MIN",
            "strokeCap": "NONE", "strokeJoin": "MITER", "dashPattern": [],
            "borderTopWeight": 0, "borderRightWeight": 0,
            "borderBottomWeight": 0, "borderLeftWeight": 0,
            "independentStrokeWeights": False, "strokeMiterLimit": 4,
            "strokesIncludedInLayout": False, "itemReverseZIndex": False,
            "counterAxisSpacing": 0, "counterAxisAlignContent": "AUTO",
            "gridTemplateColumns": [], "gridTemplateRows": [],
            "gridColumnGap": 0, "gridRowGap": 0, "gridPosition": None,
            "minWidth": None, "maxWidth": None, "minHeight": None, "maxHeight": None,
            "internalOnly": False, "flipX": False, "flipY": False, "autoRename": True,
            "textTruncation": "DISABLED", "maxLines": None,
            "pointCount": 5, "starInnerRadius": 0.38, "textDirection": "AUTO",
        }

    nodes[root_id] = {
        "id": root_id, "type": "DOCUMENT", "name": "Document",
        "parentId": None, "childIds": [page_id],
        **_empty_defaults(),
    }
    nodes[page_id] = {
        "id": page_id, "type": "CANVAS", "name": "Page 1",
        "parentId": root_id, "childIds": [],
        **_empty_defaults(),
    }

    def convert(figma_node: dict, parent_sg_id: str) -> str:
        sg_id = next_id()
        child_ids = []

        for child in figma_node.get("children", []):
            child_sg_id = convert(child, sg_id)
            child_ids.append(child_sg_id)

        node_type = figma_node.get("type", "FRAME")
        if node_type not in ("FRAME", "TEXT", "RECTANGLE", "ELLIPSE", "VECTOR",
                              "INSTANCE", "COMPONENT", "GROUP", "SECTION",
                              "ROUNDED_RECTANGLE", "LINE", "STAR", "POLYGON"):
            node_type = "FRAME"

        # Font name → split into family/style. Figma sends {family, style},
        # our SceneNode wants fontFamily + fontWeight numeric.
        font_family = "Inter"
        font_weight = 400
        italic = False
        font_name = figma_node.get("fontName")
        if isinstance(font_name, dict):
            if font_name.get("family"): font_family = font_name["family"]
            style = (font_name.get("style") or "").lower()
            italic = "italic" in style
            if "thin" in style: font_weight = 100
            elif "extralight" in style or "ultra light" in style: font_weight = 200
            elif "light" in style: font_weight = 300
            elif "medium" in style: font_weight = 500
            elif "semibold" in style or "demi" in style: font_weight = 600
            elif "extrabold" in style or "ultra bold" in style: font_weight = 800
            elif "black" in style or "heavy" in style: font_weight = 900
            elif "bold" in style: font_weight = 700

        sg_node = {
            "id": sg_id,
            "type": node_type,
            "name": figma_node.get("name", ""),
            "parentId": parent_sg_id,
            "childIds": child_ids,
            # Preserve Figma's actual position (relative to parent in auto-layout
            # is fine; Figma's x/y are absolute on the page but renderer treats
            # them per-parent — same as wireframe-service output).
            "x": figma_node.get("x", 0),
            "y": figma_node.get("y", 0),
            "width": figma_node.get("width", 0),
            "height": figma_node.get("height", 0),
            "rotation": figma_node.get("rotation", 0),
            "fills": figma_node.get("fills") or [],
            "strokes": figma_node.get("strokes") or [],
            "effects": figma_node.get("effects") or [],
            "opacity": figma_node.get("opacity", 1),
            "cornerRadius": figma_node.get("cornerRadius", 0) if isinstance(figma_node.get("cornerRadius"), (int, float)) else 0,
            "topLeftRadius": figma_node.get("topLeftRadius", 0) if isinstance(figma_node.get("topLeftRadius"), (int, float)) else 0,
            "topRightRadius": figma_node.get("topRightRadius", 0) if isinstance(figma_node.get("topRightRadius"), (int, float)) else 0,
            "bottomLeftRadius": figma_node.get("bottomLeftRadius", 0) if isinstance(figma_node.get("bottomLeftRadius"), (int, float)) else 0,
            "bottomRightRadius": figma_node.get("bottomRightRadius", 0) if isinstance(figma_node.get("bottomRightRadius"), (int, float)) else 0,
            "visible": figma_node.get("visible", True),
            "locked": False,
            "clipsContent": figma_node.get("clipsContent", False),
            # Auto-layout
            "layoutMode": figma_node.get("layoutMode", "NONE"),
            "itemSpacing": figma_node.get("itemSpacing", 0),
            "paddingTop": figma_node.get("paddingTop", 0),
            "paddingRight": figma_node.get("paddingRight", 0),
            "paddingBottom": figma_node.get("paddingBottom", 0),
            "paddingLeft": figma_node.get("paddingLeft", 0),
            "primaryAxisSizing": figma_node.get("primaryAxisSizing", "FIXED"),
            "counterAxisSizing": figma_node.get("counterAxisSizing", "FIXED"),
            "primaryAxisAlign": figma_node.get("primaryAxisAlign", "MIN"),
            "counterAxisAlign": figma_node.get("counterAxisAlign", "MIN"),
            "layoutWrap": figma_node.get("layoutWrap", "NO_WRAP"),
            "layoutGrow": figma_node.get("layoutGrow", 0),
            "layoutAlignSelf": figma_node.get("layoutAlignSelf", "AUTO"),
            "layoutPositioning": figma_node.get("layoutPositioning", "AUTO"),
            "blendMode": figma_node.get("blendMode", "PASS_THROUGH"),
            # Text-specific
            "text": figma_node.get("characters", "") if node_type == "TEXT" else "",
            "fontSize": figma_node.get("fontSize", 14) if isinstance(figma_node.get("fontSize"), (int, float)) else 14,
            "fontFamily": font_family,
            "fontWeight": font_weight,
            "italic": italic,
            "textAlignHorizontal": figma_node.get("textAlignHorizontal", "LEFT"),
            "textAlignVertical": figma_node.get("textAlignVertical", "TOP"),
            "letterSpacing": figma_node.get("letterSpacing", 0) if isinstance(figma_node.get("letterSpacing"), (int, float)) else 0,
            "lineHeight": figma_node.get("lineHeight"),
            "textAutoResize": figma_node.get("textAutoResize", "WIDTH_AND_HEIGHT") if node_type == "TEXT" else "NONE",
            "textCase": figma_node.get("textCase", "ORIGINAL"),
            "textDecoration": figma_node.get("textDecoration", "NONE"),
            "styleRuns": figma_node.get("styleRuns", []),
            # open-pencil renderer reads `node.boundVariables['fills/0/color']`
            # etc; absence triggers "Cannot read properties of undefined" mid-render.
            "boundVariables": figma_node.get("boundVariables", {}),
            "overrides": figma_node.get("overrides", {}),
            "componentId": figma_node.get("componentId"),
            "pluginData": figma_node.get("pluginData", []),
            "sharedPluginData": figma_node.get("sharedPluginData", []),
            "pluginRelaunchData": figma_node.get("pluginRelaunchData", []),
            "vectorNetwork": figma_node.get("vectorNetwork"),
            "arcData": figma_node.get("arcData"),
            "fillGeometry": figma_node.get("fillGeometry", []),
            "strokeGeometry": figma_node.get("strokeGeometry", []),
            "isMask": figma_node.get("isMask", False),
            "maskType": figma_node.get("maskType", "ALPHA"),
            "expanded": figma_node.get("expanded", True),
            "horizontalConstraint": figma_node.get("horizontalConstraint", "MIN"),
            "verticalConstraint": figma_node.get("verticalConstraint", "MIN"),
            "strokeCap": figma_node.get("strokeCap", "NONE"),
            "strokeJoin": figma_node.get("strokeJoin", "MITER"),
            "dashPattern": figma_node.get("dashPattern", []),
            "borderTopWeight": figma_node.get("borderTopWeight", 0),
            "borderRightWeight": figma_node.get("borderRightWeight", 0),
            "borderBottomWeight": figma_node.get("borderBottomWeight", 0),
            "borderLeftWeight": figma_node.get("borderLeftWeight", 0),
            "independentStrokeWeights": figma_node.get("independentStrokeWeights", False),
            "independentCorners": figma_node.get("independentCorners", False),
            "cornerSmoothing": figma_node.get("cornerSmoothing", 0),
            "strokesIncludedInLayout": figma_node.get("strokesIncludedInLayout", False),
            "itemReverseZIndex": figma_node.get("itemReverseZIndex", False),
            "counterAxisSpacing": figma_node.get("counterAxisSpacing", 0),
            "counterAxisAlignContent": figma_node.get("counterAxisAlignContent", "AUTO"),
            "gridTemplateColumns": figma_node.get("gridTemplateColumns", []),
            "gridTemplateRows": figma_node.get("gridTemplateRows", []),
            "gridColumnGap": figma_node.get("gridColumnGap", 0),
            "gridRowGap": figma_node.get("gridRowGap", 0),
            "gridPosition": figma_node.get("gridPosition"),
            "minWidth": figma_node.get("minWidth"),
            "maxWidth": figma_node.get("maxWidth"),
            "minHeight": figma_node.get("minHeight"),
            "maxHeight": figma_node.get("maxHeight"),
            "internalOnly": figma_node.get("internalOnly", False),
            "flipX": figma_node.get("flipX", False),
            "flipY": figma_node.get("flipY", False),
            "autoRename": figma_node.get("autoRename", True),
            "textTruncation": figma_node.get("textTruncation", "DISABLED"),
            "maxLines": figma_node.get("maxLines"),
            "pointCount": figma_node.get("pointCount", 5),
            "starInnerRadius": figma_node.get("starInnerRadius", 0.38),
            "textDirection": figma_node.get("textDirection", "AUTO"),
        }
        # Also patch root + page nodes added at the top — they're emitted with a smaller field set.
        nodes[sg_id] = sg_node
        return sg_id

    frame_sg_id = convert(frame_data, page_id)
    nodes[page_id]["childIds"].append(frame_sg_id)

    return {"nodes": nodes, "rootId": root_id, "images": {}}


def _extract_text_overrides_from_export(node: dict) -> dict:
    """Recursively extract ALL text content from children for overrides.
    Uses both node name AND text content as keys for maximum matching."""
    overrides = {}

    def _walk(n):
        if n.get("type") == "TEXT":
            text = n.get("characters", "")
            name = n.get("name", "")
            if text:
                # Key by node name (for structural matching)
                if name:
                    overrides[name.lower()] = text
                # Also key by the text content itself (for content matching)
                # This allows wireframe service to match by original text
                overrides[text.lower()] = text
        for child in n.get("children", []):
            _walk(child)

    _walk(node)
    return overrides


@router.get("/api/figma-plugin/status")
async def plugin_status() -> dict[str, Any]:
    """Check which Figma files have connected plugins."""
    return {
        "connected": list(_connections.keys()),
        "pending_files": list(_pending_updates.keys()),
        "count": len(_connections),
    }
