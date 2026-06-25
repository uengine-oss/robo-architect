"""DDD 발견 마법사 라우트 (035 — US1/US4).

프로파일링→추천 단계→단계 진행(SSE)→propose→confirm. confirm은 신규 생성기 없이
기존 경로(BC 생성/속성 갱신, user-story 생성)에 위임한다. Code/설계 단계의 대규모
설계 생성은 기존 증분 설계(`POST /api/ingest/user-stories/design`)를 사용하도록 안내한다.
"""

from __future__ import annotations

import asyncio
import json
import uuid

from fastapi import APIRouter, HTTPException
from sse_starlette.sse import EventSourceResponse
from starlette.requests import Request

from api.features.ingestion.event_storming.neo4j_client import get_neo4j_client
from api.features.requirements.ddd_wizard import engine as wizard_engine
from api.features.requirements.ddd_wizard import wizard_session as store
from api.features.requirements.ddd_wizard.step_prompts import profile_summary, recommend_plan
from api.features.requirements.requirements_contracts import (
    WizardAnswerRequest,
    WizardConfirmRequest,
    WizardConfirmResponse,
    WizardProposal,
    WizardSessionDTO,
    WizardStartRequest,
    WizardStartResponse,
)
from api.platform.neo4j import get_session
from api.platform.observability.request_logging import http_context
from api.platform.observability.smart_logger import SmartLogger

router = APIRouter()


def _preflight_claude_ok() -> bool:
    import shutil

    return shutil.which("claude") is not None


@router.post("/ddd-wizard/start", response_model=WizardStartResponse)
async def start_wizard(req: WizardStartRequest, request: Request) -> WizardStartResponse:
    if req.scope == "epic" and not req.epicId:
        raise HTTPException(status_code=422, detail="scope='epic'이면 epicId가 필요합니다.")
    if req.engine == "claude-ide" and not _preflight_claude_ok():
        raise HTTPException(
            status_code=409,
            detail={
                "code": "local_tooling_unavailable",
                "message": "Claude IDE 엔진을 쓰려면 로컬 claude CLI가 필요합니다. "
                "설치 전까지는 in-process 엔진을 사용하세요.",
            },
        )
    plan = recommend_plan(req.profile, scope=req.scope)
    sess = store.create_session(
        scope=req.scope, epic_id=req.epicId, profile=req.profile, plan=plan, engine=req.engine
    )
    sess.phase = "step_running"
    SmartLogger.log(
        "INFO", "DDD wizard started.",
        category="requirements.ddd_wizard.start",
        params={**http_context(request), "session_id": sess.session_id, "scope": req.scope},
    )
    return WizardStartResponse(
        sessionId=sess.session_id,
        recommendedPlan=plan,
        profileSummary=profile_summary(req.profile, scope=req.scope),
    )


@router.get("/ddd-wizard/{session_id}", response_model=WizardSessionDTO)
async def get_wizard(session_id: str) -> WizardSessionDTO:
    sess = store.get_session(session_id)
    if not sess:
        raise HTTPException(status_code=404, detail="wizard session not found")
    return sess.to_dto()


@router.post("/ddd-wizard/{session_id}/answer", response_model=WizardProposal)
async def answer_wizard(
    session_id: str, req: WizardAnswerRequest, request: Request
) -> WizardProposal:
    """답변/문서 제출 → 단계 산출물·그래프 변경안 생성(동기)."""
    sess = store.get_session(session_id)
    if not sess:
        raise HTTPException(status_code=404, detail="wizard session not found")
    sess.record_answer(req.stepKey, req.answers, req.pastedDocument)
    proposal = wizard_engine.generate_step(
        req.stepKey, req.answers, req.pastedDocument, engine=sess.engine
    )
    sess.record_proposal(proposal)
    return proposal


@router.get("/ddd-wizard/{session_id}/step/{step_key}/stream")
async def stream_wizard_step(session_id: str, step_key: str, request: Request):
    """단계 진행 SSE — 추론 안내 후 산출물 제안을 송출(Constitution III)."""
    sess = store.get_session(session_id)
    if not sess:
        raise HTTPException(status_code=404, detail="wizard session not found")

    async def gen():
        yield {"event": "step_started", "data": json.dumps({"stepKey": step_key})}
        yield {"event": "reasoning", "data": json.dumps({"message": f"'{step_key}' 단계 산출물 생성 중..."})}
        answers = sess.answers.get(step_key, {})
        document = sess.documents.get(step_key)
        proposal = await asyncio.to_thread(
            wizard_engine.generate_step, step_key, answers, document, engine=sess.engine
        )
        sess.record_proposal(proposal)
        yield {"event": "proposal", "data": proposal.model_dump_json()}
        yield {"event": "done", "data": json.dumps({"stepKey": step_key})}

    return EventSourceResponse(gen())


