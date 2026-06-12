from __future__ import annotations

import json

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from starlette.requests import Request

from api.features.proposal_lifecycle.proposal_contracts import TestRunResult
from api.platform.neo4j import get_session
from api.platform.observability.smart_logger import SmartLogger

router = APIRouter()


@router.get("/stream/{proposal_id}/validate")
async def stream_validate_sse(proposal_id: str, request: Request):
    """
    검증 실행/재검증을 SSE로 스트리밍한다 (작업 분해·인텐트 분해와 동일 방식).
    헤드리스 일회 실행이 아니라 **runner(스트리밍)** 로 robo-sync 구조 검증 + GWT 인수
    조건을 실행하며 실행 로그(narration·tool 사용)를 실시간으로 흘려보낸다. 검증이 끝나면
    결과를 저장하고 TESTING→PENDING_ACCEPTANCE로 전환한다.

    **중지**: 클라이언트가 EventSource를 닫으면(disconnect) run_skill_lines가
    GeneratorExit/CancelledError로 종료되며 finally에서 claude 서브프로세스를 kill한다.
    상태는 TESTING으로 남아 언제든 재검증할 수 있다.
    """
    from api.features.proposal_lifecycle.services.test_runner import stream_validation

    async def event_stream():
        async for event_type, data in stream_validation(proposal_id):
            payload = json.dumps(data, ensure_ascii=False)
            yield f"event: {event_type}\ndata: {payload}\n\n"

    SmartLogger.log("INFO", f"SSE validation stream started: {proposal_id}",
                    category="proposal_lifecycle.validate.stream_start",
                    params={"proposalId": proposal_id})

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.post("/{proposal_id}/validate")
async def validate_proposal(proposal_id: str):
    """
    검증 실행/재검증(비스트리밍 폴백) — 백그라운드 실행 후 프런트가 test-results를 폴링.
    UI는 기본적으로 SSE 스트리밍(`/stream/{id}/validate`)을 사용한다.
    """
    from api.features.proposal_lifecycle.services.test_runner import reset_for_validation, run_tests

    err = reset_for_validation(proposal_id)
    if err:
        raise HTTPException(status_code=err[0], detail=err[1])

    import asyncio
    asyncio.create_task(run_tests(proposal_id))

    SmartLogger.log("INFO", f"Validation triggered: {proposal_id}",
                    category="proposal_lifecycle.validate.start",
                    params={"proposalId": proposal_id})
    return {"proposalId": proposal_id, "status": "VALIDATING"}


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
        raise HTTPException(status_code=404, detail=f"No test results for {proposal_id} yet")

    try:
        data = json.loads(raw) if isinstance(raw, str) else raw
        return TestRunResult(**data)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to parse test results: {e}")
