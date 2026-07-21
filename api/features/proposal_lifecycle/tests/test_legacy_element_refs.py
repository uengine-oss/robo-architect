"""evlink — 요소별 legacyRefs 검증 계약(부정 케이스 중심)."""
from __future__ import annotations

import json

from api.features.proposal_lifecycle.services.legacy_element_refs import (
    allowed_ref_ids,
    resolve_content_refs,
    validate_strategic_refs,
    validate_tactical_refs,
)


def _refs_v2(searched=(), ok_inspections=(), failed_inspections=()):
    return [{
        "version": 2, "stage": "INTENT",
        "retrieves": [{
            "query": "q",
            "searchedNodes": [{"id": nid, "name": nid} for nid in searched],
            "inspections": (
                [{"nodeId": nid, "ok": True} for nid in ok_inspections]
                + [{"nodeId": nid, "ok": False, "error": {"code": "X"}} for nid in failed_inspections]
            ),
        }],
    }]


# ── allowed_ref_ids ──────────────────────────────────────────────────────────

def test_allowed_ids_from_v2_searched_and_ok_inspections_only():
    refs = _refs_v2(searched=["code:a.c:f1", "db:t1"],
                    ok_inspections=["code:a.c:f2"],
                    failed_inspections=["code:invented"])
    assert allowed_ref_ids(refs) == {"code:a.c:f1", "db:t1", "code:a.c:f2"}


def test_allowed_ids_from_v1_nodes_key():
    refs = [{"stage": "INTENT", "retrieves": [{"query": "q", "nodes": [{"id": "code:v1:fn"}]}]}]
    assert allowed_ref_ids(refs) == {"code:v1:fn"}


def test_allowed_ids_accepts_json_string_and_rejects_broken_input():
    refs = _refs_v2(searched=["code:x"])
    assert allowed_ref_ids(json.dumps(refs)) == {"code:x"}
    assert allowed_ref_ids("깨진 { json") == set()
    assert allowed_ref_ids(None) == set()
    assert allowed_ref_ids([]) == set()


def test_allowed_ids_survives_malformed_shapes():
    refs = ["문자열 스테이지", {"retrieves": "리스트 아님"},
            {"retrieves": [None, {"searchedNodes": "리스트 아님", "inspections": [None, {"ok": True}]},
                           {"searchedNodes": [None, {"id": ""}, {"id": 42}, {"id": "code:ok"}]}]}]
    assert allowed_ref_ids(refs) == {"code:ok"}


# ── validate_strategic_refs ──────────────────────────────────────────────────

def _diff(elements):
    return {"version": 1, "epics": elements}


def test_valid_refs_kept_and_normalized():
    diff = _diff([{"tempId": "EP-1", "legacyRefs": [
        {"nodeId": "code:a.c:f1", "role": "derived-from", "evidence": "배송상태 전이 로직"},
        "db:t1",  # bare string 도 수용
    ]}])
    warnings = validate_strategic_refs(diff, {"code:a.c:f1", "db:t1"})
    assert warnings == []
    assert diff["epics"][0]["legacyRefs"] == [
        {"nodeId": "code:a.c:f1", "role": "derived-from", "evidence": "배송상태 전이 로직"},
        {"nodeId": "db:t1"},
    ]
    assert "_legacyRefWarnings" not in diff


def test_unobserved_node_id_is_dropped_with_warning():
    diff = _diff([{"tempId": "EP-1", "legacyRefs": [{"nodeId": "code:hallucinated"}]}])
    warnings = validate_strategic_refs(diff, {"code:real"})
    assert diff["epics"][0]["legacyRefs"] == []
    assert warnings == [{"element": "epics[EP-1]", "code": "REF_NOT_OBSERVED",
                         "nodeId": "code:hallucinated"}]
    assert diff["_legacyRefWarnings"] == warnings


def test_missing_refs_falls_back_to_new_with_warning():
    diff = _diff([{"tempId": "EP-1"}])
    warnings = validate_strategic_refs(diff, {"code:x"})
    assert diff["epics"][0]["legacyRefs"] == []
    assert warnings[0]["code"] == "REFS_MISSING"


def test_non_list_refs_normalized_with_warning():
    diff = _diff([{"tempId": "EP-1", "legacyRefs": "code:x"}])
    warnings = validate_strategic_refs(diff, {"code:x"})
    assert diff["epics"][0]["legacyRefs"] == []
    assert warnings[0]["code"] == "REFS_NOT_A_LIST"


def test_empty_refs_is_honest_new_without_warning():
    diff = _diff([{"tempId": "EP-1", "legacyRefs": []}])
    assert validate_strategic_refs(diff, {"code:x"}) == []
    assert diff["epics"][0]["legacyRefs"] == []


