from __future__ import annotations

from fastapi import APIRouter

from api.features.proposal_lifecycle.routes.proposals_crud import router as crud_router
from api.features.proposal_lifecycle.routes.proposals_intent import router as intent_router
from api.features.proposal_lifecycle.routes.proposals_constitution import router as constitution_router
from api.features.proposal_lifecycle.routes.proposals_plan import router as plan_router
from api.features.proposal_lifecycle.routes.proposals_tasks import router as tasks_router
from api.features.proposal_lifecycle.routes.proposals_sandbox import router as sandbox_router
from api.features.proposal_lifecycle.routes.proposals_testing import router as testing_router
from api.features.proposal_lifecycle.routes.proposals_acceptance import router as acceptance_router
from api.features.proposal_lifecycle.routes.proposals_preview import router as preview_router
from api.features.proposal_lifecycle.routes.proposals_preview_edit import router as preview_edit_router
from api.features.proposal_lifecycle.routes.proposals_staged import router as staged_router
from api.features.proposal_lifecycle.routes.proposals_oda import router as oda_router

router = APIRouter(prefix="/api/proposals", tags=["proposals"])

router.include_router(crud_router)
router.include_router(intent_router)
router.include_router(constitution_router)
router.include_router(plan_router)
router.include_router(tasks_router)
router.include_router(sandbox_router)
router.include_router(testing_router)
router.include_router(acceptance_router)
router.include_router(preview_router)
router.include_router(preview_edit_router)
router.include_router(staged_router)
router.include_router(oda_router)
