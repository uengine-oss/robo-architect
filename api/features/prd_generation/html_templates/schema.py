"""Pydantic schema for HTML policy-document template manifests.

A template is a directory under `templates/<id>/` containing:
  - manifest.yaml (`TemplateManifest`)
  - master_template (Jinja, typically `document.html.j2`)
  - partials/*.j2 referenced by the master template
  - prompts/*.j2 for LLM-driven sections

Sections (`SectionSpec`) declare how each piece of the document is filled:
  - `derived` — pure Jinja substitution from the deterministic graph context.
  - `llm`     — body content comes entirely from an LLM call.
  - `hybrid`  — derived data is the base; the LLM only enriches a few fields
                (e.g. natural-language trigger text in a state-transition row).
"""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field


SectionKind = Literal["derived", "llm", "hybrid"]


class SectionSpec(BaseModel):
    """One section declaration inside a `TemplateManifest`."""

    id: str
    kind: SectionKind = "derived"
    prompt: Optional[str] = Field(
        default=None,
        description="Relative path (under template dir) to the prompt Jinja file for llm/hybrid sections.",
    )
    inputs: list[str] = Field(
        default_factory=list,
        description="Names of base-context keys the prompt depends on (for cache keying / debugging).",
    )


class TemplateMetadata(BaseModel):
    """Per-template metadata used by the master template."""

    doc_id_prefix: str = "POL"
    author_default: str = "(미지정)"


class TemplateManifest(BaseModel):
    """Loaded representation of `manifest.yaml`."""

    id: str
    name: str
    version: str = "v1.0"
    description: str = ""
    master_template: str = "document.html.j2"
    metadata: TemplateMetadata = Field(default_factory=TemplateMetadata)
    sections: list[SectionSpec] = Field(default_factory=list)

    def section(self, section_id: str) -> Optional[SectionSpec]:
        for s in self.sections:
            if s.id == section_id:
                return s
        return None


# ----- Derived data shapes consumed by the master template -----------------


class ActorInfo(BaseModel):
    id: str
    name: str
    kind: Literal["primary", "secondary", "external"] = "primary"
    description: str = ""


class UseCaseRow(BaseModel):
    id: str                           # e.g. UC-MBR-001
    name: str
    actor_ids: list[str] = Field(default_factory=list)
    description: str = ""
    preconditions: list[str] = Field(default_factory=list)
    main_flow: list[str] = Field(default_factory=list)
    bounded_context_slug: str = ""


class StateTransitionRow(BaseModel):
    from_state: str
    event: str
    to_state: str
    trigger: str = ""                 # natural-language trigger (LLM-enriched in hybrid mode)


class FunctionRow(BaseModel):
    id: str                           # e.g. FN-MBR-JOIN-001
    name: str
    description: str = ""
    process_id: str = ""
    bounded_context_slug: str = ""
    aggregate_slug: str = ""
    preconditions: list[str] = Field(default_factory=list)
    postconditions: list[str] = Field(default_factory=list)
    events_emitted: list[str] = Field(default_factory=list)


class ProcessStep(BaseModel):
    seq: int
    name: str
    function_id: Optional[str] = None
    wireframe_slug: Optional[str] = None
    description: str = ""


class ProcessRow(BaseModel):
    id: str                           # e.g. PR-MBR-CS-001
    name: str
    bounded_context_slug: str = ""
    actor_id: Optional[str] = None
    summary: str = ""
    steps: list[ProcessStep] = Field(default_factory=list)


class PolicyRow(BaseModel):
    id: str                           # e.g. POL-MBR-001
    name: str
    description: str = ""
    effect: str = ""
    bounded_context_slug: str = ""
    related_event: Optional[str] = None
    prose: str = ""                   # LLM-enriched detailed prose (hybrid mode)


class GlossaryRow(BaseModel):
    term: str
    definition: str = ""
    bounded_context_slug: str = ""


class MetaBlock(BaseModel):
    doc_id: str = "POL-PRJ"
    doc_kind: str = "Full 버전"
    doc_status: str = "확정본"
    version: str = "Full v1.0"
    author: str = "(미지정)"
    generated_at: str = ""            # ISO date stamp
    git_sha: str = ""                 # short SHA of HEAD (if available)
    project_name: str = ""
    title: str = ""
    eyebrow: str = ""