def test_malformed_entries_warn_and_do_not_crash():
    diff = _diff([{"tempId": "EP-1", "legacyRefs": [
        None, 42, {"role": "derived-from"}, {"nodeId": "   "}, {"nodeId": "code:ok"},
    ]}])
    warnings = validate_strategic_refs(diff, {"code:ok"})
    assert diff["epics"][0]["legacyRefs"] == [{"nodeId": "code:ok"}]
    assert [w["code"] for w in warnings] == ["REF_MALFORMED"] * 4


def test_duplicates_deduped_first_wins():
    diff = _diff([{"tempId": "EP-1", "legacyRefs": [
        {"nodeId": "code:a", "evidence": "첫째"}, {"nodeId": "code:a", "evidence": "둘째"},
    ]}])
    assert validate_strategic_refs(diff, {"code:a"}) == []
    assert diff["epics"][0]["legacyRefs"] == [{"nodeId": "code:a", "evidence": "첫째"}]


def test_evidence_truncated_and_unknown_role_dropped():
    diff = _diff([{"tempId": "EP-1", "legacyRefs": [
        {"nodeId": "code:a", "evidence": "가" * 500, "role": "invented-role", "field": "status"},
    ]}])
    validate_strategic_refs(diff, {"code:a"})
    ref = diff["epics"][0]["legacyRefs"][0]
    assert len(ref["evidence"]) == 200
    assert "role" not in ref
    assert ref["field"] == "status"


def test_revalidation_replaces_stale_warnings():
    diff = _diff([{"tempId": "EP-1", "legacyRefs": [{"nodeId": "code:bad"}]}])
    validate_strategic_refs(diff, set())
    assert diff["_legacyRefWarnings"]
    diff["epics"][0]["legacyRefs"] = [{"nodeId": "code:good"}]
    validate_strategic_refs(diff, {"code:good"})
    assert "_legacyRefWarnings" not in diff


def test_version_key_and_non_dict_elements_skipped():
    diff = {"version": 3, "epics": ["문자열", {"tempId": "EP-1", "legacyRefs": []}],
            "_legacyRefWarnings": [{"element": "낡은 경고"}]}
    assert validate_strategic_refs(diff, set()) == []
    assert diff["version"] == 3
    assert "_legacyRefWarnings" not in diff  # 낡은 경고 청소


def test_non_dict_diff_returns_no_warnings():
    assert validate_strategic_refs(None, set()) == []
    assert validate_strategic_refs("문자열", set()) == []


# ── 이종 프로젝트 안전성(임의 id 스킴·빈 그래프) ────────────────────────────

def test_arbitrary_id_schemes_pass_set_membership():
    """검증기는 id 형식을 해석하지 않는다 — 접두사·유니코드·경로문자 무관 집합 판정만."""
    weird = ["java:com.acme.Order#place", "file:src/한글 경로/주문.xml#섹션-1",
             "proc:PKG$BODY.LOAD_DATA@2", "x" * 500]
    refs = _refs_v2(searched=weird)
    diff = _diff([{"tempId": "EP-1", "legacyRefs": [{"nodeId": n} for n in weird]}])
    assert validate_strategic_refs(diff, allowed_ref_ids(refs)) == []
    assert [r["nodeId"] for r in diff["epics"][0]["legacyRefs"]] == weird


def test_empty_graph_project_falls_back_to_new_everywhere():
    """분석 안 된/빈 그래프 프로젝트: 관찰집합이 비면 모든 근거가 제거되고 new 폴백 —
    깨지지 않고 정직하게 동작해야 한다."""
    diff = _diff([{"tempId": "EP-1", "legacyRefs": [{"nodeId": "code:any"}]},
                  {"tempId": "EP-2"}])
    warnings = validate_strategic_refs(diff, allowed_ref_ids([]))
    assert diff["epics"][0]["legacyRefs"] == []
    assert diff["epics"][1]["legacyRefs"] == []
    assert {w["code"] for w in warnings} == {"REF_NOT_OBSERVED", "REFS_MISSING"}


# ── resolve_content_refs — 내용 인용 → 노드 승격(rule/example/table 전부 찍기) ──

_CHILDREN = {
    "code:f1": {
        "rules": [
            {"id": "code:f1::rule::1",
             "statement": "주문 상태가 '90'(취소) 이면 배송 상태 변경을 거부한다.",
             "examples": [{"id": "code:f1::rule::1::ex::1",
                           "given": "취소된 주문", "when": "상태 변경 시도", "then": "거부"}]},
        ],
        "tables": [{"id": "db:shop.orders", "name": "orders"}],
    },
}


def _fetch(parent_id):
    return _CHILDREN.get(parent_id)


