from api.features.proposal_lifecycle.services.legacy_evidence import (
    build_evidence_packet,
    tactical_evidence_ref_errors,
    ungrounded_gwt_values,
)


def test_packet_deduplicates_by_node_id_and_keeps_richest_gwt_detail():
    refs = [
        {"stage": "DISCOVER", "retrieves": [{"inspections": [{
            "nodeId": "code:x.c:f", "ok": True, "view": "gwt",
            "source": {"code_text": "short"}, "rules": [], "calls": [], "tables": [],
        }]}]},
        {"stage": "TACTICAL", "retrieves": [{"inspections": [{
            "nodeId": "code:x.c:f", "ok": True, "view": "gwt",
            "source": {"code_text": "complete source"},
            "rules": [{"line": 3, "text": "r"}], "calls": [{"name": "g"}], "tables": [],
        }, {"nodeId": "code:x.c:failed", "ok": False, "view": "gwt"}]}]},
    ]

    packet = build_evidence_packet(refs)

    assert [item["nodeId"] for item in packet] == ["code:x.c:f"]
    assert packet[0]["source"]["code_text"] == "complete source"
    assert packet[0]["rules"][0]["line"] == 3


def test_packet_ignores_search_only_and_non_gwt_inspections():
    refs = [{"stage": "PLAN", "retrieves": [{
        "searchedNodes": [{"id": "code:x.c:search-only"}],
        "inspections": [{"nodeId": "code:x.c:full", "ok": True}],
    }]}]

    assert build_evidence_packet(refs) == []


def test_gwt_scalar_gate_rejects_invented_representative_value_only():
    packet = [{
        "nodeId": "code:x.c:calc", "ok": True, "view": "gwt",
        "summary": "CPN10OFF는 10000, 주문금액 5000 미만이면 절반",
        "rules": [{"line": 3, "text": "등급 없으면 GRADE와 0을 반환한다"}],
    }]
    tactical = [{
        "nodeLabel": "Command", "nodeTitle": "Calculate",
        "legacyRefs": [{"nodeId": "code:x.c:calc", "rule": "등급 없으면 GRADE와 0을 반환한다"}],
        "gwt": [{
            "scenario": "low amount",
            "given": {"name": "input", "fieldValues": {
                "coupon_cd": "CPN10OFF", "order_amt": 4000,
            }},
            "when": {"name": "calculate", "fieldValues": {}},
            "then": {"name": "return", "fieldValues": {"disc": 0}},
        }],
    }]

    errors = ungrounded_gwt_values(tactical, packet)

    assert len(errors) == 1
    assert "order_amt=4000" in errors[0]


def test_gwt_scalar_gate_accepts_literals_from_strategic_input_and_comma_form():
    packet = [{
        "nodeId": "code:x.c:calc", "ok": True, "view": "gwt",
        "summary": "할인 상한은 20,000이고 빈 입력은 0",
    }]
    tactical = [{
        "nodeLabel": "Command", "nodeTitle": "Calculate", "legacyRefs": [], "gwt": [{
            "scenario": "known values",
            "given": {"name": "input", "fieldValues": {"coupon_cd": "CPN5000"}},
            "when": {"name": "calculate", "fieldValues": {}},
            "then": {"name": "return", "fieldValues": {"disc": 20000}},
        }],
    }]

    assert ungrounded_gwt_values(
        tactical, packet, {"acceptanceCriteria": ["CPN5000을 지원한다"]},
    ) == []


def test_gwt_scalar_gate_does_not_borrow_value_from_unrelated_function():
    packet = [{
        "nodeId": "code:x.c:calc", "ok": True, "view": "gwt",
        "rules": [{"text": "CPN10OFF는 10000을 설정한다."}],
    }, {
        "nodeId": "code:y.c:lookup", "ok": True, "view": "gwt",
        "rules": [{"text": "코드 4000을 오류명으로 변환한다."}],
    }]
    tactical = [{
        "nodeLabel": "Command", "nodeTitle": "Calculate",
        "legacyRefs": [{
            "nodeId": "code:x.c:calc", "rule": "CPN10OFF는 10000을 설정한다.",
        }],
        "gwt": [{
            "scenario": "invented amount",
            "given": {"name": "input", "fieldValues": {"order_amt": 4000}},
            "when": {"name": "calculate", "fieldValues": {}},
            "then": {"name": "return", "fieldValues": {"disc": 10000}},
        }],
    }]

    errors = ungrounded_gwt_values(tactical, packet)

    assert len(errors) == 1
    assert "order_amt=4000" in errors[0]


def test_command_evidence_gate_requires_exact_rule_and_all_direct_tables():
    packet = [{
        "nodeId": "code:x.c:load", "ok": True, "view": "gwt",
        "rules": [{"line": 3, "text": "입력이 비면 RET_INVALID를 반환한다."}],
        "tables": [
            {"id": "db:orders", "access": ["READ"]},
            {"id": "db:audit", "access": ["WRITE"]},
        ],
    }]
    command = {
        "nodeLabel": "Command", "nodeTitle": "Load", "legacyRefs": [
            {"nodeId": "code:x.c:load"},
            {"nodeId": "db:orders", "role": "reads"},
        ],
    }

    errors = tactical_evidence_ref_errors([command], packet)

    assert any("exact inspected RULE" in error for error in errors)
    assert any("db:audit" in error for error in errors)

    command["legacyRefs"].extend([
        {"nodeId": "code:x.c:load", "rule": "입력이 비면 RET_INVALID를 반환한다."},
        {"nodeId": "db:audit", "role": "writes"},
    ])
    assert tactical_evidence_ref_errors([command], packet) == []


def test_command_evidence_gate_does_not_promote_callee_table_to_direct_read():
    packet = [{
        "nodeId": "code:x.c:calc", "ok": True, "view": "gwt",
        "rules": [{"text": "계산 결과를 반환한다."}], "tables": [],
    }, {
        "nodeId": "code:y.c:lookup", "ok": True, "view": "gwt",
        "rules": [{"text": "코드를 조회한다."}],
        "tables": [{"id": "db:codes", "access": ["READ"]}],
    }]
    command = {"nodeLabel": "Command", "nodeTitle": "Calculate", "legacyRefs": [
        {"nodeId": "code:x.c:calc", "rule": "계산 결과를 반환한다."},
        {"nodeId": "code:y.c:lookup", "role": "derived-from"},
    ]}

    assert tactical_evidence_ref_errors([command], packet) == []
