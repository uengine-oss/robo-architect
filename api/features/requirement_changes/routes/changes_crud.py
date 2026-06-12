from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from starlette.requests import Request

from api.features.requirement_changes.requirement_changes_contracts import (
    ChangeResponse,
    ChangeSourceType,
    ChangeStatus,
    CreateChangeRequest,
    EffectItem,
    ImpactLevel,
)
from api.features.requirement_changes.services.change_id_generator import next_change_id
from api.features.requirement_changes.services.effect_analyzer import (
    create_direct_effects,
    run_effect_analysis,
    extract_title_from_prompt,
)
from api.platform.neo4j import get_session
from api.platform.observability.request_logging import http_context
from api.platform.observability.smart_logger import SmartLogger

router = APIRouter()


@router.post("/", response_model=ChangeResponse, status_code=201)
async def create_change(body: CreateChangeRequest, request: Request):
    """
    Change 생성. DRAFT 상태로 시작.
    - title은 originalPrompt에서 자동 추출 (스킬이 나중에 더 정확한 제목으로 업데이트)
    - PROMPT/MANUAL 타입은 생성 즉시 robo-change-specify 스킬 비동기 실행
    """
    import asyncio

    change_id = next_change_id()
    author = getattr(getattr(request.state, "actor", None), "email", "anonymous")
    created_at = datetime.now(timezone.utc)

    # 제목 자동 추출 (프롬프트 첫 문장, 스킬이 완료 후 더 정확한 제목으로 업데이트됨)
    auto_title = extract_title_from_prompt(body.originalPrompt)

    query = """
    CREATE (n:RequirementChange {
        id: $id,
        title: $title,
        originalPrompt: $originalPrompt,
        author: $author,
        createdAt: datetime($createdAt),
        status: 'DRAFT',
        statusHistory: '[]',
        sourceType: $sourceType,
        changeSetId: null
    })
    RETURN n {.*} AS change
    """
    with get_session() as session:
        result = session.run(
            query,
            id=change_id,
            title=auto_title,
            originalPrompt=body.originalPrompt,
            author=author,
            createdAt=created_at.isoformat(),
            sourceType=body.sourceType.value,
        )
        record = result.single()

    if body.sourceType == ChangeSourceType.DIRECT_EDIT and body.directAffectedNodeIds:
        create_direct_effects(change_id, body.directAffectedNodeIds)
    else:
        # PROMPT / MANUAL 모두 즉시 스킬 분석 트리거 (fire-and-forget)
        async def _analyze():
            try:
                result = await run_effect_analysis(change_id, body.originalPrompt)
                # 스킬이 추출한 더 정확한 제목으로 업데이트
                if result and result.get("title"):
                    with get_session() as s:
                        s.run("MATCH (n:RequirementChange {id: $id}) SET n.title = $title",
                              id=change_id, title=result["title"])
            except Exception as e:
                SmartLogger.log("WARN", f"Async effect analysis failed for {change_id}: {e}",
                                category="requirement_changes.effect.async_error",
                                params={"changeId": change_id, "error": str(e)})

        asyncio.create_task(_analyze())

    SmartLogger.log(
        "INFO",
        f"Change created: {change_id} (analysis triggered async)",
        category="requirement_changes.create",
        params={**http_context(request), "changeId": change_id, "sourceType": body.sourceType.value},
    )

    return ChangeResponse.from_neo4j(record["change"], [])


def _parse_effects(raw_effects: list) -> list[EffectItem]:
    items = []
    for e in raw_effects:
        if e.get("nodeId") is None:
            continue
        items.append(
            EffectItem(
                nodeId=str(e["nodeId"]),
                nodeLabel=str(e.get("nodeLabel", "")),
                nodeTitle=str(e.get("nodeTitle", "")),
                reason=str(e.get("reason", "")),
                impactLevel=ImpactLevel(e.get("impactLevel", "LOW")),
            )
        )
    return items


@router.get("/", response_model=list[ChangeResponse])
async def list_changes(
    request: Request,
    status: Optional[str] = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
):
    """Change 목록 반환 (createdAt 역순)."""
    # 목록 쿼리: n {.*} projection으로 dict 반환 (get_change와 동일 패턴)
    if status:
        id_query = """
        MATCH (n:RequirementChange) WHERE n.status = $status
        RETURN n {.*} AS change ORDER BY n.createdAt DESC LIMIT $limit
        """
    else:
        id_query = """
        MATCH (n:RequirementChange)
        RETURN n {.*} AS change ORDER BY n.createdAt DESC LIMIT $limit
        """

    with get_session() as session:
        result = session.run(id_query, status=status, limit=limit)
        nodes = [r["change"] for r in result.data()]

    def _row_to_change(r: dict) -> ChangeResponse:
        return ChangeResponse.from_neo4j(r, [])

    SmartLogger.log(
        "INFO",
        f"Change list returned: {len(nodes)} records.",
        category="requirement_changes.list",
        params={**http_context(request), "count": len(nodes)},
    )

    return [
        _row_to_change(r)
        for r in nodes
    ]


@router.get("/{change_id}", response_model=ChangeResponse)
async def get_change(change_id: str, request: Request):
    """Change 단건 조회 (EFFECT 포함)."""
    query = """
    MATCH (n:RequirementChange {id: $id})
    OPTIONAL MATCH (n)-[e:EFFECT]->(t)
    RETURN n {.*} AS change,
           collect({
               nodeId: t.id,
               nodeLabel: labels(t)[0],
               nodeTitle: COALESCE(t.title, t.name, t.action, ''),
               reason: e.reason,
               impactLevel: e.impactLevel
           }) AS effects
    """
    with get_session() as session:
        result = session.run(query, id=change_id)
        record = result.single()

    if not record:
        raise HTTPException(status_code=404, detail=f"Change {change_id} not found")

    return ChangeResponse.from_neo4j(record["change"], _parse_effects(record["effects"]))


@router.delete("/{change_id}", status_code=204)
async def delete_change(change_id: str, request: Request):
    """Change 삭제. IMPLEMENTED 상태이면 409."""
    with get_session() as session:
        result = session.run(
            "MATCH (n:RequirementChange {id: $id}) RETURN n.status AS status",
            id=change_id,
        )
        record = result.single()

    if not record:
        raise HTTPException(status_code=404, detail=f"Change {change_id} not found")

    if record["status"] == ChangeStatus.IMPLEMENTED.value:
        raise HTTPException(
            status_code=409,
            detail=f"Change {change_id} is IMPLEMENTED and cannot be deleted.",
        )

    with get_session() as session:
        session.run("MATCH (n:RequirementChange {id: $id}) DETACH DELETE n", id=change_id)

    SmartLogger.log(
        "INFO",
        f"Change deleted: {change_id}",
        category="requirement_changes.delete",
        params={**http_context(request), "changeId": change_id},
    )


@router.get("/_debug")
async def debug_list():
    import traceback
    try:
        with get_session() as session:
            result = session.run("MATCH (n:RequirementChange) RETURN n {.*} AS change LIMIT 1")
            rows = result.data()
            if rows:
                row = rows[0]["change"]
                return {"ok": True, "keys": list(row.keys()), "createdAt_type": str(type(row.get("createdAt")))}
            return {"ok": True, "count": 0}
    except Exception as e:
        return {"error": str(e), "trace": traceback.format_exc()}
