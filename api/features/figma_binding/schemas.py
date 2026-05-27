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
    # 024: bound Figma file's scanned design-system components.
    componentCount: int = 0


# ─── 024: Components (bound design-system catalog) ───────────────────────


class PluginComponentItem(BaseModel):
    """One COMPONENT/COMPONENT_SET node captured by the Figma plugin."""

    figmaNodeId: str
    name: str
    pageName: str = ""
    widthPx: int = 0
    heightPx: int = 0
    # Base64-encoded PNG bytes (no data-URI prefix). The plugin renders this
    # via ``node.exportAsync({format: 'PNG'})`` and ships it inline so the
    # backend never has to call Figma's REST `/v1/images` endpoint.
    pngBase64: str


class ScanComponentsRequest(BaseModel):
    """Plugin-driven scan payload — no REST API key required.

    The Figma plugin walks ``figma.root.findAll(n => n.type === 'COMPONENT'
    || n.type === 'COMPONENT_SET')`` and posts each node with its rendered
    PNG. Replaces the legacy REST path that needed an X-Figma-Token.
    """

    components: list[PluginComponentItem] = Field(default_factory=list)


class ScanComponentsResponse(BaseModel):
    scanned: int = 0
    added: int = 0
    updated: int = 0
    removed: int = 0
    vlmDescribed: int = 0
    vlmFailures: int = 0
    componentCount: int = 0
    durationMs: int = 0


class FigmaComponentRow(BaseModel):
    id: str | None = None
    figmaNodeId: str
    name: str
    pageName: str
    widthPx: int = 0
    heightPx: int = 0
    vlmDescription: str = ""
    figmaKey: str | None = None
    scannedAt: str | None = None


class FigmaComponentsListResponse(BaseModel):
    components: list[FigmaComponentRow] = Field(default_factory=list)
    componentCount: int = 0


class ConnectRequest(BaseModel):
    """Plugin-pushed binding request. The plugin reads ``figma.fileKey`` and
    ``figma.root.name`` and ships them to the backend — no REST API key
    needed because the plugin's mere presence in Figma proves the user has
    permission to the file."""

    figmaFileKey: str
    figmaFileName: str


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


# ─── Full-sync (020) ──────────────────────────────────────────────────────


class FullSyncStartResponse(BaseModel):
    runId: str
    kind: Literal["retroactive-sync", "manual-retry"]
    startedAt: str
    streamUrl: str


class LockContendedResponse(BaseModel):
    error: Literal["lock_contended"] = "lock_contended"
    messageKr: str = "다른 사용자가 동기화 중입니다"
    currentRunId: str
    currentRunHolder: str | None = None
    streamUrl: str


# ─── Sync runs / failures (020) ───────────────────────────────────────────


class SyncRunSummaryCounts(BaseModel):
    storyboardsTotal: int = 0
    pagesCreated: int = 0
    pagesAlreadyOk: int = 0
    uisTotal: int = 0
    framesPushed: int = 0
    generated: int = 0
    overwrites: int = 0
    failures: int = 0


class SyncRunSummary(BaseModel):
    runId: str
    kind: Literal["retroactive-sync", "manual-retry"]
    startedAt: str
    finishedAt: str | None = None
    status: Literal[
        "running",
        "succeeded",
        "partially-succeeded",
        "cancelled",
        "aborted-binding-unreachable",
    ]
    summary: SyncRunSummaryCounts | None = None
    actor: str
    bindingFileKey: str
    previousBinding: bool = False


class SyncRunsListResponse(BaseModel):
    currentBindingFileKey: str | None
    runs: list[SyncRunSummary]


Retryability = Literal["retryable", "non-retryable", "in-flight"]


class FailureRow(BaseModel):
    uiId: str
    displayName: str
    lastErrorKr: str | None = None
    lastAttemptAt: str | None = None
    retryability: Retryability
    nonRetryableReason: str | None = None
    bindingFileKey: str | None = None


class FailuresListResponse(BaseModel):
    currentBindingFileKey: str | None
    retryable: list[FailureRow]
    nonRetryable: list[FailureRow]
    inFlight: list[FailureRow]
