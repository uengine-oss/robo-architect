from __future__ import annotations

from typing import Any, Dict, List

from pydantic import BaseModel, Field


class ModifyRequest(BaseModel):
    """Request to modify selected nodes based on a prompt."""

    prompt: str
    selectedNodes: List[Dict[str, Any]]
    conversationHistory: List[Dict[str, Any]] = Field(default_factory=list)


