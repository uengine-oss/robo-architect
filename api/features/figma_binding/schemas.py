"""Pydantic request/response models for /api/figma-binding/* endpoints.

Wire format mirrors specs/016-figma-document-binding/contracts/rest-api.md.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


# ─── Binding lifecycle ────────────────────────────────────────────────────


class FigmaBindingResponse(BaseModel):
    id: str
    figmaFileKey: str
    figmaFileName: str
    connectedBy: str
    connectedAt: str
    lastSyncAt: str | None = None
    status: Literal["active", "unreachable", "disconnected"]
    storyboardCounts: dict[str, int] = Field(
        default_factory=lambda: {"active": 0, "archived": 0}
    )


class ConnectRequest(BaseModel):
    figmaFileKey: str
    apiToken: str


# ─── Sync storyboards ─────────────────────────────────────────────────────


class StoryboardCreatedItem(BaseModel):
    commandId: str
    figmaPageId: str
    figmaPageName: str


class StoryboardReusedItem(BaseModel):
    commandId: str
    figmaPageId: str
    figmaPageName: str


class StoryboardRenamedItem(BaseModel):
    commandId: str
    # current cached name, before this sync
    fromName: str = Field(alias="from")
    # current Command.displayName, after this sync
    toName: str = Field(alias="to")

    class Config:
        populate_by_name = True


class StoryboardArchivedItem(BaseModel):
    commandId: str
    reason: str  # "entry_command_removed" | "no_longer_entry"


class StoryboardUnreachableItem(BaseModel):
    commandId: str
    reason: str


class SyncStoryboardsResponse(BaseModel):
    created: list[StoryboardCreatedItem] = Field(default_factory=list)
    reused: list[StoryboardReusedItem] = Field(default_factory=list)
    renamed: list[StoryboardRenamedItem] = Field(default_factory=list)
    archived: list[StoryboardArchivedItem] = Field(default_factory=list)
    unreachable: list[StoryboardUnreachableItem] = Field(default_factory=list)


# ─── Storyboard listing ───────────────────────────────────────────────────


class StoryboardMappingInfo(BaseModel):
    figmaPageId: str
    figmaPageName: str
    status: Literal["active", "archived"]


class StoryboardListItem(BaseModel):
    commandId: str
    displayName: str
    stepCount: int | None = None
    mapping: StoryboardMappingInfo | None = None


# ─── Generate-frame session ───────────────────────────────────────────────


GenerationMode = Literal["component", "openpencil-ai", "html-to-design"]
ConflictPolicy = Literal["ask", "overwrite", "import-existing"]


class GenerateFrameRequest(BaseModel):
    mode: GenerationMode
    prompt: str | None = None
    onConflict: ConflictPolicy = "ask"


class ResolvedStoryboard(BaseModel):
    commandId: str
    figmaPageId: str
    figmaPageName: str


class GenerateFrameAccepted(BaseModel):
    sessionId: str
    streamUrl: str
    resolvedStoryboard: ResolvedStoryboard


# ─── History ──────────────────────────────────────────────────────────────


class BindingHistoryEntry(BaseModel):
    id: str
    eventType: str
    figmaFileKey: str | None = None
    actor: str
    at: str
    payload: dict[str, Any] | None = None


class BindingHistoryResponse(BaseModel):
    items: list[BindingHistoryEntry]
