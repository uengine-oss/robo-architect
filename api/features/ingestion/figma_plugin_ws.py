"""
WebSocket bridge for Figma Plugin ↔ RoboArchitect.

The Figma plugin connects via WebSocket and receives node update commands.
InspectorPanel/other frontends send updates via the REST API,
which are relayed to the connected plugin.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException
from pydantic import BaseModel

from api.platform.neo4j import get_session
from api.platform.observability.smart_logger import SmartLogger

router = APIRouter(tags=["figma-plugin"])

# ── Connected plugins registry (file_key → WebSocket) ──
_connections: dict[str, WebSocket] = {}
_lock = asyncio.Lock()


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


@router.get("/api/figma-plugin/poll")
async def poll_updates(file_key: str = "") -> dict[str, Any]:
    """Plugin polls this endpoint to get pending update commands."""
    if not file_key:
        return {"updates": []}

    async with _pending_lock:
        updates = _pending_updates.pop(file_key, [])

    return {"updates": updates, "count": len(updates)}


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

    # Root + Page
    nodes[root_id] = {
        "id": root_id, "type": "DOCUMENT", "name": "Document",
        "parentId": None, "childIds": [page_id],
        "x": 0, "y": 0, "width": 0, "height": 0, "rotation": 0,
        "fills": [], "strokes": [], "effects": [], "opacity": 1,
        "cornerRadius": 0, "visible": True, "locked": False,
        "clipsContent": False, "layoutMode": "NONE",
        "text": "", "fontSize": 14, "fontFamily": "Inter", "fontWeight": 400,
    }
    nodes[page_id] = {
        "id": page_id, "type": "CANVAS", "name": "Page 1",
        "parentId": root_id, "childIds": [],
        "x": 0, "y": 0, "width": 0, "height": 0, "rotation": 0,
        "fills": [], "strokes": [], "effects": [], "opacity": 1,
        "cornerRadius": 0, "visible": True, "locked": False,
        "clipsContent": False, "layoutMode": "NONE",
        "text": "", "fontSize": 14, "fontFamily": "Inter", "fontWeight": 400,
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

        sg_node = {
            "id": sg_id,
            "type": node_type,
            "name": figma_node.get("name", ""),
            "parentId": parent_sg_id,
            "childIds": child_ids,
            "x": 0, "y": 0,
            "width": figma_node.get("width", 0),
            "height": figma_node.get("height", 0),
            "rotation": 0,
            "fills": [], "strokes": [], "effects": [],
            "opacity": 1, "cornerRadius": 0,
            "visible": figma_node.get("visible", True),
            "locked": False, "clipsContent": False,
            "layoutMode": "NONE",
            "text": figma_node.get("characters", "") if node_type == "TEXT" else "",
            "fontSize": figma_node.get("fontSize", 14) if node_type == "TEXT" else 14,
            "fontFamily": "Inter", "fontWeight": 400,
        }
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
