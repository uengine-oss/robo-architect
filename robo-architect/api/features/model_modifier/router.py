"""
Chat-based Model Modification API (feature router)

- Streaming chat-based modification of domain model objects (SSE)
- ReAct style: THOUGHT/ACTION/OBSERVATION loop with inline JSON action blocks
"""

from __future__ import annotations

from fastapi import APIRouter

from .routes.chat_modify import router as chat_modify_router
from .routes.node_details import router as node_details_router

router = APIRouter(prefix="/api/chat", tags=["chat"])

router.include_router(chat_modify_router)
router.include_router(node_details_router)


