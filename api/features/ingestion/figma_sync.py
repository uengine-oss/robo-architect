"""
Figma bidirectional sync — pull frames from Figma, push .fig back.

Endpoints:
  POST /api/ingest/figma-sync/pull   — Figma frame → local UI sceneGraph
  POST /api/ingest/figma-sync/push   — local UI sceneGraph → .fig download
  GET  /api/ingest/figma-sync/status/{ui_node_id} — sync status
"""

from __future__ import annotations

import io
import json
from typing import Any

import httpx
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from api.platform.neo4j import get_session
from api.platform.observability.smart_logger import SmartLogger
from api.features.ingestion.figma_api import (
    FIGMA_API_BASE,
    _figma_headers,
    _check_figma_response,
    _semaphore,
)

router = APIRouter(prefix="/api/ingest/figma-sync", tags=["figma-sync"])

import os as _os
_WIREFRAME_SERVICE_URL = _os.getenv("WIREFRAME_SERVICE_URL", "http://localhost:7610")


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class FigmaPullRequest(BaseModel):
    api_token: str
    file_key: str
    figma_node_id: str
    ui_node_id: str


class FigmaPushRequest(BaseModel):
    ui_node_id: str


# ---------------------------------------------------------------------------
# Pull: Figma → local
# ---------------------------------------------------------------------------

@router.post("/pull")
async def pull_from_figma(req: FigmaPullRequest) -> dict[str, Any]:
    """
    Pull a Figma frame's current state and update the local UI node's sceneGraph.
    """
    # 1. Fetch the frame node tree from Figma API
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            async with _semaphore:
                resp = await client.get(
                    f"{FIGMA_API_BASE}/files/{req.file_key}/nodes",
                    params={"ids": req.figma_node_id},
                    headers=_figma_headers(req.api_token),
                )
            _check_figma_response(resp)
            resp.raise_for_status()
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Figma API 오류: {e}")

    data = resp.json()
    node_data = data.get("nodes", {}).get(req.figma_node_id)
    if not node_data or not node_data.get("document"):
        raise HTTPException(status_code=404, detail=f"Figma 노드 {req.figma_node_id}를 찾을 수 없습니다.")

    doc = node_data["document"]

    # 2. Extract component instances from Figma frame and render via wireframe service
    scene_graph = await _render_figma_frame_as_components(doc)

    # 3. Save to Neo4j
    sg_str = json.dumps(scene_graph, ensure_ascii=False)
    with get_session() as session:
        result = session.run(
            """
            MATCH (ui:UI {id: $ui_id})
            SET ui.sceneGraph = $sg,
                ui.figmaFileKey = $file_key,
                ui.figmaNodeId = $figma_node_id,
                ui.updatedAt = datetime()
            RETURN ui {.id, .name, .figmaFileKey, .figmaNodeId} as ui
            """,
            ui_id=req.ui_node_id,
            sg=sg_str,
            file_key=req.file_key,
            figma_node_id=req.figma_node_id,
        ).single()
        if not result:
            raise HTTPException(status_code=404, detail=f"UI 노드 {req.ui_node_id}를 찾을 수 없습니다.")

    SmartLogger.log(
        "INFO",
        f"Pulled Figma frame {req.figma_node_id} → UI {req.ui_node_id}",
        category="figma_sync.pull",
    )

    return {
        "ok": True,
        "ui": dict(result["ui"]),
        "sceneGraph": sg_str,
        "nodeCount": len(scene_graph.get("nodes", {})),
    }


# ---------------------------------------------------------------------------
# Push: local → Figma (.fig download)
# ---------------------------------------------------------------------------

