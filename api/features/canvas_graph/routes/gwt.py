from __future__ import annotations

import json
from typing import Any, Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from starlette.requests import Request

from api.platform.neo4j import get_session
from api.platform.observability.request_logging import http_context
from api.platform.observability.smart_logger import SmartLogger

router = APIRouter()


class _GWTRef(BaseModel):
    referencedNodeId: str | None = None
    referencedNodeType: str | None = None
    name: str | None = None


class _GWTTestCase(BaseModel):
    scenarioDescription: str | None = None
    givenFieldValues: dict[str, Any] = Field(default_factory=dict)
    whenFieldValues: dict[str, Any] = Field(default_factory=dict)
    thenFieldValues: dict[str, Any] = Field(default_factory=dict)


class UpsertGWTRequest(BaseModel):
    parentType: Literal["Command", "Policy"]
    parentId: str
    givenRef: _GWTRef | None = None
    whenRef: _GWTRef | None = None
    thenRef: _GWTRef | None = None
    testCases: list[_GWTTestCase] = Field(default_factory=list)


@router.post("/gwt/upsert")
async def upsert_gwt(payload: UpsertGWTRequest, request: Request) -> dict[str, Any]:
    """
    Upsert a single GWT node per parent (Command/Policy).
    - Mapped refs are fixed (given/when/then referenced nodes)
    - Test cases are stored as a JSON array on the GWT node
    """
    if not payload.parentId:
        raise HTTPException(status_code=400, detail="parentId is required")

    query = """
    MATCH (parent {id: $parent_id})
    WHERE $parent_type IN labels(parent)
    MERGE (gwt:GWT {parentType: $parent_type, parentId: $parent_id})
    ON CREATE SET gwt.id = randomUUID(),
                  gwt.createdAt = datetime()
    SET gwt.updatedAt = datetime(),
        gwt.givenRef = $given_ref_json,
        gwt.whenRef = $when_ref_json,
        gwt.thenRef = $then_ref_json,
        gwt.testCases = $test_cases_json
    MERGE (parent)-[:HAS_GWT]->(gwt)
    WITH gwt
    OPTIONAL MATCH (gwt)-[r:REFERENCES]->()
    DELETE r
    WITH gwt
    RETURN gwt {.id, .parentType, .parentId, .givenRef, .whenRef, .thenRef, .testCases} as gwt
    """

    given_ref_json = json.dumps(payload.givenRef.model_dump()) if payload.givenRef else None
    when_ref_json = json.dumps(payload.whenRef.model_dump()) if payload.whenRef else None
    then_ref_json = json.dumps(payload.thenRef.model_dump()) if payload.thenRef else None
    test_cases_json = json.dumps([tc.model_dump() for tc in (payload.testCases or [])])

    SmartLogger.log(
        "INFO",
        "Upsert GWT requested.",
        category="api.graph.gwt.upsert",
        params={**http_context(request), "parentType": payload.parentType, "parentId": payload.parentId},
    )

    with get_session() as session:
        rec = session.run(
            query,
            parent_type=payload.parentType,
            parent_id=payload.parentId,
            given_ref_json=given_ref_json,
            when_ref_json=when_ref_json,
            then_ref_json=then_ref_json,
            test_cases_json=test_cases_json,
        ).single()

        if not rec:
            raise HTTPException(status_code=500, detail="Failed to upsert GWT")

        out = dict(rec.get("gwt") or {})

    # Best-effort: create REFERENCES edges after node exists (separate tx not required)
    ref_query = """
    MATCH (gwt:GWT {parentType: $parent_type, parentId: $parent_id})
    WITH gwt, $refs as refs
    UNWIND refs as ref
    WITH gwt, ref
    WHERE ref.id IS NOT NULL AND ref.type IS NOT NULL
    MATCH (n {id: ref.id})
    WHERE ref.type IN labels(n)
    MERGE (gwt)-[:REFERENCES]->(n)
    RETURN count(*) as linked
    """
    refs: list[dict[str, str]] = []
    for r in (payload.givenRef, payload.whenRef, payload.thenRef):
        if r and r.referencedNodeId and r.referencedNodeType:
            refs.append({"id": r.referencedNodeId, "type": r.referencedNodeType})

    if refs:
        with get_session() as session:
            session.run(ref_query, parent_type=payload.parentType, parent_id=payload.parentId, refs=refs)

    return {"success": True, "gwt": out}

