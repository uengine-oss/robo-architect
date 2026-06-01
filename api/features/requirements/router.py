"""Requirements API (feature router) — 026 requirements-tab.

- Epic(BoundedContext) → Feature → UserStory → AcceptanceCriteria tree
- Feature CRUD
- User Story authoring (propose → confirm), move, delete
- Design-trace subgraph for a User Story's implementing Command
- Background impact reports
"""

from __future__ import annotations

from fastapi import APIRouter

from .routes.bounded_context_crud import router as bounded_context_crud_router
from .routes.canvas import router as canvas_router
from .routes.chat_edit import router as chat_edit_router
from .routes.ddd_export import router as ddd_export_router
from .routes.ddd_wizard import router as ddd_wizard_router
from .routes.child_story_generation import router as child_story_generation_router
from .routes.clarification import router as clarification_router
from .routes.ddd_validation import router as ddd_validation_router
from .routes.deletion_history import router as deletion_history_router
from .routes.design_coverage import router as design_coverage_router
from .routes.design_reflect import router as design_reflect_router
from .routes.design_trace import router as design_trace_router
from .routes.edit import router as edit_router
from .routes.epic_feature_propose import router as epic_feature_propose_router
from .routes.feature_crud import router as feature_crud_router
from .routes.feature_generation import router as feature_generation_router
from .routes.impact_report import router as impact_report_router
from .routes.pivotal_events import router as pivotal_events_router
from .routes.requirements_tree import router as requirements_tree_router
from .routes.user_story_crud import router as user_story_crud_router

router = APIRouter(prefix="/api/requirements", tags=["requirements"])

router.include_router(requirements_tree_router)
router.include_router(bounded_context_crud_router)
router.include_router(deletion_history_router)
router.include_router(chat_edit_router)
router.include_router(child_story_generation_router)
router.include_router(ddd_validation_router)
router.include_router(epic_feature_propose_router)
router.include_router(design_coverage_router)
router.include_router(design_reflect_router)
router.include_router(feature_crud_router)
router.include_router(feature_generation_router)
router.include_router(user_story_crud_router)
router.include_router(edit_router)
router.include_router(design_trace_router)
router.include_router(impact_report_router)
router.include_router(clarification_router)
# 035 — DDD 발견 마법사 & 도메인 캔버스
router.include_router(ddd_wizard_router)
router.include_router(pivotal_events_router)
router.include_router(canvas_router)
router.include_router(ddd_export_router)
