from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException
from starlette.requests import Request

from api.features.requirement_changes.requirement_changes_contracts import (
    ChangeResponse,
    ChangeSetResponse,
    ChangeStatus,
    CreateChangeSetRequest,
    EffectItem,
    ImpactLevel,
)
from api.features.requirement_changes.services.change_id_generator import next_changeset_id
from api.platform.neo4j import get_session
from api.platform.observability.request_logging import http_context
from api.platform.observability.smart_logger import SmartLogger

router = APIRouter()


def _parse_effects_from_rows(rows: list[dict]) -> list[EffectItem]:
    return [
        EffectItem(
            nodeId=str(r["nodeId"]),
            nodeLabel=str(r.get("nodeLabel", "")),
            nodeTitle=str(r.get("nodeTitle", "")),
            reason=str(r.get("reason", "")),
            impactLevel=ImpactLevel(r.get("impactLevel") or "LOW"),
        )
        for r in rows
        if r.get("nodeId")
    ]


@router.post("/changesets/", status_code=201)
async def create_changeset(body: CreateChangeSetRequest, request: Request):
    """ChangeSet 생성 및 Change 포함."""
    cs_id = next_changeset_id()
    author = getattr(getattr(request.state, "actor", None), "email", "anonymous")
    created_at = datetime.now(timezone.utc)

    create_query = """
    CREATE (cs:ChangeSet {
        id: $id,
        title: $title,
        author: $author,
        createdAt: datetime($createdAt),
        status: 'DRAFT'
    })
    WITH cs
    UNWIND $changeIds AS cid
    MATCH (chg:RequirementChange {id: cid})
    CREATE (cs)-[:CONTAINS]->(chg)
    SET chg.changeSetId = cs.id
    RETURN cs {.*} AS cs
    """
    with get_session() as session:
        result = session.run(
            create_query,
            id=cs_id,
            title=body.title,
            author=author,
            createdAt=created_at.isoformat(),
            changeIds=body.changeIds,
        )
        record = result.single()

    SmartLogger.log(
        "INFO",
        f"ChangeSet created: {cs_id}",
        category="requirement_changes.changeset.create",
        params={**http_context(request), "changeSetId": cs_id},
    )
    return {"id": cs_id, "title": body.title, "author": author, "createdAt": created_at.isoformat(), "status": "DRAFT"}


@router.get("/changesets/{cs_id}")
async def get_changeset(cs_id: str, request: Request):
    """ChangeSet 상세 (포함된 Change 목록 포함)."""
    query = """
    MATCH (cs:ChangeSet {id: $id})
    OPTIONAL MATCH (cs)-[:CONTAINS]->(chg:RequirementChange)
    OPTIONAL MATCH (chg)-[e:EFFECT]->(t)
    RETURN cs {.*} AS cs,
           collect(DISTINCT chg {.*}) AS changes
    """
    with get_session() as session:
        result = session.run(query, id=cs_id)
        record = result.single()

    if not record:
        raise HTTPException(status_code=404, detail=f"ChangeSet {cs_id} not found")

    changes = [ChangeResponse.from_neo4j(c, []) for c in record["changes"] if c]
    cs = record["cs"]
    return {
        "id": cs["id"],
        "title": cs["title"],
        "author": cs.get("author", ""),
        "createdAt": cs["createdAt"],
        "status": cs["status"],
        "changes": [c.model_dump() for c in changes],
    }


@router.post("/changesets/{cs_id}/submit")
async def submit_changeset(cs_id: str, request: Request):
    """ChangeSet 포함 모든 Change를 SUBMITTED로 전환."""
    _transition_changeset_changes(cs_id, "DRAFT", "SUBMITTED",
                                  getattr(getattr(request.state, "actor", None), "email", "anonymous"))
    return {"changeSetId": cs_id, "status": "SUBMITTED"}


