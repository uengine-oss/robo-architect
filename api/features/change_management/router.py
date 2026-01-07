"""
Change Management API (feature router)

- Impact analysis when a User Story is modified
- LLM-based change plan generation (LangGraph workflow)
- Related object search across BCs
- Human-in-the-loop plan revision (handled inside planning_agent workflow)
- Applying approved changes to Neo4j
"""

from __future__ import annotations

from fastapi import APIRouter

from .routes.change_apply import router as change_apply_router
from .routes.change_history import router as change_history_router
from .routes.change_planning import router as change_planning_router
from .routes.impact_analysis import router as impact_analysis_router
from .routes.model_reference import router as model_reference_router
from .routes.related_object_search import router as related_object_search_router

router = APIRouter(prefix="/api/change", tags=["change"])

router.include_router(impact_analysis_router)
router.include_router(change_planning_router)
router.include_router(change_apply_router)
router.include_router(change_history_router)
router.include_router(related_object_search_router)
router.include_router(model_reference_router)


