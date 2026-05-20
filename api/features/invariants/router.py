"""Aggregate Invariants API (feature router) — 027 aggregate-invariants.

- List an Aggregate's Invariants (triggers lazy legacy-text migration)
- Invariant CRUD
- Shared-condition references (VERIFIED_BY) add/remove + candidates

GWT editing itself reuses the existing `POST /api/graph/gwt/upsert` endpoint
with `parentType="Invariant"` (invariant-owned) or `parentType="Command"`
(shared) — see specs/027-aggregate-invariants/contracts/rest-api.md §4.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Response
from starlette.requests import Request

from api.platform.observability.request_logging import http_context
from api.platform.observability.smart_logger import SmartLogger

from . import invariants_service as service
from .invariants_contracts import (
    AddReferenceRequest,
    CreateInvariantRequest,
    ExceptionCatalogResponse,
    InvariantDetailDTO,
    InvariantListResponse,
    PutExceptionsRequest,
    ReferenceCandidatesResponse,
    UpdateInvariantRequest,
)

router = APIRouter(tags=["invariants"])


# ── §1 List invariants of an Aggregate (triggers lazy migration) ─────────


@router.get("/api/aggregates/{aggregate_id}/invariants", response_model=InvariantListResponse)
async def list_invariants(aggregate_id: str, request: Request) -> InvariantListResponse:
    result = service.list_for_aggregate(aggregate_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Aggregate {aggregate_id} not found")
    SmartLogger.log(
        "INFO",
        "Invariants listed for aggregate.",
        category="invariants.list",
        params={**http_context(request), "aggregate_id": aggregate_id, "count": len(result.invariants)},
    )
    return result


# ── §2 Invariant CRUD ────────────────────────────────────────────────────


@router.post(
    "/api/aggregates/{aggregate_id}/invariants",
    response_model=InvariantDetailDTO,
    status_code=201,
)
async def create_invariant(
    aggregate_id: str, req: CreateInvariantRequest, request: Request
) -> InvariantDetailDTO:
    detail, err = service.create(aggregate_id, req.declaration, req.name, req.description)
    if err == "invalid":
        raise HTTPException(status_code=422, detail="declaration must not be empty")
    if err == "aggregate_not_found":
        raise HTTPException(status_code=404, detail=f"Aggregate {aggregate_id} not found")
    if err == "duplicate":
        raise HTTPException(
            status_code=409,
            detail="An invariant with the same declaration already exists on this aggregate",
        )
    SmartLogger.log(
        "INFO",
        "Invariant created.",
        category="invariants.create",
        params={**http_context(request), "aggregate_id": aggregate_id, "invariant_id": detail.id},
    )
    return detail


@router.get("/api/invariants/{invariant_id}", response_model=InvariantDetailDTO)
async def get_invariant(invariant_id: str) -> InvariantDetailDTO:
    detail = service.get_detail(invariant_id)
    if detail is None:
        raise HTTPException(status_code=404, detail=f"Invariant {invariant_id} not found")
    return detail


@router.patch("/api/invariants/{invariant_id}", response_model=InvariantDetailDTO)
async def update_invariant(
    invariant_id: str, req: UpdateInvariantRequest, request: Request
) -> InvariantDetailDTO:
    detail = service.update(
        invariant_id,
        {"declaration": req.declaration, "name": req.name, "description": req.description},
    )
    if detail is None:
        raise HTTPException(status_code=404, detail=f"Invariant {invariant_id} not found")
    SmartLogger.log(
        "INFO",
        "Invariant updated.",
        category="invariants.update",
        params={**http_context(request), "invariant_id": invariant_id},
    )
    return detail


@router.delete("/api/invariants/{invariant_id}", status_code=204)
async def delete_invariant(invariant_id: str, request: Request) -> Response:
    if not service.delete(invariant_id):
        raise HTTPException(status_code=404, detail=f"Invariant {invariant_id} not found")
    SmartLogger.log(
        "INFO",
        "Invariant deleted.",
        category="invariants.delete",
        params={**http_context(request), "invariant_id": invariant_id},
    )
    return Response(status_code=204)


# ── §3 Shared-condition references (VERIFIED_BY) ──────────────────────────


@router.get(
    "/api/invariants/{invariant_id}/reference-candidates",
    response_model=ReferenceCandidatesResponse,
)
async def reference_candidates(invariant_id: str) -> ReferenceCandidatesResponse:
    result = service.reference_candidates(invariant_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Invariant {invariant_id} not found")
    return result


@router.post(
    "/api/invariants/{invariant_id}/references",
    response_model=InvariantDetailDTO,
    status_code=201,
)
async def add_reference(
    invariant_id: str, req: AddReferenceRequest, request: Request
) -> InvariantDetailDTO:
    detail, status = service.add_reference(invariant_id, req.commandId)
    if status == "invariant_not_found":
        raise HTTPException(status_code=404, detail=f"Invariant {invariant_id} not found")
    if status == "command_not_found":
        raise HTTPException(status_code=404, detail=f"Command {req.commandId} not found")
    if status == "wrong_aggregate":
        raise HTTPException(
            status_code=422, detail="Command does not belong to the invariant's aggregate"
        )
    if status == "already_referenced":
        raise HTTPException(status_code=409, detail="Command already referenced")
    SmartLogger.log(
        "INFO",
        "Invariant reference added.",
        category="invariants.reference.add",
        params={**http_context(request), "invariant_id": invariant_id, "command_id": req.commandId},
    )
    return detail


@router.delete(
    "/api/invariants/{invariant_id}/references/{command_id}", status_code=204
)
async def remove_reference(
    invariant_id: str, command_id: str, request: Request
) -> Response:
    if not service.remove_reference(invariant_id, command_id):
        raise HTTPException(status_code=404, detail="Reference not found")
    SmartLogger.log(
        "INFO",
        "Invariant reference removed.",
        category="invariants.reference.remove",
        params={**http_context(request), "invariant_id": invariant_id, "command_id": command_id},
    )
    return Response(status_code=204)


# ── §4 Exception domain-object catalog (per Aggregate) ────────────────────
# An Exception is an Aggregate domain object, sibling to enumerations/value
# objects. A GWT Then (Command or Invariant) references one by name.


@router.get(
    "/api/aggregates/{aggregate_id}/exceptions", response_model=ExceptionCatalogResponse
)
async def list_exceptions(aggregate_id: str) -> ExceptionCatalogResponse:
    result = service.get_exceptions(aggregate_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Aggregate {aggregate_id} not found")
    return result


@router.put(
    "/api/aggregates/{aggregate_id}/exceptions", response_model=ExceptionCatalogResponse
)
async def replace_exceptions(
    aggregate_id: str, req: PutExceptionsRequest, request: Request
) -> ExceptionCatalogResponse:
    result = service.put_exceptions(aggregate_id, req.exceptions)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Aggregate {aggregate_id} not found")
    SmartLogger.log(
        "INFO",
        "Aggregate exception catalog updated.",
        category="invariants.exceptions.put",
        params={**http_context(request), "aggregate_id": aggregate_id, "count": len(result.exceptions)},
    )
    return result