@router.post("/ddd-wizard/{session_id}/step/{step_key}/confirm", response_model=WizardConfirmResponse)
async def confirm_wizard_step(
    session_id: str, step_key: str, req: WizardConfirmRequest, request: Request
) -> WizardConfirmResponse:
    """수락된 그래프 변경안을 기존 경로로 적용(propose→confirm). 빈 목록=무변경."""
    sess = store.get_session(session_id)
    if not sess:
        raise HTTPException(status_code=404, detail="wizard session not found")
    proposal = sess.proposals.get(step_key)
    if proposal is None:
        raise HTTPException(status_code=409, detail="이 단계의 제안이 아직 없습니다.")

    accepted = {
        c.changeId: c for c in proposal.graphChanges if c.changeId in set(req.acceptedChangeIds)
    }
    applied: list[str] = []
    errors: list[str] = []
    deferred: list[str] = []
    client = get_neo4j_client()

    for change_id, change in accepted.items():
        try:
            # Strategize는 분류(BoundedContext 수정)만 의미 있음 — LLM이 라벨을
            # Aggregate/Command/Event로 잘못 내보내 노드를 오염시키는 것 방지.
            if step_key == "strategize" and change.targetType != "BoundedContext":
                deferred.append(
                    f"{change.targetType} '{change.after.get('name','?')}': Strategize 단계에선 "
                    "분류(BC 수정)만 반영 — 무시"
                )
                continue
            if change.targetType == "BoundedContext" and change.action == "create":
                name = (change.after.get("name") or "").strip()
                if not name:
                    raise ValueError("BoundedContext name 누락")
                client.create_bounded_context(name=name, description=change.after.get("description"))
                applied.append(change_id)
            elif change.targetType == "BoundedContext" and change.action == "update":
                # targetId가 없으면 after에서 BC id/이름으로 해석. BC 자체 수정이므로
                # after.name/displayName도 BC 이름 후보로 매칭(Strategize 분류 등).
                bc_id = change.targetId or _resolve_bc_id(change.after) or _bc_id_by_name(
                    change.after.get("name") or change.after.get("displayName")
                )
                if not bc_id:
                    nm = change.after.get("name") or change.after.get("displayName") or "?"
                    deferred.append(f"BoundedContext '{nm}' 수정: 대상 BC를 찾지 못해 보류")
                    continue
                _apply_bc_update(bc_id, change.after)
                applied.append(change_id)
            elif change.targetType == "UserStory" and change.action == "create":
                us_id = str(uuid.uuid4())
                client.create_user_story(
                    id=us_id,
                    role=change.after.get("role") or "사용자",
                    action=change.after.get("action") or change.after.get("name") or "",
                    benefit=change.after.get("benefit") or "",
                    priority="medium",
                    status="draft",
                )
                bc_id = _resolve_bc_id(change.after)
                if bc_id:
                    client.link_user_story_to_bc(us_id, bc_id)
                applied.append(change_id)
            elif change.targetType == "Feature" and change.action == "create":
                name = (change.after.get("name") or "").strip()
                bc_id = _resolve_bc_id(change.after)
                if not name:
                    raise ValueError("Feature name 누락")
                if not bc_id:
                    deferred.append(f"Feature '{name}': 소속 BoundedContext가 아직 없어 보류(문서에 기록)")
                    continue
                with get_session() as session:
                    rec = session.run(
                        "MATCH (bc:BoundedContext {id:$id}) RETURN bc.key AS key", id=bc_id
                    ).single()
                client.upsert_feature(
                    bc_id=bc_id, bc_key=(rec or {}).get("key") or "",
                    name=name, description=change.after.get("description"), source="ddd-wizard",
                )
                applied.append(change_id)
            elif change.targetType == "Aggregate" and change.action == "create":
                name = (change.after.get("name") or "").strip()
                bc_id = _resolve_bc_id(change.after)
                if not name:
                    raise ValueError("Aggregate name 누락")
                if not bc_id:
                    deferred.append(f"Aggregate '{name}': 소속 BoundedContext가 아직 없어 보류(문서에 기록)")
                    continue
                client.create_aggregate(name=name, bc_id=bc_id)
                applied.append(change_id)
            elif change.targetType == "Event" and change.action == "create":
                # Event는 Command→Aggregate→BC 체인이 필수. BC가 아직 없으면
                # (예: Discover 단계가 Decompose보다 먼저) 에러가 아니라 보류한다.
                # 애그리거트명 미지정 시 BC 대표 애그리거트(BC명)로 기본 연결.
                evt_name = (change.after.get("name") or "").strip()
                if not evt_name:
                    raise ValueError("Event name 누락")
                bc_id = _resolve_bc_id(change.after)
                if not bc_id:
                    deferred.append(
                        f"Event '{evt_name}': 소속 BoundedContext/Aggregate가 아직 없어 보류"
                        "(BC·애그리거트 정의 후 반영)"
                    )
                    continue
                agg_name = (change.after.get("aggregateName") or "").strip()
                if not agg_name:
                    with get_session() as session:
                        rec = session.run(
                            "MATCH (bc:BoundedContext {id:$id}) RETURN bc.name AS name", id=bc_id
                        ).single()
                    agg_name = (rec or {}).get("name") or evt_name
                agg = client.create_aggregate(name=agg_name, bc_id=bc_id)
                cmd_name = (change.after.get("commandName") or "").strip() or f"{evt_name} 처리"
                cmd = client.create_command(name=cmd_name, aggregate_id=agg["id"])
                client.create_event(
                    name=evt_name, command_id=cmd["id"],
                    description=change.after.get("description"),
                )
                applied.append(change_id)
            elif change.targetType == "Command" and change.action == "create":
                # Command는 Aggregate→BC 체인 필수. BC 없으면 보류, 애그리거트명
                # 미지정 시 BC 대표 애그리거트로 기본 연결.
                cmd_name = (change.after.get("name") or "").strip()
                if not cmd_name:
                    raise ValueError("Command name 누락")
                bc_id = _resolve_bc_id(change.after)
                if not bc_id:
                    deferred.append(
                        f"Command '{cmd_name}': 소속 BoundedContext/Aggregate가 아직 없어 보류"
                    )
                    continue
                agg_name = (change.after.get("aggregateName") or "").strip()
                if not agg_name:
                    with get_session() as session:
                        rec = session.run(
                            "MATCH (bc:BoundedContext {id:$id}) RETURN bc.name AS name", id=bc_id
                        ).single()
                    agg_name = (rec or {}).get("name") or cmd_name
                agg = client.create_aggregate(name=agg_name, bc_id=bc_id)
                client.create_command(
                    name=cmd_name, aggregate_id=agg["id"],
                    description=change.after.get("description"),
                )
                applied.append(change_id)
            else:
                errors.append(f"{change_id}: 미지원 변경({change.targetType}/{change.action})")
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{change_id}: {exc}")

    sess.mark_confirmed(step_key)
    SmartLogger.log(
        "INFO", "DDD wizard step confirmed.",
        category="requirements.ddd_wizard.confirm",
        params={**http_context(request), "session_id": session_id, "step": step_key,
                "applied": len(applied), "errors": len(errors), "deferred": len(deferred)},
    )
    return WizardConfirmResponse(appliedChanges=applied, errors=errors, deferred=deferred)


