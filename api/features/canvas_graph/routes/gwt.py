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

    given_fv = _section_values("givenFieldValues")
    when_fv = _section_values("whenFieldValues")
    then_fv = _section_values("thenFieldValues")

    # 입력 문장이 모호해(구체 값 없음) 어떤 필드도 채워지지 않은 경우, 같은 속성 카탈로그를
    # 근거로 **구체화된 추천 시나리오**(문장 + 그 시나리오의 필드 값)를 1회 더 생성해 함께
    # 내려준다. 프런트는 추출이 비었을 때 이 추천 시나리오로 생성할지 사용자에게 묻는다.
    suggestion: dict[str, Any] | None = None
    if not (given_fv or when_fv or then_fv):
        suggestion = await _suggest_concrete_scenario(catalog, text, request)

    return {
        "success": True,
        "givenFieldValues": given_fv,
        "whenFieldValues": when_fv,
        "thenFieldValues": then_fv,
        "suggestion": suggestion,
    }


_SUGGEST_SYSTEM_PROMPT = (
    "You are helping author a concrete Given/When/Then test scenario for an event-storming "
    "model. The user typed a scenario that was too vague to extract any field values from "
    "(it stated no concrete numbers, ids, or enum values). Using ONLY the property catalog "
    "provided, invent ONE concrete, plausible, fully-specified scenario that the catalog can "
    "represent, staying faithful to the user's intent. Pick realistic concrete values "
    "(numbers without quotes, valid enum items from the list, short ids/strings). "
    "Return ONLY a JSON object of the form "
    '{"scenario": "<one natural-language sentence>", '
    '"givenFieldValues": {...}, "whenFieldValues": {...}, "thenFieldValues": {...}}. '
    "Map values onto the EXACT physical property names. Omit a section (use {}) if nothing "
    "applies. The scenario sentence MUST be consistent with the field values you return. "
    "CRITICAL: write the `scenario` sentence in the SAME natural language as the user's input "
    "below — if the user wrote Korean, the scenario MUST be Korean; if English, English. "
    "Property names and id/enum values stay verbatim, but the surrounding prose follows the "
    "user's language."
)


def _scenario_language_directive(user_text: str) -> str:
    """입력 문장의 언어에 맞춰 추천 시나리오 언어를 강제하는 지시문.

    한글 음절이 하나라도 있으면 한국어로, 아니면 입력과 동일 언어로 작성하도록 명시한다.
    카탈로그의 영문 속성명 때문에 모델이 영어로 흘러가는 것을 막는 하드 가드.
    """
    has_hangul = any("가" <= ch <= "힣" for ch in user_text)
    if has_hangul:
        return "IMPORTANT: The user's input is Korean, so the `scenario` sentence MUST be written in Korean (한국어)."
    return "IMPORTANT: Write the `scenario` sentence in the SAME language as the user's input above."


async def _suggest_concrete_scenario(catalog: str, user_text: str, request: Request) -> dict[str, Any] | None:
    """모호한 입력에 대해 카탈로그 기반의 **구체화된 추천 시나리오**(문장 + 필드 값)를 1회 생성.

    실패(타임아웃/파싱오류/빈 결과)하면 None — 프런트는 추천 없이 안내만 표시하면 된다.
    """
    human_prompt = (
        f"PROPERTY CATALOG:\n{catalog}\n\n"
        f"USER'S VAGUE SCENARIO:\n{user_text}\n\n"
        f"{_scenario_language_directive(user_text)}\n\n"
        "Return the JSON object for ONE concrete scenario now."
    )
    try:
        from langchain_core.messages import HumanMessage

        from api.platform.llm import get_llm
        from api.platform.llm_messages import build_system_message

        llm = get_llm()
        response = await asyncio.wait_for(
            asyncio.to_thread(
                llm.invoke,
                [build_system_message(_SUGGEST_SYSTEM_PROMPT), HumanMessage(content=human_prompt)],
            ),
            timeout=120.0,
        )
        content = response.content if hasattr(response, "content") else str(response)
        parsed = json.loads(_strip_json_fence(content))
    except Exception as exc:  # noqa: BLE001 - 추천은 부가 기능이라 실패해도 본 응답을 막지 않는다.
        SmartLogger.log(
            "WARNING",
            "Suggest concrete GWT scenario failed (non-fatal).",
            category="api.graph.gwt.parse_nl",
            params={**http_context(request), "error": str(exc)},
        )
        return None

    if not isinstance(parsed, dict):
        return None
    scenario = str(parsed.get("scenario") or "").strip()

    def _sv(key: str) -> dict[str, Any]:
        v = parsed.get(key)
        return v if isinstance(v, dict) else {}

    given_fv, when_fv, then_fv = _sv("givenFieldValues"), _sv("whenFieldValues"), _sv("thenFieldValues")
    # 문장도 값도 못 만들었으면 추천 없음.
    if not scenario or not (given_fv or when_fv or then_fv):
        return None
    return {
        "scenario": scenario,
        "givenFieldValues": given_fv,
        "whenFieldValues": when_fv,
        "thenFieldValues": then_fv,
    }

