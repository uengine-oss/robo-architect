"""Aggregate Invariants Contracts (DTOs) — 027 aggregate-invariants.

Pydantic request/response models for the `/api/invariants` API.
See specs/027-aggregate-invariants/data-model.md §2 and contracts/rest-api.md.
"""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field

InvariantSource = Literal["manual", "ingested", "migrated"]


# ── Summary / tree rows ──────────────────────────────────────────────────


class InvariantSummaryDTO(BaseModel):
    id: str
    key: str
    name: str
    declaration: str
    source: InvariantSource = "manual"
    seq: int = 0
    # True when the invariant has at least one detailed condition — either a
    # VERIFIED_BY reference or its own GWT bundle.
    isSpecified: bool = False
    referencedCommandCount: int = 0
    type: Literal["Invariant"] = "Invariant"


# ── Detail / property editor ─────────────────────────────────────────────


class ReferencedConditionDTO(BaseModel):
    """One shared, Command-backed detailed condition."""

    commandId: str
    commandName: str
    # Whether that Command currently has a GWT bundle to edit.
    hasGwt: bool = False


class InvariantDetailDTO(BaseModel):
    id: str
    key: str
    name: str
    declaration: str
    description: Optional[str] = None
    source: InvariantSource = "manual"
    seq: int = 0
    aggregateId: str
    aggregateName: str = ""
    referencedConditions: list[ReferencedConditionDTO] = Field(default_factory=list)
    # Equals the invariant id when an invariant-owned GWT bundle exists, else None.
    # Callers edit it via POST /api/graph/gwt/upsert with parentType="Invariant".
    ownGwtParentId: Optional[str] = None
    isSpecified: bool = False


class ReferenceCandidateDTO(BaseModel):
    """A Command of the same Aggregate offered as a reference candidate."""

    commandId: str
    commandName: str
    hasGwt: bool = False
    alreadyReferenced: bool = False


# ── List response ────────────────────────────────────────────────────────


class InvariantListResponse(BaseModel):
    aggregateId: str
    invariants: list[InvariantSummaryDTO] = Field(default_factory=list)


class ReferenceCandidatesResponse(BaseModel):
    candidates: list[ReferenceCandidateDTO] = Field(default_factory=list)


# ── CRUD request bodies ──────────────────────────────────────────────────


class CreateInvariantRequest(BaseModel):
    declaration: str
    name: Optional[str] = None
    description: Optional[str] = None


class UpdateInvariantRequest(BaseModel):
    declaration: Optional[str] = None
    name: Optional[str] = None
    description: Optional[str] = None


class AddReferenceRequest(BaseModel):
    commandId: str


# ── Exception domain objects (catalog on the Aggregate) ──────────────────
# An Exception is an Aggregate-level domain object, sibling to enumerations
# and value objects. A GWT Then (Command or Invariant) may declare an
# exception outcome by referencing one of these by name.


class ExceptionFieldDTO(BaseModel):
    name: str
    type: str = "String"
    description: Optional[str] = None


class ExceptionDTO(BaseModel):
    name: str
    message: str = ""
    fields: list[ExceptionFieldDTO] = Field(default_factory=list)


class ExceptionCatalogResponse(BaseModel):
    aggregateId: str
    exceptions: list[ExceptionDTO] = Field(default_factory=list)


class PutExceptionsRequest(BaseModel):
    exceptions: list[ExceptionDTO] = Field(default_factory=list)
