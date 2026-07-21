"""spec 053 — typed 검색/상세 provenance와 대형 결과 fallback 회귀."""
from __future__ import annotations

import json

from api.platform.legacy_tool_events import encode_event, is_event
from api.features.proposal_lifecycle.services.legacy_provenance import (
    ProvenanceCollector,
    _extract_saved_path,
)


def _request(tool_id: str, kind: str, tool_input: dict) -> str:
    name = f"mcp__robo-cluster__{'cluster_retrieve' if kind == 'search' else 'node_detail'}"
    return encode_event(
        phase="request", kind=kind, tool_use_id=tool_id, tool_name=name, tool_input=tool_input,
    )


def _result(tool_id: str, kind: str, payload: str) -> str:
    name = f"mcp__robo-cluster__{'cluster_retrieve' if kind == 'search' else 'node_detail'}"
    return encode_event(
        phase="result", kind=kind, tool_use_id=tool_id, tool_name=name, content=payload,
    )


def _search_payload(n_nodes: int = 2) -> str:
    nodes = [{
        "id": f"code:x.c:fn{i}", "name": f"fn{i}", "label": "FUNCTION",
        "summary": "요약", "relevance": 0.9,
        "rules": [{"statement": "부족 시 거절", "examples": [{"given": "g"}]}],
    } for i in range(n_nodes)]
    return json.dumps({"clusters": [{"score": 0.9, "nodes": nodes}]}, ensure_ascii=False)


def _detail_payload(node_id: str = "code:x.c:fn0") -> str:
    return json.dumps({"node": {
        "id": node_id, "name": "fn0", "labels": ["FUNCTION", "EMBEDDED"],
        "properties": {"summary": "상세 요약", "logical_name": "상세 기능"},
        "source": {"available": True, "file_path": "x.c", "start_line": 10,
                   "end_line": 20, "code_text": "int fn0(){}"},
        "columns": [], "rules": [], "relationships": [],
    }}, ensure_ascii=False)


def _mcp_envelope(payload: str) -> str:
    """실제 Claude stream-json tool_result의 MCP text 형상."""
    return json.dumps({"result": payload}, ensure_ascii=False, separators=(",", ":"))


def test_typed_search_and_detail_roundtrip():
    collector = ProvenanceCollector()
    request = _request("s1", "search", {"query": "배송 조회", "database": "neo4j"})
    assert is_event(request)
    assert collector.feed(request) is None
    search = collector.feed(_result("s1", "search", _search_payload(3)))
    assert search["kind"] == "search"
    assert search["entry"]["query"] == "배송 조회"
    assert search["entry"]["database"] == "neo4j"
    assert len(search["entry"]["searchedNodes"]) == 3
    assert search["entry"]["searchedNodes"][0]["rulesCount"] == 1

    assert collector.feed(_request("d1", "detail", {"node_id": "code:x.c:fn0"})) is None
    detail = collector.feed(_result("d1", "detail", _detail_payload()))
    assert detail["kind"] == "detail"
    inspection = detail["inspection"]
    assert inspection["ok"] is True
    assert inspection["nodeId"] == "code:x.c:fn0"
    assert inspection["source"]["start_line"] == 10
    assert len(collector.entries[0]["inspections"]) == 1


def test_inline_mcp_result_envelope_is_unwrapped_for_search_and_detail():
    collector = ProvenanceCollector()
    collector.feed(_request("s1", "search", {"query": "배송 조회"}))
    search = collector.feed(_result("s1", "search", _mcp_envelope(_search_payload(2))))
    assert len(search["entry"]["searchedNodes"]) == 2

    collector.feed(_request("d1", "detail", {"node_id": "code:x.c:fn0"}))
    detail = collector.feed(_result("d1", "detail", _mcp_envelope(_detail_payload())))
    assert detail["inspection"]["ok"] is True
    assert detail["inspection"]["source"]["start_line"] == 10


def test_double_wrapped_mcp_envelope_is_unwrapped_to_fixpoint():
    """evlink P0 실측 회귀: PRO-005 의 실패 rawHead 가 `{"result":"{\\"node\\":…` —
    1회 unwrap 후에도 envelope 인 이중 포장이 실스트림에 존재한다. 고정점까지 벗겨야 한다."""
    collector = ProvenanceCollector()
    collector.feed(_request("d1", "detail", {"node_id": "code:x.c:fn0"}))
    double = _mcp_envelope(_mcp_envelope(_detail_payload()))
    detail = collector.feed(_result("d1", "detail", double))
    assert detail["inspection"]["ok"] is True
    assert detail["inspection"]["source"]["start_line"] == 10

    collector.feed(_request("s1", "search", {"query": "배송"}))
    search = collector.feed(_result("s1", "search", _mcp_envelope(_mcp_envelope(_search_payload(2)))))
    assert len(search["entry"]["searchedNodes"]) == 2


