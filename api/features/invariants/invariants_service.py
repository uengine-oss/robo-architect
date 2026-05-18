"""Orchestration + DTO assembly for Aggregate Invariants (027).

Sits between the HTTP router and `neo4j_ops`. Triggers the lazy legacy-text
migration on first list, and builds the Pydantic DTOs.
"""

from __future__ import annotations

from typing import Any

from . import neo4j_ops as ops
from .invariants_contracts import (
    ExceptionCatalogResponse,
    ExceptionDTO,
    ExceptionFieldDTO,
    InvariantDetailDTO,
    InvariantListResponse,
    InvariantSummaryDTO,
    ReferenceCandidateDTO,
    ReferenceCandidatesResponse,
    ReferencedConditionDTO,
)


def _summary_dto(row: dict[str, Any]) -> InvariantSummaryDTO:
    return InvariantSummaryDTO(
        id=row["id"],
        key=row["key"],
        name=row.get("name") or row.get("declaration") or "",
        declaration=row.get("declaration") or "",
        source=row.get("source") or "manual",
        seq=int(row.get("seq") or 0),
        isSpecified=bool(row.get("isSpecified")),
        referencedCommandCount=int(row.get("referencedCommandCount") or 0),
    )


def _detail_dto(row: dict[str, Any]) -> InvariantDetailDTO:
    refs = [
        ReferencedConditionDTO(
            commandId=r["commandId"],
            commandName=r.get("commandName") or "",
            hasGwt=bool(r.get("hasGwt")),
        )
        for r in (row.get("referencedConditions") or [])
    ]
    return InvariantDetailDTO(
        id=row["id"],
        key=row["key"],
        name=row.get("name") or row.get("declaration") or "",
        declaration=row.get("declaration") or "",
        description=row.get("description"),
        source=row.get("source") or "manual",
        seq=int(row.get("seq") or 0),
        aggregateId=row.get("aggregateId") or "",
        aggregateName=row.get("aggregateName") or "",
        referencedConditions=refs,
        ownGwtParentId=row["id"] if row.get("hasOwnGwt") else None,
        isSpecified=bool(row.get("isSpecified")),
    )


# ── List (with lazy migration) ───────────────────────────────────────────


def list_for_aggregate(aggregate_id: str) -> InvariantListResponse | None:
    """List an Aggregate's Invariants. Returns None when the Aggregate is unknown.

    First call for an Aggregate lazily migrates its legacy `invariants` text.
    """
    if ops.get_aggregate(aggregate_id) is None:
        return None
    ops.migrate_legacy_invariants(aggregate_id)
    rows = ops.list_invariants(aggregate_id)
    return InvariantListResponse(
        aggregateId=aggregate_id,
        invariants=[_summary_dto(r) for r in rows],
    )


# ── CRUD ─────────────────────────────────────────────────────────────────


def create(aggregate_id: str, declaration: str, name: str | None, description: str | None):
    """Create an Invariant. Returns (detail, error) — error in
    {None, "aggregate_not_found", "duplicate", "invalid"}."""
    declaration = (declaration or "").strip()
    if not declaration:
        return None, "invalid"
    agg = ops.get_aggregate(aggregate_id)
    if agg is None:
        return None, "aggregate_not_found"
    created, err = ops.create_invariant(
        aggregate_id=aggregate_id,
        aggregate_key=agg["key"],
        declaration=declaration,
        name=name,
        description=description,
        source="manual",
    )
    if err:
        return None, err
    return get_detail(created["id"]), None


def get_detail(invariant_id: str) -> InvariantDetailDTO | None:
    row = ops.get_invariant(invariant_id)
    return _detail_dto(row) if row else None


def update(invariant_id: str, fields: dict[str, Any]) -> InvariantDetailDTO | None:
    patch = {k: v for k, v in fields.items() if v is not None}
    if "declaration" in patch and not str(patch["declaration"]).strip():
        del patch["declaration"]
    if not ops.update_invariant(invariant_id, patch):
        return None
    return get_detail(invariant_id)


def delete(invariant_id: str) -> bool:
    return ops.delete_invariant(invariant_id)


# ── References ───────────────────────────────────────────────────────────


def reference_candidates(invariant_id: str) -> ReferenceCandidatesResponse | None:
    rows = ops.list_reference_candidates(invariant_id)
    if rows is None:
        return None
    return ReferenceCandidatesResponse(
        candidates=[
            ReferenceCandidateDTO(
                commandId=r["commandId"],
                commandName=r.get("commandName") or "",
                hasGwt=bool(r.get("hasGwt")),
                alreadyReferenced=bool(r.get("alreadyReferenced")),
            )
            for r in rows
        ]
    )


def add_reference(invariant_id: str, command_id: str):
    """Returns (detail, status). status as in neo4j_ops.add_reference."""
    status = ops.add_reference(invariant_id, command_id)
    if status != "ok":
        return None, status
    return get_detail(invariant_id), "ok"


def remove_reference(invariant_id: str, command_id: str) -> bool:
    return ops.remove_reference(invariant_id, command_id)


# ── Exception domain-object catalog ──────────────────────────────────────


def _exception_dto(row: dict[str, Any]) -> ExceptionDTO:
    return ExceptionDTO(
        name=row.get("name") or "",
        message=row.get("message") or "",
        fields=[
            ExceptionFieldDTO(
                name=f.get("name") or "",
                type=f.get("type") or "String",
                description=f.get("description"),
            )
            for f in (row.get("fields") or [])
            if (f or {}).get("name")
        ],
    )


def get_exceptions(aggregate_id: str) -> ExceptionCatalogResponse | None:
    rows = ops.get_exceptions(aggregate_id)
    if rows is None:
        return None
    return ExceptionCatalogResponse(
        aggregateId=aggregate_id,
        exceptions=[_exception_dto(r) for r in rows],
    )


def put_exceptions(aggregate_id: str, exceptions: list[ExceptionDTO]) -> ExceptionCatalogResponse | None:
    payload = [e.model_dump() for e in exceptions]
    if not ops.put_exceptions(aggregate_id, payload):
        return None
    return get_exceptions(aggregate_id)
