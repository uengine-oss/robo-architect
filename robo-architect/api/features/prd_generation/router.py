"""
PRD Generator API (feature router)

Generates PRD (Product Requirements Document) and AI-friendly project context files
from the current Event Storming model stored in Neo4j.
"""

from __future__ import annotations

from fastapi import APIRouter

from .routes.prd_export import router as prd_export_router
from .routes.tech_stacks import router as tech_stacks_router

router = APIRouter(prefix="/api/prd", tags=["PRD Generator"])

router.include_router(tech_stacks_router)
router.include_router(prd_export_router)


