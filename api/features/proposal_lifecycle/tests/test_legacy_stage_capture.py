"""spec 053 — 모든 proposal stage가 공유하는 provenance stream 경계 검증."""
from __future__ import annotations

import asyncio
import json
from pathlib import Path

from api.platform.legacy_tool_events import encode_event
from api.features.proposal_lifecycle.services import legacy_stage_capture


ROOT = Path(__file__).resolve().parents[4]


def _event(phase: str, kind: str, tool_id: str, *, tool_input=None, content=None) -> str:
    tool = "cluster_retrieve" if kind == "search" else "node_detail"
    return encode_event(
        phase=phase,
        kind=kind,
        tool_use_id=tool_id,
        tool_name=f"mcp__robo-cluster__{tool}",
        tool_input=tool_input,
        content=content,
    )


def _collect(generator) -> list[tuple[str, object]]:
    async def consume():
        return [item async for item in generator]

    return asyncio.run(consume())


def test_shared_stage_adapter_streams_search_detail_and_saves(monkeypatch):
    search_payload = json.dumps({"clusters": [{"nodes": [{
        "id": "code:x.c:f", "name": "f", "label": "FUNCTION",
        "rules": [{"statement": "r"}],
    }]}]})
    detail_payload = json.dumps({"node": {
        "id": "code:x.c:f", "name": "f", "labels": ["FUNCTION"],
        "properties": {}, "source": {"available": True, "file_path": "x.c",
        "start_line": 3, "end_line": 7, "code_text": "void f(){}"},
        "columns": [], "rules": [], "relationships": [],
    }})

    async def fake_run(*_args, **_kwargs):
        yield "일반 출력"
        yield _event("request", "search", "s1", tool_input={"query": "주문"})
        yield _event("request", "detail", "d1", tool_input={"node_id": "code:x.c:f"})
        yield _event("result", "search", "s1", content=search_payload)
        yield _event("result", "detail", "d1", content=detail_payload)

    saved = []
    monkeypatch.setattr(legacy_stage_capture, "run_skill_lines", fake_run)
    monkeypatch.setattr(
        legacy_stage_capture.ProvenanceCollector,
        "save",
        lambda self, proposal_id, stage: saved.append((proposal_id, stage, self.entries)),
    )

    events = _collect(legacy_stage_capture.stream_stage_skill_lines(
        "PRO-1", "PLAN", "skills", "proposal-plan", "계획 생성",
    ))

    assert events[0] == ("line", "일반 출력")
    assert [kind for kind, _ in events].count("legacy_ref") == 1
    assert [kind for kind, _ in events].count("legacy_detail") == 1
    assert saved[0][0:2] == ("PRO-1", "PLAN")
    assert saved[0][2][0]["query"] == "주문"
    assert saved[0][2][0]["inspections"][0]["source"]["start_line"] == 3


def test_shared_stage_adapter_saves_on_runner_failure(monkeypatch):
    async def failing_run(*_args, **_kwargs):
        yield _event("request", "search", "s1", tool_input={"query": "주문"})
        raise RuntimeError("runner failed")

    saved = []
    monkeypatch.setattr(legacy_stage_capture, "run_skill_lines", failing_run)
    monkeypatch.setattr(
        legacy_stage_capture.ProvenanceCollector,
        "save",
        lambda self, proposal_id, stage: saved.append((proposal_id, stage, self.entries)),
    )

    async def consume():
        async for _ in legacy_stage_capture.stream_stage_skill_lines(
            "PRO-2", "DDD", "skills", "proposal-discover", "상세 설계",
        ):
            pass

    try:
        asyncio.run(consume())
        raise AssertionError("runner failure must propagate")
    except RuntimeError as exc:
        assert str(exc) == "runner failed"
    assert saved == [("PRO-2", "DDD", [])]


def test_intent_plan_and_discover_require_shared_list_detail_completion_gate():
    reference = (ROOT / "skills/robo-proposals/robo-proposal-intent/references/legacy-reference.md")
    contract = reference.read_text(encoding="utf-8")
    assert "cluster_retrieve` 시도 1회 이상이 없으면 완료가 아니다" in contract
    assert "`node_detail` 성공 1회 이상" in contract

    for skill in (
        "robo-proposal-intent",
        "robo-proposal-plan",
        "robo-proposal-discover",
    ):
        text = (ROOT / f"skills/robo-proposals/{skill}/SKILL.md").read_text(encoding="utf-8")
        assert "호출 완료 게이트" in text, skill


def test_intent_contract_requires_legacy_read_and_is_strategic_only():
    text = (ROOT / "skills/robo-proposals/robo-proposal-intent/SKILL.md").read_text(
        encoding="utf-8"
    )
    assert "legacy-reference.md`를 Read 도구로 반드시 직접 읽어라" in text
    assert "strategic-output-schema.md" in text
    assert "tacticalDiff" not in text
    for tactical_term in ("Aggregate 추출", "Command/Event", "ReadModel", "Policy"):
        assert tactical_term not in text
