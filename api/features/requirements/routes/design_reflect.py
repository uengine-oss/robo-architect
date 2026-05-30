"""설계 미반영 User Story 식별 + 설계 자동 반영 오케스트레이션 (034 — US7).

"설계 미반영" = `(UserStory)-[:IMPLEMENTS]->(:Command)` 부재(design-trace empty).
Event Modeling / Design 탭 진입 시 식별해 "설계에 반영하시겠습니까?" 프롬프트의
대상으로 삼는다. 반영(reflect)은 기존 change_management 설계 변경 계획을 US별로
오케스트레이션해 제안을 만든다(최종 그래프 반영은 사용자 확인 단계 — HITL).

신규 노드 라벨/관계 0건 — 기존 IMPLEMENTS/Command/Aggregate 구조 재사용.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field
from starlette.requests import Request

from api.features.ingestion.event_storming.neo4j_client import get_neo4j_client
from api.features.ingestion.ingestion_llm_runtime import get_llm
from api.features.requirements.requirements_contracts import (
    DesignReflectRequest,
    DesignReflectResponse,
    PendingDesignResponse,
    PendingUS,
    ReflectedDesign,
)
from api.platform.neo4j import get_session
from api.platform.observability.request_logging import http_context
from api.platform.observability.smart_logger import SmartLogger

router = APIRouter()


_PENDING_QUERY = """
MATCH (us:UserStory)
WHERE NOT (us)-[:IMPLEMENTS]->(:Command)
OPTIONAL MATCH (us)-[:IMPLEMENTS]->(bc:BoundedContext)
OPTIONAL MATCH (f:Feature)-[:HAS_USER_STORY]->(us)
RETURN us.id AS id, us.role AS role, us.action AS action, us.benefit AS benefit,
       bc.id AS bcId, f.id AS featureId
