"""
Figma REST API integration — browse files, fetch frame nodes, get thumbnails.

Pattern follows confluence.py: Pydantic models, httpx async client, error handling.
"""

from __future__ import annotations

import asyncio
from typing import Any

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from api.platform.observability.smart_logger import SmartLogger

router = APIRouter(prefix="/api/ingest/figma-api", tags=["figma-api"])

FIGMA_API_BASE = "https://api.figma.com/v1"
_TIMEOUT = 30.0
# Simple concurrency limiter to respect Figma's 120 calls/min rate limit
_semaphore = asyncio.Semaphore(10)


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class FigmaCredentials(BaseModel):
    api_token: str
    file_key: str


class FigmaNodeFetchRequest(BaseModel):
    api_token: str
    file_key: str
    node_ids: list[str]


class FigmaThumbnailRequest(BaseModel):
    api_token: str
    file_key: str
    node_ids: list[str]
    scale: float = 0.5
    format: str = "png"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _figma_headers(api_token: str) -> dict[str, str]:
    return {"X-Figma-Token": api_token, "Accept": "application/json"}


def _check_figma_response(resp: httpx.Response) -> None:
    if resp.status_code == 403:
        SmartLogger.log("WARNING", f"Figma 403: {resp.text[:200]}", category="figma_api.auth")
        raise HTTPException(status_code=403, detail="Figma API 인증 실패: API 토큰을 확인하세요.")
    if resp.status_code == 404:
        SmartLogger.log("WARNING", f"Figma 404: {resp.text[:200]}", category="figma_api.not_found")
        raise HTTPException(status_code=404, detail="Figma 파일을 찾을 수 없습니다. File Key를 확인하세요.")
    if resp.status_code == 429:
        SmartLogger.log("WARNING", "Figma rate limit hit", category="figma_api.rate_limit")
        raise HTTPException(status_code=429, detail="Figma API 요청 한도 초과. 잠시 후 다시 시도하세요.")


def _extract_frames(node: dict, depth: int = 0) -> list[dict]:
    """Extract FRAME children from a Figma node (recursively up to depth 1)."""
    frames = []
    for child in node.get("children", []):
        if child.get("type") in ("FRAME", "COMPONENT", "COMPONENT_SET"):
            bb = child.get("absoluteBoundingBox", {})
            frames.append({
                "id": child["id"],
                "name": child.get("name", ""),
                "type": child.get("type", "FRAME"),
                "width": round(bb.get("width", 0)),
                "height": round(bb.get("height", 0)),
            })
    return frames


# ---------------------------------------------------------------------------
# Figma node → simplified format (same as clipboard paste)
# ---------------------------------------------------------------------------

def figma_api_node_to_simplified(
    node: dict,
    parent_id: str | None = None,
) -> list[dict]:
    """
    Convert a Figma REST API node tree to the simplified format used by the
    existing clipboard-paste ingestion pipeline.

    Figma REST API node:
      { id: "123:456", type: "FRAME", name: "...",
        absoluteBoundingBox: {x, y, width, height},
        characters: "text content",
        children: [...] }

    Output (matches handleFigmaPaste format):
      { id, type, name, text, width, height, parentId, visible }
    """
    result: list[dict] = []
    bb = node.get("absoluteBoundingBox") or node.get("absoluteRenderBounds") or {}
    node_type = node.get("type", "FRAME")

    simplified: dict[str, Any] = {
        "id": node.get("id", ""),
        "type": node_type,
        "name": node.get("name", ""),
        "width": round(bb.get("width", 0)),
        "height": round(bb.get("height", 0)),
        "visible": node.get("visible", True),
        "parentId": parent_id,
    }

    # Text content
    if node_type == "TEXT":
        simplified["text"] = node.get("characters", "")
    else:
        simplified["text"] = ""

    result.append(simplified)

    # Recurse into children
    for child in node.get("children", []):
        result.extend(figma_api_node_to_simplified(child, parent_id=node.get("id")))

    return result


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/pages")
async def list_figma_pages(creds: FigmaCredentials) -> dict[str, Any]:
    """
    Connect to a Figma file and list all pages with their top-level frames.
    """
    SmartLogger.log(
        "INFO",
        "Figma API pages requested",
        category="figma_api.pages.request",
        params={"file_key": creds.file_key, "token_length": len(creds.api_token)},
    )

    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            async with _semaphore:
                resp = await client.get(
                    f"{FIGMA_API_BASE}/files/{creds.file_key}",
                    params={"depth": 2},
                    headers=_figma_headers(creds.api_token),
                )
            _check_figma_response(resp)
            resp.raise_for_status()

    except HTTPException:
        raise
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=502, detail=f"Figma API 오류: {e.response.status_code}")
    except httpx.RequestError as e:
        raise HTTPException(status_code=502, detail=f"Figma 연결 실패: {e}")

    data = resp.json()
    file_name = data.get("name", "")
    document = data.get("document", {})

    pages = []
    for page_node in document.get("children", []):
        if page_node.get("type") != "CANVAS":
            continue
        frames = _extract_frames(page_node)
        pages.append({
            "id": page_node["id"],
            "name": page_node.get("name", ""),
            "frames": frames,
        })

    SmartLogger.log(
        "INFO",
        f"Figma file loaded: {file_name}, {len(pages)} pages",
        category="figma_api.pages.done",
        params={"file_name": file_name, "page_count": len(pages)},
    )

    return {"fileName": file_name, "fileKey": creds.file_key, "pages": pages}


