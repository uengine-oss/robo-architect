"""설계 미반영 User Story 식별 + 설계 자동 반영 오케스트레이션 (034 — US7).

설계 미반영 User Story 식별 (034 — US7).

Event Modeling / Design 탭 진입 시 "설계 미반영" US를 식별해 "설계에 반영하시겠습니까?"
프롬프트의 대상으로 삼는다. 실제 설계 생성(반영)은 기존 인제스천 설계 단계를 재사용하는
`POST /api/ingest/user-stories/design`(incremental_design_runner)이 담당한다.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from starlette.requests import Request

from api.features.requirements.requirements_contracts import (
    PendingDesignResponse,
    PendingUS,
)
from api.platform.neo4j import get_session
from api.platform.observability.request_logging import http_context
from api.platform.observability.smart_logger import SmartLogger

router = APIRouter()


# "설계 미반영" = 어떤 설계객체(Aggregate / Command / Event / Policy / ReadModel)에도
# IMPLEMENTS로 연결되지 않은 User Story. 과거에는 Command 부재만 봤으나, 인제스천이
# Aggregate 단계에서 US를 거칠게 배치한 뒤 Command 단계에서 일부(특히 조회/알림성)만
# 매핑하기 때문에, "Command 없음"만 보면 이미 모델에 들어와 있는 US까지 미반영으로
# 과대 보고된다. 따라서 Aggregate 등 어떤 설계 연결이라도 있으면 "반영됨"으로 본다.
_PENDING_QUERY = """
MATCH (us:UserStory)
WHERE NOT (us)-[:IMPLEMENTS]->(:Aggregate)
  AND NOT (us)-[:IMPLEMENTS]->(:Command)
  AND NOT (us)-[:IMPLEMENTS]->(:Event)
  AND NOT (us)-[:IMPLEMENTS]->(:Policy)
  AND NOT (us)-[:IMPLEMENTS]->(:ReadModel)
OPTIONAL MATCH (us)-[:IMPLEMENTS]->(bc:BoundedContext)
OPTIONAL MATCH (f:Feature)-[:HAS_USER_STORY]->(us)
RETURN us.id AS id, us.role AS role, us.action AS action, us.benefit AS benefit,
       bc.id AS bcId, f.id AS featureId
ORDER BY us.id
"""

# Scope predicates injected into the WHERE clause (valid for any scope).
_SCOPE_BC = "(us)-[:IMPLEMENTS]->(:BoundedContext {id: $scopeId})"
_SCOPE_FEATURE = "(:Feature {id: $scopeId})-[:HAS_USER_STORY]->(us)"


@router.get("/user-stories/pending-design", response_model=PendingDesignResponse)
async def pending_design(
    request: Request, scopeType: str = "project", scopeId: str = "*"
) -> PendingDesignResponse:
    """설계가 아직 반영되지 않은 User Story 목록을 반환한다(범위 옵션)."""
    query = _PENDING_QUERY
    params: dict[str, Any] = {}
    if scopeId and scopeId != "*":
        predicate = None
        if scopeType == "bounded_context":
            predicate = _SCOPE_BC
        elif scopeType == "feature":
            predicate = _SCOPE_FEATURE
        if predicate:
            # Add the scope predicate to the existing WHERE (before OPTIONAL MATCH).
            query = query.replace(
                "OPTIONAL MATCH (us)-[:IMPLEMENTS]->(bc:BoundedContext)",
                f"  AND {predicate}\nOPTIONAL MATCH (us)-[:IMPLEMENTS]->(bc:BoundedContext)",
                1,
            )
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