@router.post("/push")
async def push_to_figma(req: FigmaPushRequest) -> StreamingResponse:
    """
    Export the local UI node's sceneGraph as a .fig file for import into Figma.
    (Figma REST API does not support direct node modification by third parties.)
    """
    with get_session() as session:
        rec = session.run(
            "MATCH (ui:UI {id: $id}) RETURN ui.sceneGraph as sg, ui.name as name, ui.displayName as dn, ui.figmaNodeId as fid",
            id=req.ui_node_id,
        ).single()
        if not rec:
            raise HTTPException(status_code=404, detail=f"UI 노드 {req.ui_node_id}를 찾을 수 없습니다.")

    sg_str = rec.get("sg")
    if not sg_str:
        raise HTTPException(status_code=400, detail="sceneGraph 데이터가 없습니다.")

    scene_graph = json.loads(sg_str) if isinstance(sg_str, str) else sg_str
    ui_name = rec.get("dn") or rec.get("name") or "wireframe"

    # Call wireframe service to export as .fig
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                f"{_WIREFRAME_SERVICE_URL}/export-fig",
                json={"sceneGraph": scene_graph, "name": ui_name},
            )
            resp.raise_for_status()
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Wireframe service 오류: {e}")

    safe_name = ui_name.replace('"', '').replace("'", "")[:50]
    return StreamingResponse(
        io.BytesIO(resp.content),
        media_type="application/octet-stream",
        headers={"Content-Disposition": f'attachment; filename="{safe_name}.fig"'},
    )


# ---------------------------------------------------------------------------
# Status
# ---------------------------------------------------------------------------

@router.get("/status/{ui_node_id}")
async def sync_status(ui_node_id: str) -> dict[str, Any]:
    """
    Check the Figma sync status of a UI node.
    """
    with get_session() as session:
        rec = session.run(
            """
            MATCH (ui:UI {id: $id})
            RETURN ui.figmaFileKey as fileKey,
                   ui.figmaNodeId as nodeId,
                   ui.updatedAt as updatedAt
            """,
            id=ui_node_id,
        ).single()
        if not rec:
            raise HTTPException(status_code=404, detail=f"UI 노드 {ui_node_id}를 찾을 수 없습니다.")

    file_key = rec.get("fileKey")
    node_id = rec.get("nodeId")
    updated = rec.get("updatedAt")

    return {
        "linked": bool(file_key and node_id),
        "figmaFileKey": file_key,
        "figmaNodeId": node_id,
        "lastUpdated": str(updated) if updated else None,
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _render_figma_frame_as_components(doc: dict) -> dict:
    """
    Extract component instance names from a Figma frame's children,
    then call wireframe service /render to build a SceneGraph with
    matching open-pencil component instances.
    """
    frame_name = doc.get("name", "Wireframe")
    children = doc.get("children", [])

    # Extract component placements from top-level children
    components: list[dict] = []
    for child in children:
        child_type = child.get("type", "")
        child_name = child.get("name", "")

        if child_type == "INSTANCE":
            # Instance — use the component name directly
            # Also extract text overrides from TEXT children
            overrides = _extract_text_overrides(child)
            components.append({"component": child_name, "overrides": overrides})
        elif child_type in ("FRAME", "GROUP", "COMPONENT"):
            # Regular frame/group — try to match as a component
            overrides = _extract_text_overrides(child)
            components.append({"component": child_name, "overrides": overrides})

    if not components:
        # Fallback: just build a minimal scene graph
        return _build_scene_graph_from_figma_nodes_simple(doc)

    # Call wireframe service /render
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                f"{_WIREFRAME_SERVICE_URL}/render",
                json={
                    "name": frame_name,
                    "width": round(doc.get("absoluteBoundingBox", {}).get("width", 375)),
                    "height": round(doc.get("absoluteBoundingBox", {}).get("height", 812)),
                    "components": components,
                },
            )
            if resp.status_code == 200:
                return resp.json()
    except Exception as e:
        SmartLogger.log("WARN", f"Wireframe service render failed: {e}", category="figma_sync.render")

    # Fallback
    return _build_scene_graph_from_figma_nodes_simple(doc)


def _extract_text_overrides(node: dict) -> dict:
    """Recursively extract text content from TEXT children for overrides."""
    overrides = {}
    for child in node.get("children", []):
        if child.get("type") == "TEXT":
            text = child.get("characters", "")
            name = child.get("name", "")
            if text and name:
                overrides[name.lower()] = text
            elif text:
                overrides["title"] = text
        # Recurse one level
        for grandchild in child.get("children", []):
            if grandchild.get("type") == "TEXT":
                text = grandchild.get("characters", "")
                name = grandchild.get("name", "")
                if text and name:
                    overrides[name.lower()] = text
    return overrides