@router.post("/nodes")
async def fetch_figma_nodes(req: FigmaNodeFetchRequest) -> dict[str, Any]:
    """
    Fetch the full node trees for selected frames.
    Returns simplified nodes in the same format as clipboard paste.
    """
    if not req.node_ids:
        raise HTTPException(status_code=400, detail="node_ids must not be empty")

    SmartLogger.log(
        "INFO",
        f"Figma API nodes requested: {len(req.node_ids)} frames",
        category="figma_api.nodes.request",
        params={"file_key": req.file_key, "node_count": len(req.node_ids)},
    )

    # Figma API accepts comma-separated node IDs
    ids_param = ",".join(req.node_ids)

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            async with _semaphore:
                resp = await client.get(
                    f"{FIGMA_API_BASE}/files/{req.file_key}/nodes",
                    params={"ids": ids_param},
                    headers=_figma_headers(req.api_token),
                )
            _check_figma_response(resp)
            resp.raise_for_status()

    except HTTPException:
        raise
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=502, detail=f"Figma API 오류: {e.response.status_code}")
    except httpx.RequestError as e:
        raise HTTPException(status_code=502, detail=f"Figma 연결 실패: {e}")

    data = resp.json()
    nodes_map = data.get("nodes", {})

    # Convert each frame's node tree to simplified format
    all_simplified: list[dict] = []
    node_id_to_name: dict[str, str] = {}

    for node_id, node_data in nodes_map.items():
        doc = node_data.get("document")
        if not doc:
            continue
        frame_name = doc.get("name", node_id)
        node_id_to_name[node_id] = frame_name
        simplified = figma_api_node_to_simplified(doc)
        all_simplified.extend(simplified)

    SmartLogger.log(
        "INFO",
        f"Fetched {len(all_simplified)} nodes from {len(nodes_map)} frames",
        category="figma_api.nodes.done",
    )

    return {
        "figma_nodes": all_simplified,
        "node_id_map": node_id_to_name,
        "total_nodes": len(all_simplified),
    }


@router.post("/thumbnails")
async def get_figma_thumbnails(req: FigmaThumbnailRequest) -> dict[str, Any]:
    """
    Get rendered thumbnail image URLs for selected frames.
    """
    if not req.node_ids:
        raise HTTPException(status_code=400, detail="node_ids must not be empty")

    ids_param = ",".join(req.node_ids)

    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            async with _semaphore:
                resp = await client.get(
                    f"{FIGMA_API_BASE}/images/{req.file_key}",
                    params={
                        "ids": ids_param,
                        "format": req.format,
                        "scale": req.scale,
                    },
                    headers=_figma_headers(req.api_token),
                )
            _check_figma_response(resp)
            resp.raise_for_status()

    except HTTPException:
        raise
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=502, detail=f"Figma API 오류: {e.response.status_code}")
    except httpx.RequestError as e:
        raise HTTPException(status_code=502, detail=f"Figma 연결 실패: {e}")

    data = resp.json()
    images = data.get("images", {})

    return {"images": images}
