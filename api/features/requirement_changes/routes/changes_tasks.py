from __future__ import annotations

import json
import os

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from starlette.requests import Request

from api.features.requirement_changes.requirement_changes_contracts import (
    ChangeStatus,
    ImplementChangeRequest,
    ImplementationPreflight,
    PendingChange,
)
from api.features.requirement_changes.services.change_tasks_parser import parse_tasks_stream
from api.features.requirement_changes.services.skill_runner import run_skill_lines
from api.platform.neo4j import get_session
from api.platform.observability.request_logging import http_context
from api.platform.observability.smart_logger import SmartLogger

router = APIRouter()

_PROJECT_PATH = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
)


@router.get("/{change_id}/preflight", response_model=ImplementationPreflight)
async def preflight(change_id: str):
    """구현 시작 전 미반영 선행 APPROVED Change 목록 반환."""
    with get_session() as session:
        result = session.run(
            "MATCH (n:RequirementChange {id: $id}) RETURN n.createdAt AS createdAt",
            id=change_id,
        )
        record = result.single()
    if not record:
        raise HTTPException(status_code=404, detail=f"Change {change_id} not found")

    current_created_at = record["createdAt"]

    prior_query = """
    MATCH (n:RequirementChange)
    WHERE n.id <> $id
      AND n.status = 'APPROVED'
      AND n.createdAt < $createdAt
    RETURN n {.*} AS n
    ORDER BY n.createdAt ASC
    """
    with get_session() as session:
        result = session.run(prior_query, id=change_id, createdAt=current_created_at)
        prior_rows = result.data()

    def _neo4j_dt_to_iso(val) -> str:
        if val is None:
            return datetime.now(timezone.utc).isoformat()
        try:
            return val.isoformat()
        except Exception:
            return str(val)

    pending = [
        PendingChange(
            id=r["n"]["id"],
            title=r["n"].get("title", ""),
            createdAt=_neo4j_dt_to_iso(r["n"].get("createdAt")),
            status=ChangeStatus(r["n"]["status"]),
        )
        for r in prior_rows
    ]

    return ImplementationPreflight(
        changeId=change_id,
        pendingPriorChanges=pending,
        canProceed=True,
    )


@router.post("/{change_id}/implement")
async def implement_change(change_id: str, body: ImplementChangeRequest, request: Request):
    """APPROVED → IMPLEMENTED. robo-change-tasks 스킬 PTY 호출 → SSE."""
    with get_session() as session:
        result = session.run(
            "MATCH (n:RequirementChange {id: $id}) RETURN n.status AS status",
            id=change_id,
        )
        record = result.single()
    if not record:
        raise HTTPException(status_code=404, detail=f"Change {change_id} not found")
    if record["status"] != ChangeStatus.APPROVED.value:
        raise HTTPException(status_code=400, detail=f"Change must be APPROVED to implement (current: {record['status']})")

    async def event_stream():
        # 선행 Change 먼저 처리
        for prior_id in (body.includePriorChangeIds or []):
            async for event in _run_single_implement(prior_id):
                yield event

        # 현재 Change 처리
        async for event in _run_single_implement(change_id):
            yield event

    SmartLogger.log(
        "INFO",
        f"Implementation started: {change_id}",
        category="requirement_changes.implement.start",
        params={**http_context(request), "changeId": change_id},
    )
    return StreamingResponse(event_stream(), media_type="text/event-stream")


def _fetch_change_effects(change_id: str) -> dict:
    """Neo4j에서 Change와 EFFECT 노드를 조회해 구현 컨텍스트를 반환한다."""
    query = """
    MATCH (chg:RequirementChange {id: $id})
    OPTIONAL MATCH (chg)-[e:EFFECT]->(n)
    RETURN chg.title AS title,
           chg.originalPrompt AS originalPrompt,
           collect({
               nodeId: n.id,
               nodeLabel: labels(n)[0],
               nodeTitle: COALESCE(n.title, n.name, n.action, ''),
               reason: e.reason,
               impactLevel: e.impactLevel
           }) AS effects
    """
    from api.platform.neo4j import get_session
    with get_session() as session:
        result = session.run(query, id=change_id)
        record = result.single()
    if not record:
        return {"title": "", "originalPrompt": "", "effects": []}
    effects = [e for e in record["effects"] if e.get("nodeId")]
    return {
        "title": record["title"] or "",
        "originalPrompt": record["originalPrompt"] or "",
        "effects": effects,
    }


def _build_implement_prompt(change_id: str, ctx: dict) -> str:
    """구현 스킬에 전달할 human prompt를 구성한다."""
    effects_text = "\n".join(
        f"- [{e['impactLevel']}] {e['nodeLabel']}: {e['nodeTitle'] or e['nodeId']}\n"
        f"  이유: {e['reason']}"
        for e in ctx["effects"]
    ) or "(영향받는 노드 없음)"

    return (
        f"Change ID: {change_id}\n"
        f"제목: {ctx['title']}\n"
        f"원본 요구사항: {ctx['originalPrompt']}\n\n"
        f"영향받는 노드 목록:\n{effects_text}\n\n"
        f"프로젝트 루트: {_PROJECT_PATH}\n\n"
        "위 내용을 바탕으로 구현 프로토콜에 따라 태스크를 계획하고 실행하세요."
    )


async def _run_single_implement(change_id: str):
    """단일 Change 구현 스킬 실행 → SSE 이벤트 generator."""
    try:
        ctx = _fetch_change_effects(change_id)
        human_prompt = _build_implement_prompt(change_id, ctx)

        lines_gen = run_skill_lines(
            "robo-change-tasks",
            args={},
            human_prompt=human_prompt,
            add_dirs=[_PROJECT_PATH],
        )
        async for event in parse_tasks_stream(change_id, lines_gen):
            yield event

        # 완료 시 상태 IMPLEMENTED로 전환
        import json
        from datetime import datetime, timezone
        from api.features.requirement_changes.routes.changes_approval import _get_change_row, _append_status_history

        row = _get_change_row(change_id)
        if row and row.get("status") == "APPROVED":
            _append_status_history(change_id, "APPROVED", "IMPLEMENTED", "system", None)
            SmartLogger.log(
                "INFO",
                f"Change implemented: {change_id}",
                category="requirement_changes.implement.done",
                params={"changeId": change_id},
            )

    except Exception as e:
        yield f"data: {json.dumps({'phase': 'error', 'message': str(e), 'changeId': change_id})}\n\n"