def test_oversized_file_fallback_with_double_wrapped_file_content(tmp_path):
    """파일 fallback 경로에서도 파일 내용이 이중 envelope 일 수 있다 — 동일 고정점 계약."""
    saved = tmp_path / "toolu_dbl.txt"
    saved.write_text(_mcp_envelope(_mcp_envelope(_search_payload(4))), encoding="utf-8")
    collector = ProvenanceCollector()
    collector.feed(_request("s", "search", {"query": "q"}))
    notice = f"<persisted-output>Output too large. Full output saved to: {saved}</persisted-output>"
    entry = collector.feed(_result("s", "search", notice))["entry"]
    assert len(entry["searchedNodes"]) == 4


def test_interleaved_tool_ids_pair_with_their_own_inputs():
    collector = ProvenanceCollector()
    collector.feed(_request("s1", "search", {"query": "첫 검색"}))
    collector.feed(_request("s2", "search", {"query": "둘째 검색"}))
    second = collector.feed(_result("s2", "search", _search_payload(2)))
    first = collector.feed(_result("s1", "search", _search_payload(1)))
    assert second["entry"]["query"] == "둘째 검색"
    assert first["entry"]["query"] == "첫 검색"
    assert [len(entry["searchedNodes"]) for entry in collector.entries] == [2, 1]


def test_detail_failure_is_recorded_not_counted_as_success():
    collector = ProvenanceCollector()
    collector.feed(_request("s", "search", {"query": "q"}))
    collector.feed(_result("s", "search", _search_payload(1)))
    collector.feed(_request("d", "detail", {"node_id": "missing"}))
    event = collector.feed(_result("d", "detail", json.dumps({
        "error": {"code": "NODE_NOT_FOUND", "message": "node not found"}
    })))
    assert event["inspection"]["ok"] is False
    assert event["inspection"]["error"]["code"] == "NODE_NOT_FOUND"


def test_oversized_file_fallback_reads_full_search_payload(tmp_path):
    saved = tmp_path / "toolu_full.txt"
    saved.write_text(json.dumps({"result": _search_payload(5)}, ensure_ascii=False), encoding="utf-8")
    collector = ProvenanceCollector()
    collector.feed(_request("s", "search", {"query": "q"}))
    notice = f"<persisted-output>Output too large. Full output saved to: {saved}</persisted-output>"
    entry = collector.feed(_result("s", "search", notice))["entry"]
    assert len(entry["searchedNodes"]) == 5


def test_unparseable_result_keeps_audit_head():
    collector = ProvenanceCollector()
    collector.feed(_request("s", "search", {"query": "q"}))
    entry = collector.feed(_result("s", "search", "완전히 이상한 텍스트 {깨진"))["entry"]
    assert entry["searchedNodes"] == []
    assert entry["rawHead"].startswith("완전히")


def test_inspection_without_source_is_safe():
    """source 를 안 주는 노드(예: 코드 미보유 아티팩트) — 죽지 않고 빈 source 로 기록."""
    collector = ProvenanceCollector()
    collector.feed(_request("d", "detail", {"node_id": "art:x"}))
    payload = json.dumps({"node": {"id": "art:x", "name": "x", "labels": ["ARTIFACT"],
                                   "properties": {}, "columns": []}}, ensure_ascii=False)
    inspection = collector.feed(_result("d", "detail", payload))["inspection"]
    assert inspection["ok"] is True
    assert inspection["source"] == {}


def test_oversized_code_text_is_truncated_with_marker():
    """임의 프로젝트의 초대형 함수 — 저장 상한(20k)으로 절단 + 명시 플래그."""
    big = "x" * 50_000
    collector = ProvenanceCollector()
    collector.feed(_request("d", "detail", {"node_id": "code:big"}))
    payload = json.dumps({"node": {
        "id": "code:big", "name": "big", "labels": ["FUNCTION"], "properties": {},
        "source": {"available": True, "file_path": "a.c", "start_line": 1,
                   "end_line": 999, "code_text": big}, "columns": [],
    }}, ensure_ascii=False)
    inspection = collector.feed(_result("d", "detail", payload))["inspection"]
    assert inspection["source"]["code_text_truncated"] is True
    assert len(inspection["source"]["code_text"]) < 21_000
    assert inspection["source"]["code_text"].endswith("(truncated)")


def test_save_skips_when_no_entries():
    ProvenanceCollector().save("PRO-X", "INTENT")


def test_extract_saved_path_observed_formats(tmp_path):
    saved = tmp_path / "toolu_glued.txt"
    saved.write_text(_search_payload(2), encoding="utf-8")
    variants = (
        f"Error: result exceeds tokens. Output has been saved to {saved}. Use the Read tool",
        f"<persisted-output>Full output saved to: {saved}</persisted-output>",
        f"Output has been saved to {saved}.Format: JSON with schema: {{result: string}}",
        f"Full output saved to: {saved}Use the Read tool to access the full output.",
    )
    for notice in variants:
        assert _extract_saved_path(notice) == str(saved)
