"""Pydantic schemas for the robo-spec HTTP routes and MCP tool I/O.

Authoritative shapes live in
``specs/029-robo-spec-skills/contracts/{http-api,mcp-tools}.md`` —
this module is the executable mirror. Subsequent /speckit-implement
passes (T011, T021, T037, T038, T042, T048, T049) consume these
classes from `service.py`, `mcp_server.py`, and `router.py`.

Field naming follows the contracts verbatim (camelCase on the wire) so
that MCP tool clients and the frontend can rely on a single schema.
Internal Python code can convert via ``model_dump(by_alias=True)``.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Shared primitives
# ---------------------------------------------------------------------------


class Classification(str, Enum):
    """BC architectural classification — drives /robo-plan's template choice.

    See research R4 and FR-005. Absence (``None`` on the BC node) is
    meaningful: it signals to /robo-plan that the developer should be
    asked, and the answer is then persisted back via ``T3 set_bc_classification``.
    """

    CORE = "core"
    SUPPORTING = "supporting"


class ElementKind(str, Enum):
    """The labels permitted on `[:IMPLEMENTED_IN]` source-mapping links."""

    AGGREGATE = "Aggregate"
    COMMAND = "Command"
    EVENT = "Event"
    READ_MODEL = "ReadModel"


class FileRole(str, Enum):
    """Discriminator on :ImplementationFile.role — data-model §1.2."""

    PRIMARY = "primary"
    INTERFACE_ADAPTER = "interface-adapter"
    INFRASTRUCTURE = "infrastructure"
    TEST = "test"
    OTHER = "other"


class ImplementationFile(BaseModel):
    """One file linked to a design element. Mirrors data-model §1.2."""

    path: str
    role: FileRole
    last_seen_at: Optional[datetime] = Field(default=None, alias="lastSeenAt")

    model_config = ConfigDict(populate_by_name=True)


# ---------------------------------------------------------------------------
# E2 / E3 — BC classification HTTP routes (contracts/http-api.md)
# ---------------------------------------------------------------------------


class ClassificationResponse(BaseModel):
    """Response of ``GET /api/contexts/{bc_id}/classification`` (E2)."""

    bc_id: str = Field(alias="bcId")
    classification: Optional[Classification] = None

    model_config = ConfigDict(populate_by_name=True)


class ClassificationPatchRequest(BaseModel):
    """Body of ``PATCH /api/contexts/{bc_id}/classification`` (E3)."""

    classification: Classification


# ---------------------------------------------------------------------------
# E4 — open-file (contracts/http-api.md)
# ---------------------------------------------------------------------------


class OpenFileRequest(BaseModel):
    element_id: str = Field(alias="elementId")
    preferred_role: Optional[FileRole] = Field(default=None, alias="preferredRole")

    model_config = ConfigDict(populate_by_name=True)


class OpenFileResponse(BaseModel):
    status: Literal["opened", "not-implemented", "ambiguous", "offline"]
    file: Optional[ImplementationFile] = None
    candidates: Optional[list[ImplementationFile]] = None
    scaffold_task_hint: Optional[str] = Field(default=None, alias="scaffoldTaskHint")
    correlation_id: Optional[str] = Field(default=None, alias="correlationId")

    model_config = ConfigDict(populate_by_name=True)


# ---------------------------------------------------------------------------
# E6 — implementation-map (contracts/http-api.md)
# ---------------------------------------------------------------------------


class ImplementationMapElement(BaseModel):
    kind: ElementKind
    name: str
    files: list[ImplementationFile] = Field(default_factory=list)


class ImplementationMapResponse(BaseModel):
    project_id: str = Field(alias="projectId")
    bc_id: str = Field(alias="bcId")
    elements: dict[str, ImplementationMapElement]

    model_config = ConfigDict(populate_by_name=True)


# ---------------------------------------------------------------------------
# MCP T6b — register_implementation_files
# ---------------------------------------------------------------------------


class RegisterFile(BaseModel):
    path: str
    role: FileRole


class RegisterImplementationFilesInput(BaseModel):
    project_id: str = Field(alias="projectId")
    element_id: str = Field(alias="elementId")
    files: list[RegisterFile]
    mode: Literal["replace", "merge"] = "merge"

    model_config = ConfigDict(populate_by_name=True)


class RegisterImplementationFilesResult(BaseModel):
    element_id: str = Field(alias="elementId")
    files_now: int = Field(alias="filesNow")

    model_config = ConfigDict(populate_by_name=True)


# ---------------------------------------------------------------------------
# MCP T4 — compute_drift
# ---------------------------------------------------------------------------


class DriftReference(BaseModel):
    """One entry in ``compute_drift.references[]`` — what the local tasks.md
    or plan.md currently *sees* for a given design element id.
    """

    id: str
    kind: ElementKind
    name_seen: str = Field(alias="nameSeen")

    model_config = ConfigDict(populate_by_name=True)


class DriftRenamed(BaseModel):
    id: str
    old_name: str = Field(alias="oldName")
    new_name: str = Field(alias="newName")

    model_config = ConfigDict(populate_by_name=True)


class DriftDeleted(BaseModel):
    id: str
    kind: ElementKind
    name_seen: str = Field(alias="nameSeen")

    model_config = ConfigDict(populate_by_name=True)


class DriftAdded(BaseModel):
    id: str
    kind: ElementKind
    name: str


class DriftReclassified(BaseModel):
    from_: Classification = Field(alias="from")
    to: Classification

    model_config = ConfigDict(populate_by_name=True)


class DriftReport(BaseModel):
    renamed: list[DriftRenamed] = Field(default_factory=list)
    deleted: list[DriftDeleted] = Field(default_factory=list)
    added: list[DriftAdded] = Field(default_factory=list)
    reclassified: list[DriftReclassified] = Field(default_factory=list)


class ComputeDriftInput(BaseModel):
    project_id: str = Field(alias="projectId")
    bc_id: str = Field(alias="bcId")
    references: list[DriftReference] = Field(default_factory=list)
    classification_seen: Optional[Classification] = Field(
        default=None, alias="classificationSeen"
    )

    model_config = ConfigDict(populate_by_name=True)


class ComputeDriftResult(BaseModel):
    status: Literal["in-sync", "drift"]
    drift: DriftReport
    blocking: list[str] = Field(
        default_factory=lambda: ["renamed", "deleted", "reclassified"]
    )
    correlation_id: Optional[str] = Field(default=None, alias="correlationId")

    model_config = ConfigDict(populate_by_name=True)


# ---------------------------------------------------------------------------
# MCP T2 — get_bc_design (response augments existing /api/contexts/{id}/tree)
# ---------------------------------------------------------------------------


class ElementWithFiles(BaseModel):
    """Common shape used inside get_bc_design.aggregates[].* and similar
    nested locations. Carries the version + linked files per data-model §1.3.
    """

    id: str
    name: str
    kind: ElementKind
    version: int = 0
    implementation_files: list[ImplementationFile] = Field(
        default_factory=list, alias="implementationFiles"
    )

    model_config = ConfigDict(populate_by_name=True)


class GetBcDesignResult(BaseModel):
    """Thin Pydantic projection of the augmented tree response. The full
    tree shape is intentionally permissive (``extra="allow"``) so the
    contracts in contracts/mcp-tools.md remain a strict subset rather
    than an exhaustive transcription — the existing
    /api/contexts/{id}/tree response carries many fields that this
    feature does not need to redefine.
    """

    id: str
    name: str
    classification: Optional[Classification] = None
    incomplete: bool = False
    aggregates: list[dict[str, Any]] = Field(default_factory=list)
    correlation_id: Optional[str] = Field(default=None, alias="correlationId")

    model_config = ConfigDict(populate_by_name=True, extra="allow")


# ---------------------------------------------------------------------------
# MCP T5 — report_progress
# ---------------------------------------------------------------------------


class ProgressStatus(str, Enum):
    TODO = "todo"
    IN_PROGRESS = "in-progress"
    DONE = "done"
    BLOCKED = "blocked"
    ORPHANED = "orphaned"


class ProgressItem(BaseModel):
    element_id: str = Field(alias="elementId")
    status: ProgressStatus

    model_config = ConfigDict(populate_by_name=True)


class ReportProgressInput(BaseModel):
    project_id: str = Field(alias="projectId")
    feature_directory: str = Field(alias="featureDirectory")
    items: list[ProgressItem]

    model_config = ConfigDict(populate_by_name=True)


# ---------------------------------------------------------------------------
# MCP T6 / T6a — propose_sync / apply_proposal (skeleton; T046–T049 fill bodies)
# ---------------------------------------------------------------------------


class AstField(BaseModel):
    name: str
    type: str


class AstExtract(BaseModel):
    element_id: str = Field(alias="elementId")
    kind: ElementKind
    version: int = 0
    extracted_at: Optional[datetime] = Field(default=None, alias="extractedAt")
    from_files: list[str] = Field(default_factory=list, alias="fromFiles")
    fields: list[AstField] = Field(default_factory=list)

    model_config = ConfigDict(populate_by_name=True)


class ProposeSyncInput(BaseModel):
    project_id: str = Field(alias="projectId")
    bc_id: str = Field(alias="bcId")
    extracts: list[AstExtract]

    model_config = ConfigDict(populate_by_name=True)


class DiffEntry(BaseModel):
    element_id: str = Field(alias="elementId")
    added: list[AstField] = Field(default_factory=list)
    modified: list[AstField] = Field(default_factory=list)
    removed: list[AstField] = Field(default_factory=list)

    model_config = ConfigDict(populate_by_name=True)


class RenameCandidate(BaseModel):
    element_id: str = Field(alias="elementId")
    from_: AstField = Field(alias="from")
    to: AstField
    confidence: float = 0.0
    rationale: str = ""

    model_config = ConfigDict(populate_by_name=True)


class ProposeSyncResult(BaseModel):
    proposal_id: str = Field(alias="proposalId")
    diff: dict[str, list[DiffEntry]]
    rename_candidates: list[RenameCandidate] = Field(
        default_factory=list, alias="renameCandidates"
    )
    requires_confirmation: list[str] = Field(
        default_factory=list, alias="requiresConfirmation"
    )
    correlation_id: Optional[str] = Field(default=None, alias="correlationId")

    model_config = ConfigDict(populate_by_name=True)


class ApplyProposalInput(BaseModel):
    project_id: str = Field(alias="projectId")
    proposal_id: str = Field(alias="proposalId")
    confirmed: list[str] = Field(default_factory=list)

    model_config = ConfigDict(populate_by_name=True)


class AppliedEntry(BaseModel):
    element_id: str = Field(alias="elementId")
    new_version: int = Field(alias="newVersion")

    model_config = ConfigDict(populate_by_name=True)


class ApplyProposalResult(BaseModel):
    status: Literal["applied", "conflict"]
    applied: list[AppliedEntry] = Field(default_factory=list)
    rejected: list[str] = Field(default_factory=list)
    correlation_id: Optional[str] = Field(default=None, alias="correlationId")

    model_config = ConfigDict(populate_by_name=True)


# ---------------------------------------------------------------------------
# E1 — setup-project response (extension)
# ---------------------------------------------------------------------------


class RoboSpecInstallSummary(BaseModel):
    """Fragment merged into the existing setup-project response per E1."""

    robo_spec_installed: bool = Field(alias="roboSpecInstalled")
    robo_spec_checksum: str = Field(alias="roboSpecChecksum")

    model_config = ConfigDict(populate_by_name=True)