ORDER BY us.id
"""

# Scope filters appended to the base match.
_SCOPE_BC = "AND (us)-[:IMPLEMENTS]->(:BoundedContext {id: $scopeId})"
_SCOPE_FEATURE = "AND (:Feature {id: $scopeId})-[:HAS_USER_STORY]->(us)"


@router.get("/user-stories/pending-design", response_model=PendingDesignResponse)
async def pending_design(
    request: Request, scopeType: str = "project", scopeId: str = "*"
) -> PendingDesignResponse:
    """설계가 아직 반영되지 않은 User Story 목록을 반환한다(범위 옵션)."""
    query = _PENDING_QUERY
    params: dict[str, Any] = {}
    if scopeType == "bounded_context" and scopeId and scopeId != "*":
        query = query.replace("WHERE NOT", "WHERE NOT").replace(
            "RETURN us.id", _SCOPE_BC + "\nRETURN us.id"
        )
        params["scopeId"] = scopeId
    elif scopeType == "feature" and scopeId and scopeId != "*":
        query = query.replace("RETURN us.id", _SCOPE_FEATURE + "\nRETURN us.id")
        params["scopeId"] = scopeId

    with get_session() as session:
        rows = list(session.run(query, **params))

    pending = [
        PendingUS(
            userStoryId=r["id"],
            role=r["role"] or "",
            action=r["action"] or "",
            benefit=r["benefit"] or "",
            featureId=r["featureId"],
            boundedContextId=r["bcId"],
        )
        for r in rows
        if r["id"]
    ]
    SmartLogger.log(
        "INFO",
        f"{len(pending)} design-pending user stories.",
        category="requirements.design.pending",
        params={**http_context(request), "scope_type": scopeType, "count": len(pending)},
    )
    return PendingDesignResponse(pending=pending)


# ── 설계 자동 반영 (US7) ──────────────────────────────────────────────────


class _LLMDesign(BaseModel):
    aggregateName: str = ""
    commandName: str = ""
    eventName: str = ""


_DESIGN_SYSTEM = (
    "You are a DDD / Event Storming modeler. Given ONE user story and the list "
    "of existing Aggregates in its Bounded Context, design the minimal slice "
    "that implements it: choose the Aggregate it belongs to (REUSE an existing "
    "aggregate name when one fits; otherwise propose a concise new one), the "
    "Command the user triggers, and the Event the command emits. "
    "Use the SAME natural language as the user story (e.g. Korean). "
    "Command is an imperative (e.g. '주문 취소'); Event is past tense (e.g. '주문 취소됨')."
)


def _us_context(us_id: str) -> dict | None:
    with get_session() as session:
        rec = session.run(
            """
            MATCH (us:UserStory {id: $id})
            OPTIONAL MATCH (us)-[:IMPLEMENTS]->(bc:BoundedContext)
            OPTIONAL MATCH (f:Feature)-[:HAS_USER_STORY]->(us)
            OPTIONAL MATCH (fbc:BoundedContext)-[:HAS_FEATURE]->(f)
            RETURN us.role AS role, us.action AS action, us.benefit AS benefit,
                   coalesce(bc.id, fbc.id) AS bcId
            """,
            id=us_id,
        ).single()
    return dict(rec) if rec else None


@router.post("/design/reflect", response_model=DesignReflectResponse)
async def reflect_design(req: DesignReflectRequest, request: Request) -> DesignReflectResponse:
    """선택된 미반영 User Story들에 대해 Aggregate→Command→Event 설계를 생성·반영한다."""
    client = get_neo4j_client()
    reflected: list[ReflectedDesign] = []

    for us_id in req.userStoryIds:
        ctx = _us_context(us_id)
        if not ctx:
            reflected.append(ReflectedDesign(userStoryId=us_id, ok=False, message="User Story not found"))
            continue
        bc_id = ctx.get("bcId")
        if not bc_id:
            reflected.append(
                ReflectedDesign(userStoryId=us_id, ok=False, message="배치할 Bounded Context가 없습니다")
            )
            continue

        existing = client.get_aggregates_by_bc(bc_id)
        existing_names = [a["name"] for a in existing if a.get("name")]
        prompt = (
            f"User Story: As a {ctx.get('role','')}, I want to {ctx.get('action','')}, "
            f"so that {ctx.get('benefit','')}\n\n"
            f"기존 Aggregate: {', '.join(existing_names) or '(없음)'}"
        )
        try:
            design: _LLMDesign = get_llm().with_structured_output(_LLMDesign).invoke(
                [SystemMessage(content=_DESIGN_SYSTEM), HumanMessage(content=prompt)]
            )
        except Exception as exc:  # noqa: BLE001
            reflected.append(ReflectedDesign(userStoryId=us_id, boundedContextId=bc_id, ok=False, message=str(exc)))
            continue

        agg_name = (design.aggregateName or "").strip() or (existing_names[0] if existing_names else "Default")
        cmd_name = (design.commandName or "").strip() or (ctx.get("action") or "Command")
        evt_name = (design.eventName or "").strip()

        # Reuse an existing aggregate (case-insensitive) or create a new one.
        match = next((a for a in existing if (a.get("name") or "").lower() == agg_name.lower()), None)
        reused = match is not None
        try:
            agg_id = match["id"] if match else client.create_aggregate(name=agg_name, bc_id=bc_id)["id"]
            cmd = client.create_command(name=cmd_name, aggregate_id=agg_id)
            cmd_id = cmd["id"]
            if evt_name:
                client.create_event(name=evt_name, command_id=cmd_id)
            client.link_user_story_to_command(us_id, cmd_id)
            client.link_user_story_to_aggregate(us_id, agg_id)
        except Exception as exc:  # noqa: BLE001
            reflected.append(ReflectedDesign(userStoryId=us_id, boundedContextId=bc_id, ok=False, message=str(exc)))
            continue

        reflected.append(
            ReflectedDesign(
                userStoryId=us_id,
                boundedContextId=bc_id,
                aggregateName=agg_name,
                commandName=cmd_name,
                eventName=evt_name or None,
                reusedAggregate=reused,
                ok=True,
            )
        )

    SmartLogger.log(
        "INFO",
        f"Reflected design for {sum(1 for r in reflected if r.ok)}/{len(reflected)} user stories.",
        category="requirements.design.reflect",
        params={**http_context(request), "count": len(reflected)},
    )
    return DesignReflectResponse(reflected=reflected)
