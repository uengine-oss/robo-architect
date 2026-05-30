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
from pydantic import BaseModel, Field
from starlette.requests import Request

from api.features.requirements.requirements_contracts import (
    PendingDesignResponse,
    PendingUS,
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