def test_rule_statement_resolves_to_rule_node():
    diff = _diff([{"tempId": "EP-1", "legacyRefs": [
        {"nodeId": "code:f1", "rule": "주문 상태가 '90'(취소) 이면  배송 상태 변경을 거부한다"},
    ]}])
    warnings = resolve_content_refs(diff, None, _fetch)
    ref = diff["epics"][0]["legacyRefs"][0]
    assert warnings == []
    assert ref["nodeId"] == "code:f1::rule::1"
    assert ref["role"] == "rule"
    assert ref["parentId"] == "code:f1"
    assert "'90'" in ref["statement"]
    assert ref["examples"][0]["when"] == "상태 변경 시도"


def test_unmatched_rule_keeps_function_ref_with_warning():
    diff = _diff([{"tempId": "EP-1", "legacyRefs": [
        {"nodeId": "code:f1", "rule": "이 함수에 없는 지어낸 규칙 문장이다"},
    ]}])
    warnings = resolve_content_refs(diff, None, _fetch)
    ref = diff["epics"][0]["legacyRefs"][0]
    assert ref["nodeId"] == "code:f1"  # 함수 근거는 유지, 규칙 주장만 기각
    assert "rule" not in ref
    assert warnings[0]["code"] == "RULE_NOT_MATCHED"


def test_example_resolves_to_example_node():
    diff = _diff([{"tempId": "EP-1", "legacyRefs": [
        {"nodeId": "code:f1", "example": {"given": "취소된 주문", "when": "상태 변경 시도"}},
    ]}])
    warnings = resolve_content_refs(diff, None, _fetch)
    ref = diff["epics"][0]["legacyRefs"][0]
    assert warnings == []
    assert ref["nodeId"] == "code:f1::rule::1::ex::1"
    assert ref["role"] == "example"
    assert ref["examples"][0]["then"] == "거부"


def test_table_name_resolves_including_schema_prefix():
    tactical = [{"nodeId": "AGG-1", "legacyRefs": [
        {"nodeId": "code:f1", "table": "SHOP.ORDERS", "role": "writes"},
    ]}]
    warnings = resolve_content_refs(None, tactical, _fetch)
    ref = tactical[0]["legacyRefs"][0]
    assert warnings == []
    assert ref["nodeId"] == "db:shop.orders"
    assert ref["role"] == "writes"  # 테이블은 기존 role 유지
    assert ref["parentId"] == "code:f1"


def test_table_field_on_direct_table_id_is_self_match():
    """LLM 이 테이블을 직접 id 로 인용하며 table 필드를 중복 첨부 — 경고 없이 필드만 제거."""
    tactical = [{"nodeId": "AGG-1", "legacyRefs": [
        {"nodeId": "db:shop.product_stock", "table": "product_stock", "role": "reads"},
    ]}]
    warnings = resolve_content_refs(None, tactical, _fetch)
    ref = tactical[0]["legacyRefs"][0]
    assert warnings == []
    assert ref["nodeId"] == "db:shop.product_stock"
    assert "table" not in ref and "parentId" not in ref


def test_roundtrip_reverify_drops_detached_content_ref():
    diff = _diff([{"tempId": "EP-1", "legacyRefs": [
        {"nodeId": "code:f1::rule::999", "role": "rule", "parentId": "code:f1",
         "statement": "옛 문장"},
    ]}])
    warnings = resolve_content_refs(diff, None, _fetch)
    assert diff["epics"][0]["legacyRefs"] == []
    assert warnings[0]["code"] == "CONTENT_NOT_OBSERVED"


def test_resolved_duplicates_dedupe_and_missing_parent_safe():
    diff = _diff([{"tempId": "EP-1", "legacyRefs": [
        {"nodeId": "code:f1", "rule": "주문 상태가 '90'(취소) 이면 배송 상태 변경을 거부한다."},
        {"nodeId": "code:f1", "rule": "주문 상태가 '90'(취소) 이면 배송 상태 변경을 거부한다."},
        {"nodeId": "code:unknown", "rule": "아무 규칙"},
    ]}])
    warnings = resolve_content_refs(diff, None, _fetch)
    refs = diff["epics"][0]["legacyRefs"]
    assert [r["nodeId"] for r in refs] == ["code:f1::rule::1", "code:unknown"]
    assert [w["code"] for w in warnings] == ["RULE_NOT_MATCHED"]


# ── validate_tactical_refs ───────────────────────────────────────────────────

def test_tactical_list_validated_with_element_keys():
    tactical = [
        {"nodeId": "agg-1", "legacyRefs": [{"nodeId": "code:ok"}, {"nodeId": "code:bad"}]},
        {"name": "OrderAggregate"},
    ]
    warnings = validate_tactical_refs(tactical, {"code:ok"})
    assert tactical[0]["legacyRefs"] == [{"nodeId": "code:ok"}]
    assert {w["code"] for w in warnings} == {"REF_NOT_OBSERVED", "REFS_MISSING"}
    assert warnings[0]["element"] == "tactical[agg-1]"


def test_tactical_non_list_input_is_noop():
    assert validate_tactical_refs(None, set()) == []
    assert validate_tactical_refs({"not": "list"}, set()) == []
