from __future__ import annotations

import json

from fastapi import APIRouter, HTTPException, Query, Response
from fastapi.responses import StreamingResponse
from starlette.requests import Request

from api.features.proposal_lifecycle.proposal_contracts import TestRunResult
from api.platform.neo4j import get_session
from api.platform.observability.smart_logger import SmartLogger

router = APIRouter()


@router.get("/stream/{proposal_id}/validate")
async def stream_validate_sse(proposal_id: str, request: Request,
                              scenarioIds: list[str] | None = Query(None)):
    """
    검증 실행/재검증을 SSE로 스트리밍한다 (작업 분해·인텐트 분해와 동일 방식).
    헤드리스 일회 실행이 아니라 **runner(스트리밍)** 로 robo-sync 구조 검증 + GWT 인수
    조건을 실행하며 실행 로그(narration·tool 사용)를 실시간으로 흘려보낸다. 검증이 끝나면
    결과를 저장하고 TESTING→PENDING_ACCEPTANCE로 전환한다.

    **중지**: 클라이언트가 EventSource를 닫으면(disconnect) run_skill_lines가
    GeneratorExit/CancelledError로 종료되며 finally에서 claude 서브프로세스를 kill한다.
    상태는 TESTING으로 남아 언제든 재검증할 수 있다.

    **부분 재검증**(D-2 ⑭): `?scenarioIds=SC-003,SC-007` 이면 그 항목만 다시 재고 기존
    testResults 에 병합한다(덮지 않는다). `results` 이벤트는 병합된 전체 결과다.
    """
    from api.features.proposal_lifecycle.services.test_runner import parse_scenario_ids, stream_validation

    ids = parse_scenario_ids(scenarioIds)

    async def event_stream():
        async for event_type, data in stream_validation(proposal_id, ids or None):
            payload = json.dumps(data, ensure_ascii=False)
            yield f"event: {event_type}\ndata: {payload}\n\n"

    SmartLogger.log("INFO", f"SSE validation stream started: {proposal_id}",
                    category="proposal_lifecycle.validate.stream_start",
                    params={"proposalId": proposal_id, "scenarioIds": ids})

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.post("/{proposal_id}/validate")
async def validate_proposal(proposal_id: str, scenarioIds: list[str] | None = Query(None)):
    """
    검증 실행/재검증(비스트리밍 폴백) — 백그라운드 실행 후 프런트가 test-results를 폴링.
    UI는 기본적으로 SSE 스트리밍(`/stream/{id}/validate`)을 사용한다.

    `?scenarioIds=SC-003,SC-007`(쉼표 또는 반복) 이면 **부분 재검증** — 그 항목만 다시 재고
    결과는 기존 testResults 에 병합한다. 전체 결과가 없으면 409, 없는 id 면 400.
    """
    import asyncio

    from api.features.proposal_lifecycle.services.test_runner import (
        parse_scenario_ids, prepare_partial_validation, reset_for_validation, run_tests,
    )

    ids = parse_scenario_ids(scenarioIds)
    if ids:
        err, existing, targets = prepare_partial_validation(proposal_id, ids)
        if err:
            raise HTTPException(status_code=err[0], detail=err[1])
        asyncio.create_task(run_tests(proposal_id, ids, (existing, targets)))
    else:
        err = reset_for_validation(proposal_id)
        if err:
            raise HTTPException(status_code=err[0], detail=err[1])
        asyncio.create_task(run_tests(proposal_id))

    SmartLogger.log("INFO", f"Validation triggered: {proposal_id}",
                    category="proposal_lifecycle.validate.start",
                    params={"proposalId": proposal_id, "scenarioIds": ids})
    return {"proposalId": proposal_id, "status": "VALIDATING", "scenarioIds": ids}


@router.get("/{proposal_id}/sandbox-head")
async def get_sandbox_head(proposal_id: str):
    """샌드박스 worktree 의 HEAD 커밋 — 「고치고 다시 검증」 루프가 **커밋을 감지**하는 신호.

    셀에 "고친 뒤 커밋해라" 를 주입한 뒤 프런트가 이 값을 폴링해, 바뀌면 그 항목만
    부분 재검증한다. worktree 가 없거나 git 이 실패하면 head=None.
    """
    import subprocess
    from pathlib import Path

    with get_session() as session:
        record = session.run(
            "MATCH (p:Proposal {id: $id}) RETURN p.sandboxWorktreePath AS path",
            id=proposal_id,
        ).single()
    if not record:
        raise HTTPException(status_code=404, detail=f"Proposal {proposal_id} not found")

    path = record.get("path")
    head = None
    if path and Path(path).is_dir():
        try:
            out = subprocess.run(
                ["git", "rev-parse", "HEAD"], cwd=str(path),
                capture_output=True, text=True, timeout=10,
            )
            if out.returncode == 0:
                head = out.stdout.strip() or None
        except Exception:
            head = None
    return {"proposalId": proposal_id, "head": head}


@router.get("/{proposal_id}/test-results", response_model=TestRunResult)
async def get_test_results(proposal_id: str, request: Request):
    """자동 테스트 결과를 반환한다."""
    with get_session() as session:
        result = session.run(
            "MATCH (p:Proposal {id: $id}) RETURN p.testResults AS testResults, p.status AS status",
            id=proposal_id,
        )
        record = result.single()

    if not record:
        raise HTTPException(status_code=404, detail=f"Proposal {proposal_id} not found")

    raw = record.get("testResults")
    if not raw:
        # "아직 없음" 은 오류가 아니라 정상 대기 상태다. 404 로 표현하면 프런트가
        # 검증이 끝날 때까지 폴링하는 동안 콘솔에 오류가 쌓여 실패처럼 보인다.
        # 204(No Content)로 응답해 "요청은 유효하고 결과가 아직 없다"를 구분한다.
        return Response(status_code=204)

    try:
        data = json.loads(raw) if isinstance(raw, str) else raw
        # I11: 요약 총계(totalScenarios/passed/failed/skipped)를 items 로부터 재계산해
        # 항목 목록과 항상 일치시킨다(저장 시점 집계가 items 와 어긋나는 경우 방지).
        items = data.get("items") or []
        if items:
            counts: dict[str, int] = {}
            for it in items:
                r = str((it or {}).get("result") or "").upper()
                counts[r] = counts.get(r, 0) + 1
            data["totalScenarios"] = len(items)
            data["passed"] = counts.get("PASS", 0)
            data["failed"] = counts.get("FAIL", 0)
            data["skipped"] = counts.get("SKIP", 0) + counts.get("SKIPPED", 0)
        return TestRunResult(**data)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to parse test results: {e}")