@router.post("/changesets/{cs_id}/approve")
async def approve_changeset(cs_id: str, request: Request):
    """ChangeSet 전체 APPROVED. 자기 승인 방지."""
    actor = getattr(getattr(request.state, "actor", None), "email", "anonymous")
    with get_session() as session:
        result = session.run(
            "MATCH (cs:ChangeSet {id: $id})-[:CONTAINS]->(chg) RETURN chg.author AS author LIMIT 1",
            id=cs_id,
        )
        row = result.single()
    if row and row["author"] == actor:
        raise HTTPException(status_code=403, detail="자기 승인은 불가합니다.")
    _transition_changeset_changes(cs_id, "SUBMITTED", "APPROVED", actor)
    return {"changeSetId": cs_id, "status": "APPROVED"}


@router.post("/changesets/{cs_id}/reject")
async def reject_changeset(cs_id: str, request: Request):
    """ChangeSet 전체 REJECTED."""
    actor = getattr(getattr(request.state, "actor", None), "email", "anonymous")
    if actor:
        with get_session() as session:
            result = session.run(
                "MATCH (cs:ChangeSet {id: $id})-[:CONTAINS]->(chg) RETURN chg.author AS author LIMIT 1",
                id=cs_id,
            )
            row = result.single()
        if row and row["author"] == actor:
            raise HTTPException(status_code=403, detail="자기 반려는 불가합니다.")
    _transition_changeset_changes(cs_id, "SUBMITTED", "REJECTED", actor)
    return {"changeSetId": cs_id, "status": "REJECTED"}


@router.delete("/changesets/{cs_id}/changes/{change_id}", status_code=204)
async def remove_from_changeset(cs_id: str, change_id: str):
    """Change를 ChangeSet에서 제거 (Change 노드는 유지)."""
    with get_session() as session:
        session.run(
            """
            MATCH (cs:ChangeSet {id: $cs_id})-[r:CONTAINS]->(chg:RequirementChange {id: $chg_id})
            DELETE r
            SET chg.changeSetId = null
            """,
            cs_id=cs_id,
            chg_id=change_id,
        )


def _transition_changeset_changes(cs_id: str, from_status: str, to_status: str, actor: str) -> None:
    import json
    from datetime import datetime, timezone

    query = """
    MATCH (cs:ChangeSet {id: $cs_id})-[:CONTAINS]->(chg:RequirementChange)
    WHERE chg.status = $from_status
    WITH chg
    SET chg.status = $to_status
    WITH chg,
         apoc.convert.fromJsonList(COALESCE(chg.statusHistory, '[]')) AS hist
    SET chg.statusHistory = apoc.convert.toJson(
        hist + [{fromStatus: $from_status, toStatus: $to_status, at: datetime(), actor: $actor}]
    )
    """
    # APOC 없으면 Python에서 직접 처리
    try:
        with get_session() as session:
            session.run(query, cs_id=cs_id, from_status=from_status, to_status=to_status, actor=actor)
    except Exception:
        _python_transition_changeset(cs_id, from_status, to_status, actor)


def _python_transition_changeset(cs_id: str, from_status: str, to_status: str, actor: str) -> None:
    import json
    from datetime import datetime, timezone

    with get_session() as session:
        result = session.run(
            "MATCH (cs:ChangeSet {id: $id})-[:CONTAINS]->(chg) WHERE chg.status = $s RETURN chg.id AS id, chg.statusHistory AS hist",
            id=cs_id,
            s=from_status,
        )
        rows = result.data()

    for row in rows:
        try:
            hist = json.loads(row["hist"] or "[]")
        except Exception:
            hist = []
        hist.append({
            "fromStatus": from_status,
            "toStatus": to_status,
            "at": datetime.now(timezone.utc).isoformat(),
            "actor": actor,
            "comment": None,
        })
        with get_session() as session:
            session.run(
                "MATCH (n:RequirementChange {id: $id}) SET n.status = $s, n.statusHistory = $hist",
                id=row["id"],
                s=to_status,
                hist=json.dumps(hist),
            )
