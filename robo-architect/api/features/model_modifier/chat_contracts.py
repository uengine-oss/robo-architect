from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


class ModifyRequest(BaseModel):
    """Request to modify selected nodes based on a prompt."""

    prompt: str
    selectedNodes: List[Dict[str, Any]]
    conversationHistory: List[Dict[str, Any]] = Field(default_factory=list)


class DraftChange(BaseModel):
    """
    A proposed change emitted by the LLM during /api/chat/modify (draft-only).

    - For update actions, `updates` is the field-patch map (source of truth).
    - For compatibility with the existing canvas sync, we may also include some
      flattened fields (e.g., description/template) in applied responses, but drafts
      are primarily driven by `updates`.
    """

    changeId: str
    action: Literal["rename", "update", "create", "delete", "connect"]
    targetId: str

    targetName: Optional[str] = None
    targetType: Optional[str] = None
    bcId: Optional[str] = None
    bcName: Optional[str] = None

    # ReAct-friendly explanation (shown in confirm UI)
    rationale: Optional[str] = None

    # Field patches for update/create
    updates: Dict[str, Any] = Field(default_factory=dict)

    # Optional: server-derived details for confirm UI
    before: Dict[str, Any] = Field(default_factory=dict)
    after: Dict[str, Any] = Field(default_factory=dict)

    # connect specifics
    sourceId: Optional[str] = None
    connectionType: Optional[str] = None


class ConfirmRequest(BaseModel):
    drafts: List[DraftChange] = Field(default_factory=list)
    approvedChangeIds: List[str] = Field(default_factory=list)


class ConfirmResponse(BaseModel):
    success: bool
    appliedChanges: List[Dict[str, Any]] = Field(default_factory=list)
    errors: List[str] = Field(default_factory=list)


