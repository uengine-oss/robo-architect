"""lite L-4 — Intent 분해가 연결과 떨어져 돌고, 다시 붙으면 처음부터 다시 받는다."""

from __future__ import annotations

import asyncio

import pytest

from api.features.proposal_lifecycle.services import detached_runs


@pytest.fixture(autouse=True)
def _clean_runs():
    detached_runs._RUNS.clear()
    yield
    for run in detached_runs._RUNS.values():
        run.task.cancel()
    detached_runs._RUNS.clear()


def _work(gate: asyncio.Event, calls: list[int]):
    async def gen():
        calls.append(1)
        yield "phase", {"message": "분해 중"}
        yield "log_line", {"text": "첫 줄"}
        await gate.wait()
        yield "log_line", {"text": "둘째 줄"}
        yield "done", {"status": "DRAFT"}
    return gen


@pytest.mark.asyncio
async def test_disconnect_does_not_stop_work_and_reattach_replays():
    gate, calls = asyncio.Event(), []
    run = detached_runs.start_or_join("intent:p1", _work(gate, calls))

    # 첫 화면: 두 이벤트를 받고 연결이 끊긴다(생성기 닫힘)
    first = run.follow()
    got = [await first.__anext__(), await first.__anext__()]
    assert [e for e, _ in got] == ["phase", "log_line"]
    await first.aclose()

    gate.set()
    await asyncio.sleep(0.01)
    assert run.finished and not run.cancelled, "연결이 끊겨도 작업은 끝까지 돈다"

    # 돌아온 화면: 처음부터 끝(done)까지 다시 받는다
    again = [e async for e, _ in detached_runs.get_run("intent:p1").follow()]
    assert again == ["phase", "log_line", "log_line", "done"]
    assert calls == [1], "다시 붙어도 작업은 한 번만 돈다"


@pytest.mark.asyncio
async def test_start_while_running_joins_instead_of_restarting():
    gate, calls = asyncio.Event(), []
    a = detached_runs.start_or_join("intent:p2", _work(gate, calls))
    b = detached_runs.start_or_join("intent:p2", _work(gate, calls))
    assert a is b
    gate.set()
    await asyncio.wait_for(a.task, 1)
    assert calls == [1]

    # 끝난 뒤에 다시 시작하면(재생성) 새 작업이다
    gate2 = asyncio.Event()
    gate2.set()
    c = detached_runs.start_or_join("intent:p2", _work(gate2, calls))
    assert c is not a
    await asyncio.wait_for(c.task, 1)
    assert calls == [1, 1]


@pytest.mark.asyncio
async def test_live_follower_gets_events_as_they_come():
    gate, calls = asyncio.Event(), []
    run = detached_runs.start_or_join("intent:p3", _work(gate, calls))

    async def collect():
        return [e async for e, _ in run.follow()]

    task = asyncio.create_task(collect())
    await asyncio.sleep(0.01)
    assert not task.done()
    gate.set()
    assert await asyncio.wait_for(task, 1) == ["phase", "log_line", "log_line", "done"]


@pytest.mark.asyncio
async def test_cancel_stops_work_and_reports_error():
    gate, calls = asyncio.Event(), []
    run = detached_runs.start_or_join("intent:p4", _work(gate, calls))
    await asyncio.sleep(0.01)
    assert detached_runs.cancel("intent:p4") is True
    await asyncio.wait_for(run.task, 1)  # 취소는 error 이벤트로 바뀌고 task 는 조용히 끝난다
    events = [e async for e, _ in run.follow()]
    assert events[-1] == "error" and run.cancelled
    assert detached_runs.cancel("intent:p4") is False


@pytest.mark.asyncio
async def test_failure_becomes_error_event():
    async def boom():
        yield "phase", {}
        raise RuntimeError("LLM 429")

    run = detached_runs.start_or_join("intent:p5", boom)
    events = [(e, d) async for e, d in run.follow()]
    assert events[-1][0] == "error" and "429" in events[-1][1]["message"]


@pytest.mark.asyncio
async def test_attach_route_does_not_start_work(monkeypatch):
    from fastapi import FastAPI
    from httpx import ASGITransport, AsyncClient

    from api.features.proposal_lifecycle.routes import proposals_intent

    started = []

    async def fake_stream(pid):
        started.append(pid)
        yield "done", {"proposalId": pid}

    monkeypatch.setattr(proposals_intent, "stream_intent", fake_stream)
    app = FastAPI()
    app.include_router(proposals_intent.router)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as client:
        r = await client.get("/stream/p6/intent?attach=true")
        assert "event: idle" in r.text and started == []
        s = await client.get("/stream/p6/intent/status")
        assert s.json()["running"] is False

        r = await client.get("/stream/p6/intent")
        assert "event: done" in r.text and started == ["p6"]
        r = await client.get("/stream/p6/intent?attach=true")
        assert "event: done" in r.text and started == ["p6"], "끝난 분해에 붙으면 결과만 다시 받는다"


@pytest.mark.asyncio
async def test_clarify_answer_reruns_once_and_stream_joins(monkeypatch):
    """명확화에 답하면 분해를 한 번만 다시 돌린다 — 이어 여는 스트림은 그 작업에 붙는다."""
    from contextlib import contextmanager

    from fastapi import FastAPI
    from httpx import ASGITransport, AsyncClient

    from api.features.proposal_lifecycle.routes import proposals_crud, proposals_intent

    started: list[str] = []
    gate = asyncio.Event()

    async def fake_stream(pid):
        started.append(pid)
        yield "phase", {"message": "다시 분해"}
        await gate.wait()
        yield "done", {"proposalId": pid}

    class _Session:
        def run(self, *a, **k):
            return None

    @contextmanager
    def _session():
        yield _Session()

    monkeypatch.setattr(proposals_intent, "stream_intent", fake_stream)
    monkeypatch.setattr("api.features.proposal_lifecycle.services.intent_runner.stream_intent", fake_stream)
    monkeypatch.setattr(proposals_crud, "get_session", _session)
    monkeypatch.setattr(proposals_crud, "_get_proposal_row", lambda pid: {"id": pid, "clarificationLog": "[]"})
    monkeypatch.setattr(proposals_crud.ProposalResponse, "from_neo4j", classmethod(lambda cls, row, _: {"id": row["id"]}))

    from api.features.proposal_lifecycle.proposal_contracts import AnswerClarificationRequest

    body = AnswerClarificationRequest(answers=[{"questionIndex": 0, "answer": "월 2회"}])
    assert (await proposals_crud.answer_clarification("p7", body, None)) == {"id": "p7"}
    await asyncio.sleep(0.01)

    app = FastAPI()
    app.include_router(proposals_intent.router)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as client:
        assert started == ["p7"], "답하면 분해가 detached 로 한 번 돈다"
        gate.set()
        r = await client.get("/stream/p7/intent")
        assert "event: done" in r.text
        assert started == ["p7"], "이어 여는 스트림은 새로 시작하지 않고 붙는다"
