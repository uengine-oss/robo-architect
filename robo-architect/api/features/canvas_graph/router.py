from __future__ import annotations

from fastapi import APIRouter

from .routes.canvas_expansion import router as canvas_expansion_router
from .routes.canvas_event_triggers import router as canvas_event_triggers_router
from .routes.canvas_relationships import router as canvas_relationships_router
from .routes.canvas_subgraph import router as canvas_subgraph_router
from .routes.graph_maintenance import router as graph_maintenance_router

router = APIRouter(prefix="/api/graph", tags=["canvas-graph"])

router.include_router(graph_maintenance_router)
router.include_router(canvas_subgraph_router)
router.include_router(canvas_expansion_router)
router.include_router(canvas_event_triggers_router)
router.include_router(canvas_relationships_router)
