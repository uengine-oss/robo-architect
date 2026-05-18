"""Requirements tree route (026 — requirements-tab)."""

from __future__ import annotations

from fastapi import APIRouter
from starlette.requests import Request

from api.features.requirements.requirements_contracts import RequirementsTreeDTO
from api.features.requirements.tree_service import build_requirements_tree
from api.platform.observability.request_logging import http_context
from api.platform.observability.smart_logger import SmartLogger

router = APIRouter()


@router.get("/tree", response_model=RequirementsTreeDTO)
async def get_requirements_tree(request: Request) -> RequirementsTreeDTO:
    """Epic(BoundedContext) → Feature → UserStory → AcceptanceCriteria tree."""
    SmartLogger.log(
        "INFO",
        "Requirements tree requested.",
        category="requirements.tree.request",
        params={**http_context(request)},
    )
    tree = build_requirements_tree()
    SmartLogger.log(
        "INFO",
        "Requirements tree built.",
        category="requirements.tree.done",
        params={
            **http_context(request),
            "epics": len(tree.epics),
            "unassigned": len(tree.unassigned),
        },
    )
    return tree
