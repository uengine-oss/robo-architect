from __future__ import annotations

from fastapi import APIRouter

from api.features.requirement_changes.routes.changes_crud import router as crud_router
from api.features.requirement_changes.routes.changes_impact import router as impact_router
from api.features.requirement_changes.routes.changes_changeset import router as changeset_router
from api.features.requirement_changes.routes.changes_approval import router as approval_router
from api.features.requirement_changes.routes.changes_design import router as design_router
from api.features.requirement_changes.routes.changes_tasks import router as tasks_router

router = APIRouter(prefix="/api/requirement-changes", tags=["requirement-changes"])

router.include_router(crud_router)
router.include_router(impact_router)
router.include_router(changeset_router)
router.include_router(approval_router)
router.include_router(design_router)
router.include_router(tasks_router)
