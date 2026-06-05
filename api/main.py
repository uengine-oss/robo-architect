"""
FastAPI Backend for Event Storming Navigator

Provides REST APIs for:
- BC (Bounded Context) listing and tree structure
- Subgraph queries for canvas rendering
- Document ingestion with real-time progress streaming
"""

from __future__ import annotations

from dotenv import load_dotenv
load_dotenv()

import os
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from starlette.requests import Request
from starlette.responses import Response
from fastapi.middleware.cors import CORSMiddleware

from api.platform.observability.request_logging import (
    RequestTimer,
    http_context,
    new_request_id,
    set_request_id,
)
from api.platform.observability.smart_logger import SmartLogger
from api.platform.middleware.language_middleware import language_middleware
from api.platform.neo4j import init_neo4j_driver, close_neo4j_driver

# Neo4j 드라이버의 경고 로그 필터링
# "Received notification from DBMS server" 메시지를 필터링
class Neo4jNotificationFilter(logging.Filter):
    """Neo4j DBMS notification 경고를 필터링하는 필터"""
    def filter(self, record):
        # "Received notification from DBMS server" 메시지 필터링
        if "Received notification from DBMS server" in record.getMessage():
            return False
        return True

# Neo4j 로거에 필터 적용
neo4j_logger = logging.getLogger("neo4j")
neo4j_logger.addFilter(Neo4jNotificationFilter())
# Neo4j 로거의 레벨을 ERROR로 설정하여 WARNING 메시지 차단
neo4j_logger.setLevel(logging.ERROR)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage Neo4j connection lifecycle + Robo-Spec MCP session manager."""
    SmartLogger.log(
        "INFO",
        "Starting API (lifespan init)",
        category="api.lifespan",
        params={
            "logger_impl": getattr(SmartLogger, "impl_source", "unknown"),
        },
    )
    init_neo4j_driver(log=True)
    # Apply ingestion cache default (on by default; override INGESTION_CACHE_DEFAULT=0).
    try:
        from api.features.ingestion.langchain_cache import ensure_default_cache_state
        ensure_default_cache_state()
    except Exception as e:  # noqa: BLE001 — cache is best-effort
        SmartLogger.log(
            "WARN",
            f"Failed to apply ingestion cache default: {e}",
            category="ingestion.cache.default_failed",
            params={"error": str(e)},
        )
    # 020: release any stale Figma full-sync locks left over from a prior crash.
    try:
        from api.features.figma_binding.service import release_stale_locks_on_startup
        release_stale_locks_on_startup()
    except Exception as e:  # noqa: BLE001 — recovery is best-effort
        SmartLogger.log(
            "WARN",
            f"Failed to release stale figma_binding locks: {e}",
            category="figma_binding.full_sync.stale_lock_released",
            params={"error": str(e)},
        )
    # 029: enter the robo-spec MCP session-manager context for the lifetime
    # of the app. Without this the streamable-HTTP handler raises
    # "Task group is not initialized" on the first request. Falls back to
    # a no-op when the MCP SDK is unavailable.
    # 038: 기존 RequirementChange 노드 초기화 (RESET_CHANGE_DATA=true 시에만)
    try:
        from api.features.requirement_changes.services.migration import reset_change_data
        reset_change_data()
    except Exception as e:  # noqa: BLE001
        SmartLogger.log(
            "WARN",
            f"requirement_changes migration skipped: {e}",
            category="requirement_changes.migration.skipped",
            params={"error": str(e)},
        )

    from api.features.robo_spec.router import mcp_lifespan
    async with mcp_lifespan():
        yield
    close_neo4j_driver(log=True)
    SmartLogger.log("INFO", "API stopped", category="api.lifespan")


app = FastAPI(
    title="Event Storming Navigator API",
    description="API for Ontology-based Event Storming Canvas",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS for Vue.js frontend + Figma plugin sandbox.
#
# allow_credentials MUST be False while allow_origins is "*", per CORS spec:
# browsers reject any actual response (not just preflight) that combines
# Access-Control-Allow-Origin: * with Access-Control-Allow-Credentials: true,
# which surfaces in the Figma plugin as "Failed to fetch" with no other
# diagnostic. The project has no cookie/session auth, so credentials are
# unused — flipping the flag is safe. Switch back to a concrete origin
# allow-list (and credentials=True) only when introducing real auth.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -----------------------------------------------------------------------------
# Request Correlation + Narrative Logging (LDVC)
# -----------------------------------------------------------------------------

@app.middleware("http")
async def _request_id_middleware(request: Request, call_next):
    """
    Assign a request_id to every inbound HTTP request and emit start/end logs.
    This gives us a deterministic "Bridge of Trust" for tracing execution.
    """
    rid = request.headers.get("x-request-id") or new_request_id()
    set_request_id(rid)
    timer = RequestTimer()

    SmartLogger.log(
        "INFO",
        "HTTP request received: starting route execution.",
        category="api.http.start",
        params=http_context(request),
    )

    try:
        response: Response = await call_next(request)
        SmartLogger.log(
            "INFO",
            "HTTP request completed.",
            category="api.http.end",
            params={
                **http_context(request),
                "result": {
                    "status_code": response.status_code,
                    "duration_ms": timer.ms(),
                },
            },
        )
        response.headers["X-Request-Id"] = rid
        return response
    except Exception as e:
        SmartLogger.log(
            "ERROR",
            "HTTP request failed: route raised an exception.",
            category="api.http.error",
            params={
                **http_context(request),
                "error": {"type": type(e).__name__, "message": str(e)},
                "duration_ms": timer.ms(),
            },
        )
        raise
    finally:
        # Avoid leaking request_id into unrelated async contexts.
        set_request_id(None)


# -----------------------------------------------------------------------------
# Identity propagation (spec 032)
# -----------------------------------------------------------------------------
# Reads `X-User-Name` / `X-User-Email` headers set by the Electron launcher
# hand-off and attaches an `Actor` to `request.state.actor`. Registered AFTER
# the request_id middleware so the actor log line carries the same
# correlation id as the rest of the request lifecycle.
#
# Trust model: local-loopback only. See
# `specs/032-desktop-startup-picker/contracts/identity-header-contract.md`.
from api.platform.identity import IdentityMiddleware  # noqa: E402

app.add_middleware(IdentityMiddleware)

# Feature 031: capture per-request output-language from Accept-Language header.
# Registered after the request_id middleware so the language tag is set
# BEFORE the request_id middleware's start/end logs fire — http_context()
# now includes the resolved language alongside request_id on every log line.
app.middleware("http")(language_middleware)

# Include ingestion router
from api.features.ingestion.router import router as ingestion_router
app.include_router(ingestion_router)

# Include hybrid ingestion router (Document + Code → BPM-first → Event Storming)
from api.features.ingestion.hybrid.router import router as hybrid_ingestion_router
app.include_router(hybrid_ingestion_router)

# Include Confluence integration router
from api.features.ingestion.confluence import router as confluence_router
app.include_router(confluence_router)

# Figma REST API integration + bidirectional sync
from api.features.ingestion.figma_api import router as figma_api_router
from api.features.ingestion.figma_sync import router as figma_sync_router
from api.features.ingestion.figma_plugin_ws import router as figma_plugin_ws_router
app.include_router(figma_api_router)
app.include_router(figma_sync_router)
app.include_router(figma_plugin_ws_router)

# Include change management router (OLD — LangChain-based, grandfathered)
from api.features.change_management.router import router as change_router
app.include_router(change_router)

# Include requirement changes router (038 — Skill-First, new)
from api.features.requirement_changes.router import router as req_changes_router
app.include_router(req_changes_router)

# Include chat-based model modification router
from api.features.model_modifier.router import router as chat_router
app.include_router(chat_router)

# Include PRD generator router
from api.features.prd_generation.router import router as prd_router
app.include_router(prd_router)

# Include user story add/apply router
from api.features.user_stories.authoring_router import router as user_story_router
app.include_router(user_story_router)


"""
Feature routers (business capabilities)
"""
from api.features.health.router import router as health_router
from api.features.contexts.router import router as contexts_router
from api.features.canvas_graph.router import router as canvas_graph_router
from api.features.user_stories.catalog_router import router as user_stories_catalog_router

app.include_router(health_router)
app.include_router(contexts_router)
app.include_router(canvas_graph_router)
app.include_router(user_stories_catalog_router)

# ReadModel / CQRS configuration APIs
from api.features.readmodel_cqrs.router import router as readmodel_cqrs_router

app.include_router(readmodel_cqrs_router)

# Claude Code terminal WebSocket
from api.features.claude_code.router import router as claude_code_router
app.include_router(claude_code_router)

# Figma document binding (feature 016)
from api.features.figma_binding.router import router as figma_binding_router
from api.features.figma_binding.plugin_messages import router as figma_binding_plugin_ack_router
app.include_router(figma_binding_router)
app.include_router(figma_binding_plugin_ack_router)

# AI Design proxy (open-pencil AI → backend LLM runtime)
from api.features.ai_design.router import router as ai_design_router
app.include_router(ai_design_router)

# DDD-for-SDD artifact generation (feature 022)
from api.features.ddd_spec.router import router as ddd_spec_router
app.include_router(ddd_spec_router)

# Requirements tab (feature 026)
from api.features.requirements.router import router as requirements_router
app.include_router(requirements_router)

# Aggregate Invariants (feature 027)
from api.features.invariants.router import router as invariants_router
app.include_router(invariants_router)

# Robo Spec — Claude Code skill MCP bridge (feature 029)
from api.features.robo_spec.router import router as robo_spec_router, mount_mcp as _mount_robo_spec_mcp
app.include_router(robo_spec_router)
_mount_robo_spec_mcp(app)


if __name__ == "__main__":
    import uvicorn

    HOST = os.getenv("API_HOST", "0.0.0.0")
    PORT = os.getenv("API_PORT", 8000)

    SmartLogger.log("INFO", "Starting API", category="api.main", params={"host": HOST, "port": PORT})
    uvicorn.run("api.main:app", host=HOST, port=PORT, reload=True)

