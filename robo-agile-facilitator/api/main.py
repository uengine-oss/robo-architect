"""AESF - AI Event Storming Facilitator

Main FastAPI application entry point.
"""
from dotenv import load_dotenv
load_dotenv()

from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
import socketio

from .config import get_settings
from .features.event_storming.graph_store import graph
from .features.workshop_realtime.presence_store import presence
from .features.event_storming.http_api import router as sessions_router
from .features.ai_facilitator.realtime_api import router as realtime_router
from .features.event_storming.export_api import router as export_router
from .features.workshop_realtime.server import sio
from .platform.observability.request_logging import (
    RequestTimer,
    http_context,
    new_request_id,
    set_request_id,
    sha256_bytes,
    summarize_for_log,
)
from .platform.observability.smart_logger import SmartLogger


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler for startup/shutdown."""
    # Startup
    SmartLogger.log("INFO", "app.startup.begin", category="app", params={})
    
    try:
        t = RequestTimer()
        await graph.connect()
        SmartLogger.log("INFO", "neo4j.connect.ok", category="app", params={"duration_ms": t.ms()})
    except Exception as e:
        SmartLogger.log("ERROR", "neo4j.connect.error", category="app", params={"error": repr(e)})
    
    try:
        t = RequestTimer()
        await presence.connect()
        SmartLogger.log("INFO", "redis.connect.ok", category="app", params={"duration_ms": t.ms()})
    except Exception as e:
        SmartLogger.log("ERROR", "redis.connect.error", category="app", params={"error": repr(e)})
    
    SmartLogger.log("INFO", "app.startup.ready", category="app", params={})
    
    yield
    
    # Shutdown
    SmartLogger.log("INFO", "app.shutdown.begin", category="app", params={})
    try:
        t = RequestTimer()
        await graph.disconnect()
        SmartLogger.log("INFO", "neo4j.disconnect.ok", category="app", params={"duration_ms": t.ms()})
    except Exception as e:
        SmartLogger.log("ERROR", "neo4j.disconnect.error", category="app", params={"error": repr(e)})

    try:
        t = RequestTimer()
        await presence.disconnect()
        SmartLogger.log("INFO", "redis.disconnect.ok", category="app", params={"duration_ms": t.ms()})
    except Exception as e:
        SmartLogger.log("ERROR", "redis.disconnect.error", category="app", params={"error": repr(e)})

    SmartLogger.log("INFO", "app.shutdown.done", category="app", params={})


# Create FastAPI app
app = FastAPI(
    title="AESF - AI Event Storming Facilitator",
    description="WebRTC-based video conferencing with AI-powered Event Storming facilitation",
    version="0.1.0",
    lifespan=lifespan
)

# Request lifecycle logging (request_id + duration + summarized body)
@app.middleware("http")
async def _request_logging_middleware(request: Request, call_next):
    t = RequestTimer()
    rid = (
        (request.headers.get("x-request-id") or "").strip()
        or (request.headers.get("x-correlation-id") or "").strip()
        or new_request_id()
    )
    set_request_id(rid)

    body_summary = None
    try:
        body_bytes = await request.body()
        if body_bytes:
            ct = (request.headers.get("content-type") or "").lower()
            if "application/json" in ct:
                try:
                    body_json = await request.json()
                    body_summary = summarize_for_log(body_json)
                except Exception:
                    body_summary = {
                        "__type__": "bytes",
                        "__len__": len(body_bytes),
                        "__sha256__": sha256_bytes(body_bytes),
                    }
            else:
                body_summary = {
                    "__type__": "bytes",
                    "__len__": len(body_bytes),
                    "__sha256__": sha256_bytes(body_bytes),
                }
    except Exception as e:
        body_summary = {"__error__": repr(e)}

    SmartLogger.log(
        "INFO",
        "http.request.start",
        category="http",
        params={
            **http_context(request),
            "body": body_summary,
        },
    )

    try:
        response = await call_next(request)
        SmartLogger.log(
            "INFO",
            "http.request.end",
            category="http",
            params={
                **http_context(request),
                "status_code": getattr(response, "status_code", None),
                "duration_ms": t.ms(),
                "response_content_length": (getattr(getattr(response, "headers", None), "get", lambda *_: None))(
                    "content-length"
                ),
            },
        )
        return response
    except Exception as e:
        SmartLogger.log(
            "ERROR",
            "http.request.exception",
            category="http",
            params={
                **http_context(request),
                "duration_ms": t.ms(),
                "error": repr(e),
            },
        )
        raise
    finally:
        set_request_id(None)

# CORS configuration
settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register API routers
app.include_router(sessions_router)
app.include_router(realtime_router)
app.include_router(export_router)


@app.get("/")
async def root():
    """Health check endpoint."""
    return {
        "name": "AESF Backend",
        "version": "0.1.0",
        "status": "running"
    }


@app.get("/health")
async def health():
    """Detailed health check."""
    health_status = {
        "api": "healthy",
        "neo4j": "unknown",
        "redis": "unknown"
    }
    
    try:
        # Check Neo4j
        _ = await graph.get_session("health-check")
        health_status["neo4j"] = "healthy"
    except Exception:
        health_status["neo4j"] = "unhealthy"
    
    try:
        # Check Redis
        await presence._client.ping()
        health_status["redis"] = "healthy"
    except Exception:
        health_status["redis"] = "unhealthy"
    
    return health_status


# Wrap FastAPI app with Socket.IO
socket_app = socketio.ASGIApp(sio, other_asgi_app=app)

