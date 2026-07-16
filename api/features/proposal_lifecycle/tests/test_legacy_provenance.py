"""legacy_provenance 단위테스트 (spec 052) — 마커 파싱·초대형 파일폴백·경로추출 회귀 방지.

실측 기반: CLI 초대형-결과 안내문은 최소 두 포맷으로 온다(둘 다 실제 관측):
  A) "Error: result (...) exceeds maximum allowed tokens. Output has been saved to <p>. Use ..."
  B) "<persisted-output>Output too large (90.8KB). Full output saved to: <p></persisted-output>"
포맷 A 만 처리하던 조건이 B 를 놓쳐 nodes=0 침묵이 났다 — 그 재발을 여기서 막는다.
"""
from __future__ import annotations

import json

from api.features.proposal_lifecycle.services.legacy_provenance import (
    MARK_QUERY,
    MARK_RESULT,
    ProvenanceCollector,
    _extract_saved_path,
    is_marker,
)


def _result_payload(n_nodes: int = 2) -> str:
    nodes = [{
        "id": f"code:x.c:fn{i}", "name": f"fn{i}", "label": "FUNCTION",
        "summary": "요약", "relevance": 0.9,
        "rules": [{"statement": "부족 시 거절", "examples": [{"given": "g"}]}],
    } for i in range(n_nodes)]
    return json.dumps({"clusters": [{"score": 0.9, "nodes": nodes}]}, ensure_ascii=False)


def test_extract_saved_path_format_a():
    t = ("Error: result (78,139 characters across 2,315 lines) exceeds maximum allowed "
         "tokens. Output has been saved to C:\\Users\\u\\.claude\\p\\abc.txt. Use the Read tool")
    assert _extract_saved_path(t) == "C:\\Users\\u\\.claude\\p\\abc.txt"


def test_extract_saved_path_format_b_persisted_output():
    t = ("<persisted-output>Output too large (90.8KB). Full output saved to: "
         "C:\\Users\\u\\.claude\\projects\\x\\tool-results\\toolu_01HK.txt</persisted-output>")
    assert _extract_saved_path(t) == "C:\\Users\\u\\.claude\\projects\\x\\tool-results\\toolu_01HK.txt"


def test_marker_roundtrip_and_compact():
    c = ProvenanceCollector()
    assert is_marker(MARK_QUERY + "{}") and is_marker(MARK_RESULT + "{}")
    assert c.feed(MARK_QUERY + json.dumps({"query": "배송 조회", "database": "neo4j"})) is None
    entry = c.feed(MARK_RESULT + _result_payload(3))
    assert entry is not None
    assert entry["query"] == "배송 조회"
    assert entry["database"] == "neo4j"
    assert len(entry["nodes"]) == 3
    assert entry["nodes"][0]["rulesCount"] == 1
    assert "raw_head" not in entry           # 성공 경로엔 원문 조각 미저장(노이즈 금지)


def test_oversized_file_fallback_reads_full_payload(tmp_path):
    saved = tmp_path / "toolu_full.txt"
    saved.write_text(_result_payload(5), encoding="utf-8")
    c = ProvenanceCollector()
    c.feed(MARK_QUERY + json.dumps({"query": "q"}))
    notice = (f"<persisted-output>Output too large (90.8KB). "
              f"Full output saved to: {saved}</persisted-output>")
    entry = c.feed(MARK_RESULT + notice)
    assert entry is not None
    assert len(entry["nodes"]) == 5          # ★전량 반영(사용자 원칙) — 파일에서 복원됨


def test_unparseable_keeps_raw_head_for_audit():
    c = ProvenanceCollector()
    c.feed(MARK_QUERY + json.dumps({"query": "q"}))
    entry = c.feed(MARK_RESULT + "완전히 이상한 텍스트 {깨진")
    assert entry["nodes"] == []
    assert entry["raw_head"].startswith("완전히")   # 조용한 0 금지 — 감사 단서 보존


def test_save_skips_when_no_entries():
    # 검색 0회면 저장 자체를 안 한다(빈 스테이지 노이즈 금지) — DB 호출이 없어야 한다.
    c = ProvenanceCollector()
    c.save("PRO-X", "INTENT")   # get_session 을 부르면 즉시 예외났을 것(연결 없음 가정 환경)


def test_extract_saved_path_format_c_flattened_schema_notice():
    # 실측 3번째 포맷(2026-07-16 PRO-004): 경로 뒤에 "Format: JSON with schema..." 산문이
    # 이어지고, 마커 평탄화로 개행이 사라진 한 줄 상태.
    t = ("Error: result (137,505 characters) exceeds maximum allowed tokens. Output has "
         "been saved to C:\\Users\\u\\.claude\\projects\\x\\tool-results\\mcp-robo-cluster-"
         "cluster_retrieve-1784177048726.txt.Format: JSON with schema: {result: string}"
         "- For targeted queries (find a value, filter by field): use jq on the file directly.")
    assert _extract_saved_path(t) == ("C:\\Users\\u\\.claude\\projects\\x\\tool-results\\"
                                      "mcp-robo-cluster-cluster_retrieve-1784177048726.txt")


def test_oversized_fallback_unwraps_result_envelope(tmp_path):
    # 실측: CLI 저장 파일은 {"result": "<도구 텍스트>"} 한 겹 포장 — 언랩 후 전량 복원.
    saved = tmp_path / "toolu_env.txt"
    saved.write_text(json.dumps({"result": _result_payload(4)}, ensure_ascii=False),
                     encoding="utf-8")
    c = ProvenanceCollector()
    c.feed(MARK_QUERY + json.dumps({"query": "q"}))
    notice = (f"Error: result (137,505 characters) exceeds maximum allowed tokens. "
              f"Output has been saved to {saved}.Format: JSON with schema: {{result: string}}")
    entry = c.feed(MARK_RESULT + notice)
    assert entry is not None
    assert len(entry["nodes"]) == 4          # ★포장 벗기고 전량 반영
    assert "raw_head" not in entry


def test_extract_saved_path_flattened_glued_use_notice(tmp_path):
    # 실측 4번째(2026-07-16 라이브 PRO-001/002): persisted-output 안내문에서 마커 평탄화가
    # 경로와 다음 문장 사이 개행을 지워 공백 없이 붙는다(".txtUse the Read tool...").
    # 문자 경계로는 파일명 연속과 구분 불가 → 확장자 경계 후보를 실존 검사로 확정하는 회귀.
    saved = tmp_path / "toolu_glued.txt"
    saved.write_text(_result_payload(2), encoding="utf-8")
    notice = (f"<persisted-output>Output too large (103.8KB). Full output saved to: "
              f"{saved}Use the Read tool to access the full output.</persisted-output>")
    c = ProvenanceCollector()
    c.feed(MARK_QUERY + json.dumps({"query": "q"}))
    entry = c.feed(MARK_RESULT + notice)
    assert entry is not None
    assert len(entry["nodes"]) == 2          # ★붙은 안내문에서도 전량 복원
