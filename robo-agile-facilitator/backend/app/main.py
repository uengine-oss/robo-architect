"""AESF - AI Event Storming Facilitator

Main FastAPI application entry point.
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import socketio

from .config import get_settings
from .db.neo4j import db
from .db.redis import redis_db
from .api.sessions import router as sessions_router
from .api.realtime import router as realtime_router
from .api.export import router as export_router
from .websocket.canvas import sio


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler for startup/shutdown."""
    # Startup
    print("🚀 Starting AESF Backend...")
    
    try:
        await db.connect()
        print("✅ Neo4j connected")
    except Exception as e:
        print(f"⚠️ Neo4j connection failed: {e}")
    
    try:
        await redis_db.connect()
        print("✅ Redis connected")
    except Exception as e:
        print(f"⚠️ Redis connection failed: {e}")
    
    print("🎯 AESF Backend ready!")
    
    yield
    
    # Shutdown
    print("👋 Shutting down AESF Backend...")
    await db.disconnect()
    await redis_db.disconnect()


# Create FastAPI app
app = FastAPI(
    title="AESF - AI Event Storming Facilitator",
    description="WebRTC-based video conferencing with AI-powered Event Storming facilitation",
    version="0.1.0",
    lifespan=lifespan
)

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
        session = await db.get_session("health-check")
        health_status["neo4j"] = "healthy"
    except Exception:
        health_status["neo4j"] = "unhealthy"
    
    try:
        # Check Redis
        await redis_db._client.ping()
        health_status["redis"] = "healthy"
    except Exception:
        health_status["redis"] = "unhealthy"
    
    return health_status


# Wrap FastAPI app with Socket.IO
socket_app = socketio.ASGIApp(sio, other_asgi_app=app)

