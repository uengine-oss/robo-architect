"""Epic → Feature(spec.md) 자동 생성·확정 (034).

Epic 아래는 User Story를 바로 만들지 않고 **Feature부터** 만든다. 각 Feature = 하나의
speckit spec.md(US들 + edge cases + 핵심 가정). 생성은 deepagents 기반
`feature_spec_agent`(speckit-specify 방법론), 제안→확인(HITL) 후 영속.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException
from starlette.requests import Request

from api.features.ingestion.event_storming.neo4j_client import get_neo4j_client
from api.features.requirements.requirements_contracts import (
    ConfirmFeaturesRequest,
    ConfirmFeaturesResponse,
    FeatureNodeDTO,
    GeneratedFeature,
    GenerateFeaturesResponse,
)
from api.features.requirements.spec_agent.feature_spec_agent import generate_features_for_epic
from api.platform.neo4j import get_session
from api.platform.observability.request_logging import http_context
from api.platform.observability.smart_logger import SmartLogger

router = APIRouter()


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

    try:
        raw = generate_features_for_epic(
            bc_name=rec["name"] or "", bc_description=rec["d"] or "", existing_feature_names=existing
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
            userStories=[
                s for s in (f.get("userStories") or []) if (s.get("action") or "").strip()
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