def _bc_id_by_name(name: str | None) -> str | None:
    """BC를 name 또는 displayName으로 찾아 id 반환."""
    name = (name or "").strip()
    if not name:
        return None
    with get_session() as session:
        rec = session.run(
            "MATCH (bc:BoundedContext) WHERE bc.name = $n OR bc.displayName = $n "
            "RETURN bc.id AS id LIMIT 1",
            n=name,
        ).single()
    return rec["id"] if rec else None


def _resolve_bc_id(after: dict) -> str | None:
    """변경안 after에서 BoundedContext id를 얻는다. id가 없으면 이름으로 매칭."""
    bc_id = (after.get("boundedContextId") or "").strip()
    if bc_id:
        return bc_id
    return _bc_id_by_name(after.get("boundedContextName") or after.get("boundedContext"))


def _apply_bc_update(bc_id: str, after: dict) -> None:
    """BC 속성만 SET(관계 보존) — 캔버스 속성 포함."""
    # 주의: name/displayName은 의도적으로 제외 — BC update(Strategize 분류·Define
    # 캔버스)가 LLM의 after.name(라벨)으로 BC 이름을 덮어쓰는 오염 방지. 이름 변경은
    # 전용 PATCH(bounded_context_crud)로만.
    allowed = {"purpose", "description", "domainRoles", "ubiquitousLanguage",
               "businessDecisions", "assumptions", "classification", "domainType"}
    after = dict(after)
    # 전략 분류(Core/Supporting/Generic)는 앱이 두 필드를 따로 읽는 불일치가 있다:
    # canvas/contexts는 `classification`, aggregates/viewer 등은 `domainType`.
    # LLM이 둘 중 무엇으로 주든 **둘 다** 동일 값으로 세팅해 어디서든 보이게 한다.
    cls = after.get("classification") or after.get("domainType")
    if cls:
        after["classification"] = cls
        after["domainType"] = cls
    sets = ["bc.version = coalesce(bc.version, 0) + 1"]
    params: dict = {"id": bc_id}
    for k, v in after.items():
        if k in allowed:
            sets.append(f"bc.{k} = ${k}")
            params[k] = v
    if len(sets) == 1:
        return
    with get_session() as session:
        session.run(f"MATCH (bc:BoundedContext {{id:$id}}) SET {', '.join(sets)}", **params)
