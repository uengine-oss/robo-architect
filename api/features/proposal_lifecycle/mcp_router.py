from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI

from api.features.proposal_lifecycle.mcp_server import build_mcp_server
from api.platform.observability.smart_logger import SmartLogger

_mcp_server: Any | None = build_mcp_server()


@asynccontextmanager
async def mcp_lifespan():
    if _mcp_server is None or not hasattr(_mcp_server, "session_manager"):
        yield
        return
    async with _mcp_server.session_manager.run():
        SmartLogger.log(
            "INFO",
            "Proposal MCP session manager started.",
            category="proposal_lifecycle.mcp.session_manager_started",
        )
        try:
            yield
        finally:
            SmartLogger.log(
                "INFO",
                "Proposal MCP session manager stopping.",
                category="proposal_lifecycle.mcp.session_manager_stopping",
            )


def mount_mcp(app: FastAPI) -> None:
    if _mcp_server is None:
        return
    try:
        app.mount("/mcp/proposals", _mcp_server.streamable_http_app())
        SmartLogger.log(
            "INFO",
            "Proposal MCP streamable-HTTP transport mounted at /mcp/proposals.",
            category="proposal_lifecycle.mcp.mounted",
        )
    except Exception as e:  # noqa: BLE001
        SmartLogger.log(
            "ERROR",
            f"Failed to mount Proposal MCP at /mcp/proposals: {e}",
            category="proposal_lifecycle.mcp.mount_failed",
            params={"error": str(e)},
        )
