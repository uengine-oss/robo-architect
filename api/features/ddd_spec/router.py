"""FastAPI router for ``/api/ddd-spec/*``.

Four endpoints — three sync, one SSE — projecting the event-storming graph
into the "DDD for SDD" artifact set under ``specs/bounded-contexts/`` and
``specs/context-map.md``.
"""
from __future__ import annotations

import json

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse, StreamingResponse

from api.features.ddd_spec import service
from api.features.ddd_spec.schemas import (
    GenerateAggregateRequest,
    GenerateAllRequest,
    GenerateBoundedContextRequest,
    GenerateContextMapRequest,
)

router = APIRouter(prefix="/api/ddd-spec", tags=["ddd-spec"])


def _http_lock_busy() -> HTTPException:
    return HTTPException(
        status_code=409,
        detail={"code": "lock_busy", "message": "Another DDD-spec generation is in progress."},
    )


@router.post("/generate-bounded-context")
def post_generate_bounded_context(req: GenerateBoundedContextRequest):
    """T022: synchronous full-set generation for one Bounded Context."""
    try:
        result = service.generate_bounded_context(req)
    except BlockingIOError:
        raise _http_lock_busy()
    except ValueError as e:
        code = str(e)
        if code == "bounded_context_not_found":
            raise HTTPException(
                status_code=404,
                detail={"code": code, "message": f"Bounded Context {req.bounded_context_id!r} not found."},
            )
        if code == "empty_bounded_context":
            raise HTTPException(
                status_code=400,
                detail={"code": code, "message": "Bounded Context has no Aggregates and no User Stories."},
            )
        raise
    return JSONResponse(content=result.model_dump())


@router.post("/generate-aggregate")
def post_generate_aggregate(req: GenerateAggregateRequest):
    """T030: refresh just one Aggregate Spec file."""
    try:
        result = service.generate_aggregate(req)
    except BlockingIOError:
        raise _http_lock_busy()
    except ValueError as e:
        code = str(e)
        if code == "aggregate_not_found":
            raise HTTPException(
                status_code=404,
                detail={"code": code, "message": f"Aggregate {req.aggregate_id!r} not found."},
            )
        raise
    return JSONResponse(content=result.model_dump())


@router.post("/generate-context-map")
def post_generate_context_map(req: GenerateContextMapRequest):
    """T027: (re)generate ``specs/context-map.md``."""
    try:
        result = service.generate_context_map(req)
    except BlockingIOError:
        raise _http_lock_busy()
    except ValueError as e:
        code = str(e)
        if code == "no_bounded_contexts":
            raise HTTPException(
                status_code=400,
                detail={"code": code, "message": "The graph contains no Bounded Contexts."},
            )
        raise
    return JSONResponse(content=result.model_dump())


@router.post("/generate-all")
async def post_generate_all(req: GenerateAllRequest):
    """T033: SSE-streamed full-model bootstrap."""

    async def _stream():
        async for event, payload in service.generate_all(req):
            yield f"event: {event}\ndata: {json.dumps(payload)}\n\n"

    return StreamingResponse(_stream(), media_type="text/event-stream")
