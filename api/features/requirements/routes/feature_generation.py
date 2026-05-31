"""Epic → Feature(spec.md) 자동 생성·확정 (034).

Epic 아래는 User Story를 바로 만들지 않고 **Feature부터** 만든다. 각 Feature = 하나의
speckit spec.md(US들 + edge cases + 핵심 가정). 생성은 deepagents 기반
`feature_spec_agent`(speckit-specify 방법론), 제안→확인(HITL) 후 영속.
"""

from __future__ import annotations

import asyncio
import json
import threading
import uuid

from fastapi import APIRouter, HTTPException
from sse_starlette.sse import EventSourceResponse
from starlette.requests import Request

from api.features.ingestion.event_storming.neo4j_client import get_neo4j_client
from api.features.requirements.requirements_contracts import (
    ConfirmFeaturesRequest,
    ConfirmFeaturesResponse,
    FeatureNodeDTO,
    GeneratedFeature,
    GenerateFeaturesResponse,
)
from api.features.requirements.spec_agent.feature_spec_agent import (
    generate_features_for_epic,
    stream_features_for_epic,
)
from api.platform.neo4j import get_session
from api.platform.observability.request_logging import http_context
from api.platform.observability.smart_logger import SmartLogger

router = APIRouter()


def _epic_context(bc_id: str):
    with get_session() as session:
        rec = session.run(
            "MATCH (bc:BoundedContext {id:$id}) RETURN coalesce(bc.displayName,bc.name) AS name, bc.description AS d",
            id=bc_id,
        ).single()
        if not rec:
            return None
        existing = [
            r["n"]
            for r in session.run(
                "MATCH (bc:BoundedContext {id:$id})-[:HAS_FEATURE]->(f:Feature) RETURN f.name AS n", id=bc_id
            )
        ]
        existing_reqs = [
            f"{r['role']}: {r['action']}"
            for r in session.run("MATCH (us:UserStory) RETURN us.role AS role, us.action AS action LIMIT 200")
            if r["action"]
        ]
    return rec["name"] or "", rec["d"] or "", existing, existing_reqs


@router.get("/epic/{bc_id}/generate-features/stream")
async def generate_features_stream(bc_id: str, request: Request):
    """Epic→Feature 생성을 deep agent 리즈닝과 함께 SSE로 스트리밍한다(034).

    progress 이벤트: {phase: start|reasoning|complete, message, features?}.
    """
    ctx = _epic_context(bc_id)
    if ctx is None:
        raise HTTPException(status_code=404, detail=f"Bounded context {bc_id} not found")
    bc_name, bc_desc, existing, existing_reqs = ctx

    loop = asyncio.get_event_loop()
    queue: asyncio.Queue = asyncio.Queue()

    def _worker():
        try:
            for ev in stream_features_for_epic(
                bc_name=bc_name, bc_description=bc_desc,
                existing_feature_names=existing, existing_requirements=existing_reqs,
            ):
                loop.call_soon_threadsafe(queue.put_nowait, ev)
        except Exception as exc:  # noqa: BLE001
            loop.call_soon_threadsafe(
                queue.put_nowait, {"phase": "complete", "message": f"오류: {exc}", "features": []}
            )
        finally:
            loop.call_soon_threadsafe(queue.put_nowait, None)

    threading.Thread(target=_worker, daemon=True).start()

    async def gen():
        while True:
            if await request.is_disconnected():
                break
            ev = await queue.get()
            if ev is None:
                break
            yield {"event": "progress", "data": json.dumps(ev, ensure_ascii=False)}
            if ev.get("phase") == "complete":
                break

    return EventSourceResponse(gen())


