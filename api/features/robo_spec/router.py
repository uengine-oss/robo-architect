"""HTTP routes for robo-spec + MCP server mount.

Contracts:
- ``specs/029-robo-spec-skills/contracts/http-api.md`` — E2..E6 (the E1
  extension lives in ``api/features/claude_code/router.py``).
- ``specs/029-robo-spec-skills/contracts/mcp-tools.md`` — mounted at
  ``/mcp`` (streamable-HTTP transport).

The MCP mount is tolerant of a missing ``mcp`` SDK: if the SDK fails
to import, the app boots with the HTTP surface intact and a clear log
line pointing at the install command. This keeps developers unblocked
while the dependency is rolling out across local environments.
"""

from __future__ import annotations

from contextlib import AsyncExitStack, asynccontextmanager
from typing import Any

from fastapi import APIRouter, FastAPI

from api.features.robo_spec.mcp_server import build_mcp_server
from api.platform.observability.smart_logger import SmartLogger

router = APIRouter(prefix="/api/robo-spec", tags=["robo-spec"])


@router.get("/health", include_in_schema=True)
async def health() -> dict[str, str]:
    """Liveness probe for the robo-spec sub-system."""
    return {"status": "ok", "feature": "robo-spec", "spec": "029"}


# Module-level singleton — built once at import time, reused by the
# lifespan context manager and by ``mount_mcp``.
_mcp_server: Any | None = build_mcp_server()


@asynccontextmanager
async def mcp_lifespan():
    """Run the FastMCP session manager for the lifetime of the app.

    The streamable-HTTP transport's request handler relies on a task
    group that is created by ``session_manager.run()``. Without this
    wrapper, the first POST to ``/mcp/`` raises
    ``RuntimeError: Task group is not initialized``.

    FastAPI's ``app.mount()`` does **not** propagate the mounted
    sub-app's lifespan, so we chain explicitly from the main
    application's lifespan (see ``api/main.py``).
    """
    if _mcp_server is None or not hasattr(_mcp_server, "session_manager"):
        yield
        return
    async with _mcp_server.session_manager.run():
        SmartLogger.log(
            "INFO",
            "MCP session manager started (streamable-HTTP task group live).",
            category="robo_spec.mcp.session_manager_started",
        )
        try:
            yield
        finally:
            SmartLogger.log(
                "INFO",
                "MCP session manager stopping.",
                category="robo_spec.mcp.session_manager_stopping",
            )


def mount_mcp(app: FastAPI) -> None:
    """Mount the streamable-HTTP MCP transport under ``/mcp`` on the given
    FastAPI app. Idempotent and safe to call before any tool is registered.

    Called once from ``api/main.py`` after ``app.include_router(router)``.
    The lifespan chaining for ``session_manager.run()`` is set up
    separately in ``api/main.py``'s ``lifespan`` context.
    """
    if _mcp_server is None:
        return
    try:
        app.mount("/mcp", _mcp_server.streamable_http_app())
        SmartLogger.log(
            "INFO",
            "MCP streamable-HTTP transport mounted at /mcp.",
            category="robo_spec.mcp.mounted",
        )
    except Exception as e:  # noqa: BLE001 — startup must not crash on MCP
        SmartLogger.log(
            "ERROR",
            f"Failed to mount MCP at /mcp: {e}",
            category="robo_spec.mcp.mount_failed",
            params={"error": str(e)},
        )
