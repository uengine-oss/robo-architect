from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from starlette.requests import Request

import json as _json

from api.features.requirement_changes.requirement_changes_contracts import EffectChangeType, EffectItem, ImpactLevel, RegressionAnalysis
from api.features.requirement_changes.services.effect_analyzer import run_effect_analysis
from api.features.requirement_changes.services.regression_analyzer import analyze_regression
from api.platform.neo4j import get_session
from api.platform.observability.request_logging import http_context
from api.platform.observability.smart_logger import SmartLogger

router = APIRouter()


def _parse_template(raw) -> dict | None:
    if not raw:
        return None
    if isinstance(raw, dict):
        return raw
    try:
        return _json.loads(raw)
    except Exception:
        return None


def _resolve_create_title(template: dict | None, node_label: str) -> str:
    if not template:
        return f"신규 {node_label}"
    if node_label == "UserStory":
        action = template.get("action", "")
        role = template.get("role", "")
        return f"{role}이 {action}" if role and action else action or f"신규 {node_label}"
    return template.get("name") or f"신규 {node_label}"


def _fetch_effects(change_id: str) -> list[EffectItem]:
    query = """
    MATCH (chg:RequirementChange {id: $id})-[e:EFFECT]->(t)
    RETURN t.id AS nodeId,
           CASE WHEN 'CreationIntent' IN labels(t)
                THEN t.nodeLabel
                ELSE labels(t)[0]
           END AS nodeLabel,
           CASE WHEN 'CreationIntent' IN labels(t)
                THEN t.templateData
                ELSE COALESCE(t.title, t.name, t.action, '')
           END AS nodeTitle,
           e.reason AS reason,
           e.impactLevel AS impactLevel,
           COALESCE(e.changeType, 'MODIFY') AS changeType,
           e.templateData AS templateData,
           e.appliedNodeId AS appliedNodeId
    """
    with get_session() as session:
        result = session.run(query, id=change_id)
        rows = result.data()

    items = []
    for r in rows:
        if not r["nodeId"]:
            continue
        change_type = EffectChangeType(r.get("changeType") or "MODIFY")
        template = _parse_template(r.get("templateData"))
        node_label = r["nodeLabel"] or ""
        if change_type == EffectChangeType.CREATE:
            node_title = _resolve_create_title(template, node_label)
        else:
            node_title = r["nodeTitle"] or ""
        items.append(EffectItem(
            nodeId=r["nodeId"] or "",
            nodeLabel=node_label,
            nodeTitle=node_title,
            reason=r["reason"] or "",
            impactLevel=ImpactLevel(r.get("impactLevel") or "LOW"),
            changeType=change_type,
            templateData=template,
            appliedNodeId=r.get("appliedNodeId"),
        ))
    return items


@router.get("/{change_id}/impact")
async def get_impact(change_id: str, request: Request):
    """EFFECT 관계 및 영향받는 노드 목록 반환."""
    effects = _fetch_effects(change_id)
    SmartLogger.log(
        "INFO",
        f"Impact fetched for {change_id}: {len(effects)} effects",
        category="requirement_changes.impact.fetch",
        params={**http_context(request), "changeId": change_id, "count": len(effects)},
    )
    return {"changeId": change_id, "effects": [e.model_dump() for e in effects]}


@router.post("/{change_id}/analyze-impact")
async def analyze_impact(change_id: str, request: Request):
    """robo-change-specify 스킬 호출 → EFFECT 생성. SSE 스트림."""

    # Change 존재 여부 확인
    with get_session() as session:
        result = session.run(
            "MATCH (n:RequirementChange {id: $id}) RETURN n.originalPrompt AS prompt",
            id=change_id,
        )
        record = result.single()
    if not record:
        raise HTTPException(status_code=404, detail=f"Change {change_id} not found")

    prompt = record["prompt"] or ""

    async def event_stream():
        yield f"data: {json.dumps({'phase': 'analyzing', 'message': 'robo-change-specify 스킬이 Stories/Processes/Design 영향도를 분석 중...'})}\n\n"
        try:
            result = await run_effect_analysis(change_id, prompt)
            effects = result.get("effects", []) if result else []
            # title 업데이트 (스킬이 추출한 제목)
            if result and result.get("title"):
                with get_session() as s:
                    s.run("MATCH (n:RequirementChange {id: $id}) SET n.title = $title",
                          id=change_id, title=result["title"])
            yield f"data: {json.dumps({'phase': 'done', 'effectCount': len(effects), 'effects': effects})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'phase': 'error', 'message': str(e)})}\n\n"

    SmartLogger.log(
        "INFO",
        f"analyze-impact started for {change_id}",
        category="requirement_changes.impact.analyze_start",
        params={**http_context(request), "changeId": change_id},
    )
    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.get("/{change_id}/regression", response_model=RegressionAnalysis)
async def get_regression(change_id: str, request: Request):
    """Change 적용 후 영향받는 테스트 목록 반환 (그래프 트래버설)."""
    with get_session() as session:
        result = session.run("MATCH (n:RequirementChange {id: $id}) RETURN n.id", id=change_id)
        if not result.single():
            raise HTTPException(status_code=404, detail=f"Change {change_id} not found")

    analysis = analyze_regression(change_id)
    SmartLogger.log(
        "INFO",
        f"Regression analysis: {change_id}, tests={len(analysis.regressionTests)}",
        category="requirement_changes.regression",
        params={**http_context(request), "changeId": change_id},
    )
    return analysis