@router.post("/epic/{bc_id}/generate-features", response_model=GenerateFeaturesResponse)
async def generate_features(bc_id: str, request: Request) -> GenerateFeaturesResponse:
    """Epic을 Feature(각 = spec.md)들로 분해 제안한다(미확정). 각 Feature에 US+edge cases 포함."""
    with get_session() as session:
        rec = session.run(
            "MATCH (bc:BoundedContext {id:$id}) RETURN coalesce(bc.displayName,bc.name) AS name, bc.description AS d",
            id=bc_id,
        ).single()
        if not rec:
            raise HTTPException(status_code=404, detail=f"Bounded context {bc_id} not found")
        existing = [
            r["n"]
            for r in session.run(
                "MATCH (bc:BoundedContext {id:$id})-[:HAS_FEATURE]->(f:Feature) RETURN f.name AS n", id=bc_id
            )
        ]
        # 충돌·중복 검사용: 프로젝트 전체 요구사항(역할:행동) 일부.
        existing_reqs = [
            f"{r['role']}: {r['action']}"
            for r in session.run(
                "MATCH (us:UserStory) RETURN us.role AS role, us.action AS action LIMIT 200"
            )
            if r["action"]
        ]

    try:
        raw = generate_features_for_epic(
            bc_name=rec["name"] or "", bc_description=rec["d"] or "",
            existing_feature_names=existing, existing_requirements=existing_reqs,
        )
    except Exception as exc:  # noqa: BLE001 — degrade to empty (manual fallback)
        SmartLogger.log(
            "ERROR", "Feature generation failed.",
            category="requirements.feature.generate", params={"error": str(exc)},
        )
        raw = []

    features = [
        GeneratedFeature(
            name=f.get("name", ""), description=f.get("description", ""),
            edgeCases=[e for e in (f.get("edgeCases") or []) if e],
            assumptions=[a for a in (f.get("assumptions") or []) if a],
            conflicts=[c for c in (f.get("conflicts") or []) if c],
            userStories=[
                {
                    "role": s.get("role", ""), "action": s.get("action", ""),
                    "benefit": s.get("benefit", ""),
                    "acceptanceCriteria": [a for a in (s.get("acceptanceCriteria") or []) if a],
                }
                for s in (f.get("userStories") or [])
                if (s.get("action") or "").strip()
            ],
        )
        for f in raw
        if (f.get("name") or "").strip()
    ]
    SmartLogger.log(
        "INFO", f"Proposed {len(features)} features for epic {bc_id}.",
        category="requirements.feature.generate",
        params={**http_context(request), "bc_id": bc_id, "count": len(features)},
    )
    return GenerateFeaturesResponse(boundedContextId=bc_id, features=features)


@router.post("/features/confirm", response_model=ConfirmFeaturesResponse, status_code=201)
async def confirm_features(req: ConfirmFeaturesRequest, request: Request) -> ConfirmFeaturesResponse:
    """선택된 Feature들(+그 안의 US)을 영속. Feature 노드에 edge cases·가정 저장."""
    client = get_neo4j_client()
    with get_session() as session:
        bc = session.run(
            "MATCH (bc:BoundedContext {id:$id}) RETURN bc.key AS key", id=req.boundedContextId
        ).single()
    if not bc:
        raise HTTPException(status_code=404, detail=f"Bounded context {req.boundedContextId} not found")

    created: list[FeatureNodeDTO] = []
    for feat in req.features:
        if not (feat.name or "").strip():
            continue
        f = client.upsert_feature(
            bc_id=req.boundedContextId, bc_key=bc["key"], name=feat.name.strip(),
            description=feat.description or None, source="manual",
            edge_cases=list(feat.edgeCases or []), assumptions=list(feat.assumptions or []),
        )
        if not f:
            continue
        # 그 Feature 하위 User Story들 영속 + 링크
        for story in feat.userStories:
            if not (story.action or "").strip():
                continue
            us_id = str(uuid.uuid4())
            client.create_user_story(
                id=us_id, role=story.role or "사용자", action=story.action,
                benefit=story.benefit or "", priority="medium", status="draft",
                acceptance_criteria=list(story.acceptanceCriteria or []) or None,
            )
            client.link_user_story_to_bc(us_id, req.boundedContextId)
            client.link_user_story_to_feature(us_id, f["id"], source="manual")
        created.append(
            FeatureNodeDTO(
                id=f["id"], name=f["name"], description=f.get("description"),
                source=f.get("source") or "manual", boundedContextId=req.boundedContextId,
                edgeCases=list(f.get("edgeCases") or []), assumptions=list(f.get("assumptions") or []),
            )
        )

    SmartLogger.log(
        "INFO", f"Confirmed {len(created)} features under epic {req.boundedContextId}.",
        category="requirements.feature.confirm",
        params={**http_context(request), "bc_id": req.boundedContextId, "count": len(created)},
    )
    return ConfirmFeaturesResponse(created=created)
