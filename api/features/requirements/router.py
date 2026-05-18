"""Requirements API (feature router) — 026 requirements-tab.

- Epic(BoundedContext) → Feature → UserStory → AcceptanceCriteria tree
- Feature CRUD
- User Story authoring (propose → confirm), move, delete
- Design-trace subgraph for a User Story's implementing Command
- Background impact reports
"""

from __future__ import annotations

from fastapi import APIRouter

from .routes.design_trace import router as design_trace_router
from .routes.feature_crud import router as feature_crud_router
from .routes.impact_report import router as impact_report_router
from .routes.requirements_tree import router as requirements_tree_router
from .routes.user_story_crud import router as user_story_crud_router

router = APIRouter(prefix="/api/requirements", tags=["requirements"])

router.include_router(requirements_tree_router)
router.include_router(feature_crud_router)
router.include_router(user_story_crud_router)
router.include_router(design_trace_router)
router.include_router(impact_report_router)