def _build_scene_graph_from_figma_nodes_simple(doc: dict) -> dict:
    """Fallback: build minimal SceneGraph from Figma API node structure."""
    from api.features.ingestion.figma_api import figma_api_node_to_simplified
    simplified = figma_api_node_to_simplified(doc)
    return _build_scene_graph_from_figma_nodes(simplified, doc.get("name", "Wireframe"))


def _build_scene_graph_from_figma_nodes(
    simplified_nodes: list[dict],
    frame_name: str,
) -> dict:
    """
    Build a minimal SerializedSceneGraph from simplified Figma API nodes.
    Creates a root DOCUMENT → CANVAS → FRAME structure with child nodes.
    """
    from api.platform.open_pencil_client import render_wireframe

    # Try wireframe service first (if available)
    # Build component list from the simplified nodes for the render endpoint
    # For now, build a basic scene graph directly
    nodes: dict[str, dict] = {}
    root_id = "0:0"
    page_id = "0:1"

    # Root document node
    nodes[root_id] = {
        "id": root_id, "type": "DOCUMENT", "name": "Document",
        "parentId": None, "childIds": [page_id],
        "x": 0, "y": 0, "width": 0, "height": 0, "rotation": 0,
        "fills": [], "strokes": [], "effects": [], "opacity": 1,
        "cornerRadius": 0, "visible": True, "locked": False,
        "clipsContent": False, "layoutMode": "NONE",
    }

    # Page canvas node
    nodes[page_id] = {
        "id": page_id, "type": "CANVAS", "name": "Page 1",
        "parentId": root_id, "childIds": [],
        "x": 0, "y": 0, "width": 0, "height": 0, "rotation": 0,
        "fills": [], "strokes": [], "effects": [], "opacity": 1,
        "cornerRadius": 0, "visible": True, "locked": False,
        "clipsContent": False, "layoutMode": "NONE",
    }

    # Find the root frame in simplified nodes (first node without parentId or with parentId=None)
    root_frames = [n for n in simplified_nodes if not n.get("parentId")]
    if not root_frames and simplified_nodes:
        root_frames = [simplified_nodes[0]]

    # Build node ID → children map
    children_map: dict[str, list[str]] = {}
    node_by_id: dict[str, dict] = {}
    for n in simplified_nodes:
        nid = n["id"]
        node_by_id[nid] = n
        pid = n.get("parentId")
        if pid:
            children_map.setdefault(pid, []).append(nid)

    # Convert each simplified node to a scene graph node
    def convert_node(sn: dict, parent_sg_id: str) -> str:
        sg_id = sn["id"].replace(":", "_")  # Figma IDs use ":" which may conflict
        child_ids = []
        for child_fid in children_map.get(sn["id"], []):
            child = node_by_id.get(child_fid)
            if child:
                child_sg_id = convert_node(child, sg_id)
                child_ids.append(child_sg_id)

        node_type = sn.get("type", "FRAME")
        if node_type not in ("FRAME", "TEXT", "RECTANGLE", "ELLIPSE", "VECTOR",
                              "INSTANCE", "COMPONENT", "GROUP", "SECTION",
                              "ROUNDED_RECTANGLE", "LINE", "STAR", "POLYGON"):
            node_type = "FRAME"

        sg_node: dict[str, Any] = {
            "id": sg_id,
            "type": node_type,
            "name": sn.get("name", ""),
            "parentId": parent_sg_id,
            "childIds": child_ids,
            "x": 0, "y": 0,
            "width": sn.get("width", 0),
            "height": sn.get("height", 0),
            "rotation": 0,
            "fills": [], "strokes": [], "effects": [],
            "opacity": 1, "cornerRadius": 0,
            "visible": sn.get("visible", True),
            "locked": False, "clipsContent": False,
            "layoutMode": "NONE",
            "text": sn.get("text", "") if node_type == "TEXT" else "",
            "fontSize": 14, "fontFamily": "Inter", "fontWeight": 400,
        }

        nodes[sg_id] = sg_node
        return sg_id

    for rf in root_frames:
        frame_sg_id = convert_node(rf, page_id)
        nodes[page_id]["childIds"].append(frame_sg_id)

    return {"nodes": nodes, "rootId": root_id, "images": {}}
