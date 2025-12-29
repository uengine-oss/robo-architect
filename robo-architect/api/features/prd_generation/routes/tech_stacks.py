from __future__ import annotations

from fastapi import APIRouter
from starlette.requests import Request

from api.features.prd_generation.prd_tech_stack_catalog import build_tech_stack_options
from api.platform.observability.request_logging import http_context
from api.platform.observability.smart_logger import SmartLogger

router = APIRouter()


@router.get("/tech-stacks")
async def get_available_tech_stacks(request: Request):
    SmartLogger.log(
        "INFO",
        "PRD: tech stack options requested.",
        category="api.prd.tech_stacks.request",
        params=http_context(request),
    )
    payload = build_tech_stack_options()
    SmartLogger.log(
        "INFO",
        "PRD: tech stack options returned.",
        category="api.prd.tech_stacks.done",
        params={**http_context(request), "summary": {"keys": list(payload.keys())}},
    )
    return payload


