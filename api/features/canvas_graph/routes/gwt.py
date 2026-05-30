from __future__ import annotations

import asyncio
import json
import re
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
    # 027 — a Then may declare an Exception outcome instead of (or alongside) an
    # Event. `exceptionName` resolves to an entry in the owning Aggregate's
    # `exceptions` domain-object catalog. Applies to Command and Invariant GWT.
    exceptionName: str | None = None


class _GWTTestCase(BaseModel):
    scenarioDescription: str | None = None
    givenFieldValues: dict[str, Any] = Field(default_factory=dict)
    whenFieldValues: dict[str, Any] = Field(default_factory=dict)
    thenFieldValues: dict[str, Any] = Field(default_factory=dict)


class UpsertGWTRequest(BaseModel):
    # "Invariant" added by feature 027 — an invariant-owned GWT bundle is stored
    # as GWT {parentType:"Invariant", parentId:<invariant.id>}. The upsert query
    # matches the parent by id + label, so no further change is needed.
    parentType: Literal["Command", "Policy", "Invariant"]
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


@router.get("/gwt/{parent_type}/{parent_id}")
async def get_gwt(parent_type: str, parent_id: str) -> dict[str, Any]:
    """Read the single GWT bundle for a parent (Command/Policy/Invariant).

    Returns ``{"gwt": null}`` when the parent has no GWT yet. Added by feature
    027 so the Invariant editor can load both invariant-owned and referenced
    Command GWT bundles into the shared editor component.
    """
    query = """
    MATCH (gwt:GWT {parentType: $parent_type, parentId: $parent_id})
    RETURN gwt {.id, .parentType, .parentId, .givenRef, .whenRef, .thenRef, .testCases} AS gwt
    """
    with get_session() as session:
        rec = session.run(query, parent_type=parent_type, parent_id=parent_id).single()
    return {"gwt": dict(rec["gwt"]) if rec else None}


# ---------------------------------------------------------------------------
# Natural-language -> GWT field values
# ---------------------------------------------------------------------------


class _NLProperty(BaseModel):
    name: str
    displayName: str | None = None
    type: str | None = None
    enumItems: list[str] = Field(default_factory=list)


class _NLSection(BaseModel):
    name: str | None = None
    properties: list[_NLProperty] = Field(default_factory=list)


class ParseNLRequest(BaseModel):
    text: str
    given: _NLSection | None = None
    when: _NLSection | None = None
    then: _NLSection | None = None


def _section_brief(label: str, section: _NLSection | None) -> str:
    """Render a section's property catalog for the LLM prompt."""
    if section is None:
        return f"{label}: (not applicable — omit this section in the output)"
    if not section.properties:
        return f"{label} ({section.name or ''}): (no properties)"
    lines = [f"{label} ({section.name or ''}):"]
    for p in section.properties:
        logical = f" / 논리명: {p.displayName}" if p.displayName and p.displayName != p.name else ""
        enum = f" / enum 값: {', '.join(p.enumItems)}" if p.enumItems else ""
        lines.append(f"  - {p.name} (type: {p.type or 'String'}{logical}{enum})")
    return "\n".join(lines)


def _strip_json_fence(content: str) -> str:
    if "```json" in content:
        content = content.split("```json", 1)[1].split("```", 1)[0]
    elif "```" in content:
        content = content.split("```", 1)[1].split("```", 1)[0]
    content = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", content)
    return content.strip()


@router.post("/gwt/parse-nl")
async def parse_gwt_nl(payload: ParseNLRequest, request: Request) -> dict[str, Any]:
    """
    Parse a natural-language scenario sentence into Given/When/Then field values.

    The caller supplies the property catalog (physical name, logical/display name,
    type, enum items) for each section so the LLM can map free text onto the exact
    physical property keys and emit type-correct values.
    """
    text = (payload.text or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="text is required")

    catalog = "\n".join(
        [
            _section_brief("Given", payload.given),
            _section_brief("When", payload.when),
            _section_brief("Then", payload.then),
        ]
    )

    system_prompt = (
        "You convert a natural-language Given/When/Then test scenario into structured "
        "field values for an event-storming model. You are given the property catalog "
        "for each section. Map the described facts onto the EXACT physical property "
        "names (the `name`, not the logical name). Only include properties that the "
        "sentence actually states or clearly implies — never invent values for "
        "unmentioned properties. Match value types strictly: numbers without quotes, "
        "booleans as true/false, enum values must be one of the listed enum items, "
        "dates as ISO strings. Respond with ONLY a JSON object of the form "
        '{"givenFieldValues": {...}, "whenFieldValues": {...}, "thenFieldValues": {...}}. '
        "Omit a section entirely (use {}) if it is not applicable or nothing is stated for it."
    )
    human_prompt = (
        f"PROPERTY CATALOG:\n{catalog}\n\n"
        f"NATURAL LANGUAGE SCENARIO:\n{text}\n\n"
        "Return the JSON object now."
    )

    SmartLogger.log(
        "INFO",
        "Parse GWT natural language requested.",
        category="api.graph.gwt.parse_nl",
        params={**http_context(request), "textLength": len(text)},
    )

    try:
        from langchain_core.messages import HumanMessage

        from api.platform.llm import get_llm
        from api.platform.llm_messages import build_system_message

        llm = get_llm()
        response = await asyncio.wait_for(
            asyncio.to_thread(
                llm.invoke,
                [build_system_message(system_prompt), HumanMessage(content=human_prompt)],
            ),
            timeout=120.0,
        )
        content = response.content if hasattr(response, "content") else str(response)
        parsed = json.loads(_strip_json_fence(content))
    except asyncio.TimeoutError:
        raise HTTPException(status_code=504, detail="자연어 해석 시간 초과")
    except json.JSONDecodeError as exc:
        SmartLogger.log(
            "WARNING",
            "Parse GWT NL: invalid JSON from LLM.",
            category="api.graph.gwt.parse_nl",
            params={**http_context(request), "error": str(exc)},
        )
        raise HTTPException(status_code=502, detail="자연어 해석 결과를 파싱하지 못했습니다")
    except Exception as exc:  # noqa: BLE001 - surface LLM/config errors to the client
        SmartLogger.log(
            "ERROR",
            "Parse GWT NL failed.",
            category="api.graph.gwt.parse_nl",
            params={**http_context(request), "error": str(exc)},
        )
        raise HTTPException(status_code=500, detail=f"자연어 해석 실패: {exc}")

    def _section_values(key: str) -> dict[str, Any]:
        value = parsed.get(key) if isinstance(parsed, dict) else None
        return value if isinstance(value, dict) else {}

    return {
        "success": True,
        "givenFieldValues": _section_values("givenFieldValues"),
        "whenFieldValues": _section_values("whenFieldValues"),
        "thenFieldValues": _section_values("thenFieldValues"),
    }

