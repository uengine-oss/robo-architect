"""056 — Proposal 초안 스토리보드 API.

GET  /api/proposals/{id}/storyboard?scenes=0|1  현재 스토리보드(경량/전체)
POST /api/proposals/{id}/storyboard?force=0|1   (재)생성 시작 — 백그라운드
PUT  /api/proposals/{id}/storyboard/steps/{step_id}  편집된 sceneGraph 저장
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from starlette.requests import Request

from api.features.proposal_lifecycle.services import storyboard_runner
from api.platform.observability.smart_logger import SmartLogger

router = APIRouter()


class StoryboardStepUpdate(BaseModel):
    sceneGraph: dict[str, Any]


@router.get("/{proposal_id}/storyboard")
async def get_storyboard(proposal_id: str, scenes: int = Query(1)) -> dict[str, Any]:
    sb = storyboard_runner.load_storyboard(proposal_id)
    if sb is None:
        # Proposal 자체가 없거나 아직 생성 전
        from api.platform.neo4j import get_session

        with get_session() as session:
            exists = session.run("MATCH (p:Proposal {id: $id}) RETURN count(p) AS c", id=proposal_id).single()["c"]
        if not exists:
            raise HTTPException(status_code=404, detail="proposal not found")
        return {"status": "none", "running": storyboard_runner.is_running(proposal_id), "journeys": []}
    out = sb if scenes else storyboard_runner.strip_scenes(sb)
    out["running"] = storyboard_runner.is_running(proposal_id)
    return out


@router.post("/{proposal_id}/storyboard")
async def generate_storyboard(proposal_id: str, request: Request, force: int = Query(0)) -> dict[str, Any]:
    row = storyboard_runner._load_proposal(proposal_id)
    if row is None:
        raise HTTPException(status_code=404, detail="proposal not found")
    started = storyboard_runner.schedule_storyboard(proposal_id, force=bool(force))
    SmartLogger.log("INFO", f"storyboard requested {proposal_id} force={force}",
                    category="proposal_lifecycle.storyboard.request",
                    params={"proposalId": proposal_id, "force": bool(force)})
    return {"started": started, "running": storyboard_runner.is_running(proposal_id)}


@router.put("/{proposal_id}/storyboard/steps/{step_id}")
async def update_storyboard_step(proposal_id: str, step_id: str, body: StoryboardStepUpdate) -> dict[str, Any]:
    sb = storyboard_runner.update_step_scene(proposal_id, step_id, body.sceneGraph)
    if sb is None:
        raise HTTPException(status_code=404, detail="storyboard step not found")
    return storyboard_runner.strip_scenes(sb)
