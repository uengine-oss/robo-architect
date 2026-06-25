"""040 Proposal Impact Artifact Preview — read-only 미리보기 엔드포인트.

모든 핸들러는 Neo4j **읽기 전용**(오버레이 투영은 메모리 합성). 라이브 그래프에 절대
쓰지 않는다(Constitution I, US2). 응답은 대응 라이브 read 엔드포인트 형태를 미러한다.

prefix(상위 router): /api/proposals → 본 라우터 경로는 /{proposal_id}/preview/...
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from starlette.requests import Request

from api.features.proposal_lifecycle.services.preview_projection import (
    resolve_open_target,
    build_data_preview,
    build_design_preview,
    PreviewError,
)
from api.platform.observability.request_logging import http_context
from api.platform.observability.smart_logger import SmartLogger

router = APIRouter()


# ---------------------------------------------------------------------------
# GET /{id}/preview/resolve — 항목 → 뷰어 라우팅 + 열기 가능 여부
# ---------------------------------------------------------------------------

@router.get("/{proposal_id}/preview/resolve")
async def preview_resolve(
    proposal_id: str,
    request: Request,
    nodeId: Optional[str] = Query(default=None),
    nodeLabel: Optional[str] = Query(default=None),
    nodeTitle: Optional[str] = Query(default=None),
):
    """임팩트/diff 항목 하나가 어떤 뷰어로 열리는지 판정. renderable=false 면 프런트가
    '열기'를 비활성 + 사유 표시(FR-010)."""
    result = resolve_open_target(proposal_id, nodeId, nodeLabel, nodeTitle)
    SmartLogger.log(
        "INFO", "preview_resolve",
        category="proposal_lifecycle.preview.resolve",
        params={**http_context(request), "proposalId": proposal_id,
                "nodeId": nodeId, "nodeLabel": nodeLabel,
                "renderable": result.get("renderable"), "viewer": result.get("viewer")},
    )
    return result


# ---------------------------------------------------------------------------
# GET /{id}/preview/contexts/{bc_id}/full-tree — Data 오버레이 미리보기
# 라이브 GET /api/contexts/{bc}/full-tree 미러 + source/badge
# ---------------------------------------------------------------------------

@router.get("/{proposal_id}/preview/contexts/{bc_id}/full-tree")
async def preview_data_full_tree(proposal_id: str, bc_id: str, request: Request):
    SmartLogger.log(
        "INFO", "preview_projection_start",
        category="proposal_lifecycle.preview.data.start",
        params={**http_context(request), "proposalId": proposal_id, "bcId": bc_id, "viewer": "data"},
    )
    try:
        tree = build_data_preview(proposal_id, bc_id)
    except PreviewError as e:
        raise HTTPException(status_code=404, detail=str(e))

    meta = (tree.get("_preview") or {}).get("meta") or []
    source_dist: dict[str, int] = {}
    for m in meta:
        source_dist[m.get("source", "?")] = source_dist.get(m.get("source", "?"), 0) + 1
    SmartLogger.log(
        "INFO", "preview_projection_built",
        category="proposal_lifecycle.preview.data.done",
        params={**http_context(request), "proposalId": proposal_id, "bcId": bc_id,
                "nodeCount": len(meta), "sourceDist": source_dist},
    )
    return tree


# ---------------------------------------------------------------------------
# GET /{id}/preview/design/{bc_id}/graph — Design(캔버스) 오버레이 미리보기
# 라이브 GET /api/graph/expand-with-bc/{id} 형태({nodes, relationships, bcContext}) 미러
# ---------------------------------------------------------------------------

@router.get("/{proposal_id}/preview/design/{bc_id}/graph")
async def preview_design_graph(proposal_id: str, bc_id: str, request: Request):
    """043-fix: Command/Event '열기' → Design 캔버스에 해당 BC 그래프를 투영(읽기 전용).

    canvasStore.addNodesWithLayout 가 소비하는 `{nodes, relationships, bcContext}` 형태를
    반환한다. CREATE 전용(라이브 미존재) 제안도 오버레이로 그릴 수 있다."""
    SmartLogger.log(
        "INFO", "preview_projection_start",
        category="proposal_lifecycle.preview.design.start",
        params={**http_context(request), "proposalId": proposal_id, "bcId": bc_id, "viewer": "design"},
    )
    try:
        graph = build_design_preview(proposal_id, bc_id)
    except PreviewError as e:
        raise HTTPException(status_code=404, detail=str(e))

    meta = (graph.get("_preview") or {}).get("meta") or []
    SmartLogger.log(
        "INFO", "preview_projection_built",
        category="proposal_lifecycle.preview.design.done",
        params={**http_context(request), "proposalId": proposal_id, "bcId": bc_id,
                "nodeCount": len(graph.get("nodes") or []), "overlayCount": len(meta)},
    )
    return graph
