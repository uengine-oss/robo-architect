"""Pydantic request / response / SSE-event shapes for the ``/api/ddd-spec`` endpoints.

Mirrors ``specs/022-spec-generation-from-event-storming/data-model.md`` §2–§3.
"""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field


ArtifactKind = Literal[
    "domain_terms",
    "bc_canvas",
    "aggregate_spec",
    "acl_spec",
    "requirements",
    "context_map",
    # Scene-graph JSON sidecars are no longer emitted (2026-05-12
    # amendment) — the SVG is the only visual asset; structure cues
    # come from the element tree inside requirements.md.
    "svg",
    # Frontend perspective (US5 — 2026-05-12 amendment).
    "frontend_framework",
    "frontend_menu",
    "frontend_ui_flow",
]

SkipKind = Literal["bounded_context", "aggregate", "context_map", "artifact_file"]

AliasesToAvoidMode = Literal["omit", "suggest"]


class GenerateBoundedContextRequest(BaseModel):
    bounded_context_id: str
    overwrite: bool = False
    aliases_to_avoid: AliasesToAvoidMode = "suggest"
    smooth_ears: bool = True
    render_svg: bool = True


class GenerateAggregateRequest(BaseModel):
    aggregate_id: str
    overwrite: bool = False
    smooth_ears: bool = True


class GenerateContextMapRequest(BaseModel):
    overwrite: bool = False
    infer_patterns_with_llm: bool = False


class GenerateAllRequest(BaseModel):
    overwrite: bool = False
    aliases_to_avoid: AliasesToAvoidMode = "suggest"
    smooth_ears: bool = True
    render_svg: bool = True
    infer_patterns_with_llm: bool = False


class ArtifactFileInfo(BaseModel):
    kind: ArtifactKind
    path: str
    bounded_context_id: Optional[str] = None
    aggregate_id: Optional[str] = None


class SkippedItem(BaseModel):
    kind: SkipKind
    id: Optional[str] = None
    existing_path: str
    reason: Literal[
        "already_exists",
        "empty_bounded_context",
        # US7 — per-BC agent files are deprecated; reported on emit so the
        # user knows to delete their local copy.
        "deprecated_per_bc_agent",
    ]
    message: Optional[str] = None


class GenerationWarning(BaseModel):
    code: str
    message: str
    target: dict[str, str] = Field(default_factory=dict)


class GenerationResult(BaseModel):
    created: list[ArtifactFileInfo] = Field(default_factory=list)
    skipped: list[SkippedItem] = Field(default_factory=list)
    warnings: list[GenerationWarning] = Field(default_factory=list)
    correlation_id: str


# --- SSE event payloads (POST /generate-all) -------------------------------


class SsePhaseEvent(BaseModel):
    phase: Literal["loading_model", "context_map", "bounded_contexts"]
    message: str


class SseBcStartedEvent(BaseModel):
    bounded_context_id: str
    bounded_context_name: str
    index: int
    total: int


class SseWireframeRenderedEvent(BaseModel):
    bounded_context_id: str
    user_story_id: str
    ui_id: str
    svg_path: Optional[str] = None


class SseBcCompletedEvent(BaseModel):
    bounded_context_id: str
    files: list[ArtifactFileInfo]


class SseBcFailedEvent(BaseModel):
    bounded_context_id: str
    error_code: str
    message: str


class SseErrorEvent(BaseModel):
    error_code: str
    message: str
    correlation_id: str
