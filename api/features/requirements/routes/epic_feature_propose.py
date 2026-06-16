"""Epic / Feature AI 제안 (034 — US1, in-process 엔진).

자연어 설명을 받아 Epic(BoundedContext) 또는 Feature 후보를 LLM이 제안한다.
후보는 미확정 상태로 반환되며(Constitution IV), 확정은 기존 create 경로
(`POST /bounded-context`, `POST /feature`)를 그대로 사용한다. 후보가 없으면
빈 배열을 반환해 수동 입력으로 폴백할 수 있다.
"""

from __future__ import annotations

from fastapi import APIRouter
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field
from starlette.requests import Request

from api.features.requirements.requirements_contracts import (
    EpicProposal,
    EpicProposeRequest,
    EpicProposeResponse,
    FeatureProposal,
    FeatureProposeRequest,
    FeatureProposeResponse,
)
from api.features.ingestion.ingestion_llm_runtime import get_llm
from api.platform.neo4j import get_session
from api.platform.observability.request_logging import http_context
from api.platform.observability.smart_logger import SmartLogger

router = APIRouter()


class _LLMEpics(BaseModel):
    proposals: list[EpicProposal] = Field(default_factory=list)


class _LLMFeatures(BaseModel):
    proposals: list[FeatureProposal] = Field(default_factory=list)


_EPIC_SYSTEM = (
    "You are a DDD domain architect. From the user's natural-language "
    "description, propose 1–3 Bounded Contexts (Epics) — each a cohesive "
    "business capability area. For each, return: `name` = a concise English "
    "PascalCase technical identifier (no spaces, e.g. CustomerSupport), "
    "`displayName` = a short human label in the SAME natural language as the "
    "user's input (e.g. 고객센터), and `description` = a one-line summary in "
    "that same language. Avoid duplicating the existing Bounded Contexts listed."
)

_FEATURE_SYSTEM = (
    "You are a DDD domain architect. From the user's natural-language "
    "description, propose 1–3 Features (cohesive groupings of user stories) "
    "that belong inside the given Bounded Context. Each has a short name and a "
    "one-line description. Avoid duplicating the existing Features listed. "
    "Write name/description in the SAME natural language as the user's input."
)


def _existing_bc_names() -> list[str]:
    with get_session() as session:
        return [r["n"] for r in session.run("MATCH (bc:BoundedContext) RETURN bc.name AS n")]


def _bc_context(bc_id: str) -> tuple[str | None, list[str]]:
    with get_session() as session:
        rec = session.run(
            "MATCH (bc:BoundedContext {id:$id}) RETURN bc.name AS n", id=bc_id
        ).single()
        feats = [
            r["n"]
            for r in session.run(
                "MATCH (bc:BoundedContext {id:$id})-[:HAS_FEATURE]->(f:Feature) RETURN f.name AS n",
                id=bc_id,
            )
        ]
    return (rec["n"] if rec else None), feats


@router.post("/epic/propose", response_model=EpicProposeResponse)
async def propose_epic(req: EpicProposeRequest, request: Request) -> EpicProposeResponse:
    """자연어 설명에서 Epic(BoundedContext) 후보를 제안한다(미확정)."""
    existing = _existing_bc_names()
    prompt = f"설명: {req.text}\n\n기존 Bounded Context: {', '.join(existing) or '(없음)'}"
    try:
        structured = get_llm().with_structured_output(_LLMEpics)
        result: _LLMEpics = structured.invoke(
            [SystemMessage(content=_EPIC_SYSTEM), HumanMessage(content=prompt)]
        )
        proposals = [p for p in (result.proposals or []) if (p.name or "").strip()]
    except Exception as exc:  # noqa: BLE001 — fall back to manual entry
        SmartLogger.log("ERROR", "Epic propose failed.", category="requirements.epic.propose", params={"error": str(exc)})
        proposals = []
    SmartLogger.log(
        "INFO", f"Proposed {len(proposals)} epic(s).",
        category="requirements.epic.propose",
        params={**http_context(request), "count": len(proposals)},
    )
    return EpicProposeResponse(proposals=proposals)


@router.post("/feature/propose", response_model=FeatureProposeResponse)
async def propose_feature(req: FeatureProposeRequest, request: Request) -> FeatureProposeResponse:
    """자연어 설명에서 Feature 후보를 제안한다(미확정). 소속 Epic 컨텍스트 반영."""
    bc_name, feats = (None, [])
    if req.boundedContextId:
        bc_name, feats = _bc_context(req.boundedContextId)
    prompt = (
        f"설명: {req.text}\n\n"
        f"소속 Bounded Context: {bc_name or '(미지정)'}\n"
        f"기존 Feature: {', '.join(feats) or '(없음)'}"
    )
    try:
        structured = get_llm().with_structured_output(_LLMFeatures)
        result: _LLMFeatures = structured.invoke(
            [SystemMessage(content=_FEATURE_SYSTEM), HumanMessage(content=prompt)]
        )
        proposals = []
        for p in result.proposals or []:
            if not (p.name or "").strip():
                continue
            p.boundedContextId = req.boundedContextId
            proposals.append(p)
    except Exception as exc:  # noqa: BLE001 — fall back to manual entry
        SmartLogger.log("ERROR", "Feature propose failed.", category="requirements.feature.propose", params={"error": str(exc)})
        proposals = []
    SmartLogger.log(
        "INFO", f"Proposed {len(proposals)} feature(s).",
        category="requirements.feature.propose",
        params={**http_context(request), "count": len(proposals)},
    )
    return FeatureProposeResponse(proposals=proposals)
