from __future__ import annotations

from fastapi import APIRouter

from .routes.canvas_expansion import router as canvas_expansion_router
from .routes.canvas_event_triggers import router as canvas_event_triggers_router
from .routes.canvas_relationships import router as canvas_relationships_router
from .routes.canvas_subgraph import router as canvas_subgraph_router
from .routes.gwt import router as gwt_router
from .routes.graph_maintenance import router as graph_maintenance_router
from .routes.bigpicture_timeline import router as bigpicture_timeline_router
from .routes.bpmn_process import router as bpmn_process_router
from .routes.event_modeling import router as event_modeling_router
from .routes.traceability import router as traceability_router

router = APIRouter(prefix="/api/graph", tags=["canvas-graph"])

router.include_router(graph_maintenance_router)
router.include_router(canvas_subgraph_router)
router.include_router(canvas_expansion_router)
router.include_router(canvas_event_triggers_router)
router.include_router(canvas_relationships_router)
router.include_router(gwt_router)
router.include_router(bigpicture_timeline_router)
router.include_router(bpmn_process_router)
router.include_router(event_modeling_router)
router.include_router(traceability_router)