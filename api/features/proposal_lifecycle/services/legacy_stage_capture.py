"""모든 Proposal LLM stage가 공유하는 레거시 provenance stream adapter."""
from __future__ import annotations

from typing import AsyncGenerator

from api.platform.legacy_tool_events import decode_event, is_event
from api.platform.skill_runner import run_skill_lines
from api.features.proposal_lifecycle.services.legacy_provenance import ProvenanceCollector


def _result_events(result: dict) -> list[tuple[str, object]]:
    if result["kind"] == "search":
        entry = result["entry"]
        count = len(entry["searchedNodes"])
        rules = sum(node["rulesCount"] for node in entry["searchedNodes"])
        return [
            ("legacy_ref", entry),
            ("log_line", {"text": f"   → 레거시 후보 {count}개 · 규칙 {rules}개 검색됨 ⛓"}),
        ]
    inspection = result["inspection"]
    if inspection["ok"]:
        source = inspection.get("source") or {}
        lines = ""
        if source.get("available"):
            lines = f" ({source.get('start_line')}~{source.get('end_line')}줄)"
        message = f"   → {inspection.get('name') or inspection['nodeId']} 상세 검토됨{lines}"
    else:
        message = (
            f"   → {inspection['nodeId']} 상세 조회 실패: "
            f"{inspection.get('error', {}).get('code', 'DETAIL_FAILED')}"
        )
    return [("legacy_detail", inspection), ("log_line", {"text": message})]


async def stream_stage_skill_lines(
    proposal_id: str,
    stage: str,
    skill_root: str,
    skill_name: str,
    human_prompt: str,
    **runner_kwargs,
) -> AsyncGenerator[tuple[str, object], None]:
    """일반 line과 provenance SSE event를 함께 흘리고 완료된 호출을 stage에 저장한다."""
    collector = ProvenanceCollector()
    try:
        async for line in run_skill_lines(
            skill_root, skill_name, human_prompt, **runner_kwargs,
        ):
            if not is_event(line):
                yield "line", line
                continue
            event = decode_event(line)
            result = collector.feed(line)
            if event["phase"] == "request":
                tool_input = event.get("input") or {}
                if event["kind"] == "search":
                    query = str(tool_input.get("query") or "").strip()
                    if query:
                        yield "log_line", {"text": f"🔍 레거시 그래프 검색: \"{query}\""}
                else:
                    node_id = str(tool_input.get("node_id") or "").strip()
                    if node_id:
                        yield "log_line", {"text": f"📄 레거시 노드 상세 조회: {node_id}"}
                continue
            if result is not None:
                for output in _result_events(result):
                    yield output
    finally:
        collector.save(proposal_id, stage)
