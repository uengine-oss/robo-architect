from __future__ import annotations

from fastapi import APIRouter
from starlette.requests import Request

from api.platform.neo4j import get_session
from api.platform.observability.request_logging import http_context
from api.platform.observability.smart_logger import SmartLogger

router = APIRouter(tags=["health"])


@router.get("/api/health")
async def health_check(request: Request):
    """Health check endpoint."""
    SmartLogger.log(
        "INFO",
        "Health check requested: verifying Neo4j connectivity.",
        category="api.health.request",
        params=http_context(request),
    )
    try:
        with get_session() as session:
            session.run("RETURN 1")
        SmartLogger.log(
            "INFO",
            "Health check OK: Neo4j connection verified.",
            category="api.health.ok",
            params={**http_context(request), "neo4j": "connected"},
        )
        return {"status": "healthy", "neo4j": "connected"}
    except Exception as e:
        SmartLogger.log(
            "ERROR",
            "Health check failed: Neo4j connection could not be verified.",
            category="api.health.error",
            params={**http_context(request), "error": {"type": type(e).__name__, "message": str(e)}},
        )
        return {"status": "unhealthy", "error": str(e)}


