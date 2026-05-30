"""DDD 적합성·입도·정합성 검증 (034 — US6, in-process 엔진).

추가/생성되는 요구사항(Epic/Feature/User Story)이 (1) 올바른 BC(Epic)에 속하는지,
(2) Feature 입도가 과도하지 않은지, (3) 기존 요구사항과 충돌/중복하는지를 in-process
LLM이 그래프 컨텍스트(정의된 BC 목록 + 대상 BC의 Feature·User Story)로 검증한다.
교정안은 비차단(경고)이며, 적합하면 findings 가 비어 `ok=true`.

robo-spec 스킬(`robo-validate`) 기반의 claude-ide 경로는 후속 — 여기서는 설치가 필요
없는 in-process 경로를 제공한다.
"""

from __future__ import annotations

from fastapi import APIRouter
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field
from starlette.requests import Request

from api.features.ingestion.event_storming.neo4j_client import get_neo4j_client
from api.features.ingestion.ingestion_llm_runtime import get_llm
from api.features.requirements.requirements_contracts import (
    ValidateRequest,
    ValidateResponse,
    ValidationFinding,
)
from api.platform.neo4j import get_session
from api.platform.observability.request_logging import http_context
from api.platform.observability.smart_logger import SmartLogger

router = APIRouter()


class _LLMFindings(BaseModel):
    findings: list[ValidationFinding] = Field(default_factory=list)


_SYSTEM_PROMPT = (
    "You are a DDD / Event Storming domain architect reviewing whether a "
    "requirement fits the existing model. Given the target requirement and the "
    "list of defined Bounded Contexts (Epics) with their Features and existing "
    "User Stories, check three things and report ONLY real problems as findings:\n"
    "1) kind='wrong_bc' — the target belongs in a DIFFERENT Bounded Context than "
    "the one it is assigned to. Put the better BC id in suggestion.suggestedBoundedContextId "
    "and action='replace_bc'.\n"
    "2) kind='oversized_feature' — a Feature is too broad and should be split into "
    "smaller Features / User Stories. action='split', describe the split in details.\n"
    "3) kind='spec_conflict' — the target duplicates or contradicts an existing "
    "User Story. action='merge' or 'differentiate', name the conflicting item in affected[].\n"
    "If everything is appropriate, return an EMPTY findings list. Be conservative: "
    "do NOT invent problems. Write all message/details text in the SAME natural "
    "language as the provided requirement (e.g. Korean if the target is Korean)."
)


def _all_bcs() -> list[dict]:
    with get_session() as session:
        return [
            {"id": r["id"], "name": r["name"], "description": r["d"]}
            for r in session.run(
                "MATCH (bc:BoundedContext) RETURN bc.id AS id, bc.name AS name, bc.description AS d"
            )
        ]


def _features_and_stories(bc_id: str) -> tuple[list[dict], list[dict]]:
    with get_session() as session:
        feats = [
            {"id": r["id"], "name": r["name"]}
            for r in session.run(
                "MATCH (bc:BoundedContext {id:$id})-[:HAS_FEATURE]->(f:Feature) RETURN f.id AS id, f.name AS name",
                id=bc_id,
            )
        ]
    stories = get_neo4j_client().get_user_stories_by_bc(bc_id)
    return feats, stories


def _build_prompt(req: ValidateRequest) -> str:
    lines: list[str] = ["[검증 대상]"]
    lines.append(f"종류: {req.targetType}")
    if req.name:
        lines.append(f"이름: {req.name}")
    if req.description:
        lines.append(f"설명: {req.description}")
    if req.action:
        lines.append(f"User Story: As a {req.role or ''}, I want to {req.action}, so that {req.benefit or ''}")
    if req.boundedContextId:
        lines.append(f"배치된 BoundedContext id: {req.boundedContextId}")
    if req.featureId:
        lines.append(f"배치된 Feature id: {req.featureId}")

    lines.append("\n[정의된 Bounded Context 목록]")
    for bc in _all_bcs():
        lines.append(f"- id={bc['id']} | {bc['name']} | {bc.get('description') or ''}")

    if req.boundedContextId:
        feats, stories = _features_and_stories(req.boundedContextId)
        lines.append("\n[대상 BC의 Feature]")
        lines += [f"- {f['name']}" for f in feats] or ["- (없음)"]
        lines.append("\n[대상 BC의 기존 User Story]")
        lines += [f"- {s.get('role','')}: {s.get('action','')}" for s in stories] or ["- (없음)"]

    lines.append("\n부적합 항목만 findings로 보고하세요. 모두 적합하면 빈 목록을 반환하세요.")
    return "\n".join(lines)


@router.post("/validate", response_model=ValidateResponse)
async def validate_requirement(req: ValidateRequest, request: Request) -> ValidateResponse:
    """요구사항의 DDD 적합성·입도·정합성을 검증하고 교정안을 제안(비차단)."""
    try:
        structured = get_llm().with_structured_output(_LLMFindings)
        result: _LLMFindings = structured.invoke(
            [SystemMessage(content=_SYSTEM_PROMPT), HumanMessage(content=_build_prompt(req))]
        )
        findings = result.findings or []
    except Exception as exc:  # noqa: BLE001 — degrade to "no findings" (non-blocking)
        SmartLogger.log(
            "ERROR",
            "DDD validation failed.",
            category="requirements.validate",
            params={"error": str(exc)},
        )
        findings = []

    SmartLogger.log(
        "INFO",
        f"DDD validation produced {len(findings)} finding(s).",
        category="requirements.validate",
        params={**http_context(request), "target_type": req.targetType, "count": len(findings)},
    )
    return ValidateResponse(ok=len(findings) == 0, findings=findings, source="in-process")
