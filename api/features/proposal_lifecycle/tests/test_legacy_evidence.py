import json

from api.features.proposal_lifecycle.services.legacy_evidence import (
    build_evidence_packet,
    evidence_prompt_block,
    gwt_evidence_ref_errors,
    optional_legacy_refs_instruction,
    tactical_evidence_ref_errors,
    ungrounded_gwt_values,
)


def test_legacy_refs_instruction_has_one_non_conflicting_mode():
    absent = optional_legacy_refs_instruction([])
    present = optional_legacy_refs_instruction([{"nodeId": "code:x.c:f"}])

    assert "legacyRefs는 빈 배열" in absent
    assert "실제 RULE" not in absent
    assert "1개 이상" not in absent
    assert "실제 RULE" in present
    assert "빈 배열" not in present


def _rule(node_id: str, rule_id: str, text: str, *, condition: str = "", effects=None) -> dict:
    return {
        "evidence_id": f"{node_id}::{rule_id}", "rule_id": rule_id, "line": 3,
        "condition": condition, "effects": list(effects or []),
        "narrative": {"text": text, "authority": "analyzer_llm"},
    }


def _gwt_item(node_id: str, code_text: str, *, rules=None, calls=None, tables=None) -> dict:
    rules = list(rules or [])
    target_id = f"{node_id}::TARGET"
    evidence = {
        target_id: {"id": target_id, "kind": "TARGET", "owner_id": node_id,
                    "attributes": {"type": "FUNCTION"}},
    }
    slots = {
        f"{node_id}::RESPONSIBILITY": {
            "slot_id": f"{node_id}::RESPONSIBILITY", "family": "FUNCTION",
            "role": "RESPONSIBILITY", "target_ref": target_id,
            "evidence_refs": [target_id], "meaning": code_text,
            "status": "sufficient", "missing_context": [],
        },
    }
    for rule in rules:
        evidence_id = rule["evidence_id"]
        evidence[evidence_id] = {
            "id": evidence_id, "kind": "RULE", "owner_id": node_id,
            "file": "x.c", "start_line": rule["line"], "end_line": rule["line"],
            "attributes": {"anchor_line": rule["line"], "condition": rule["condition"],
                           "effects": rule["effects"]},
        }
    return {
        "nodeId": node_id, "ok": True, "view": "frame",
        "schemaVersion": "semantic-frame-packet/v1", "label": "FUNCTION",
        "semanticFrame": {
            "schema": "semantic-frame/v1", "profile_schema": "structural-profile/v1",
            "target": {"id": node_id, "type": "FUNCTION", "owner_id": "", "file": "x.c",
                       "start_line": 1, "end_line": 9},
            "profile": {
                "schema": "structural-profile/v1",
                "target": {"id": node_id, "type": "FUNCTION", "owner_id": "", "file": "x.c",
                           "start_line": 1, "end_line": 9},
                "evidence": evidence,
            },
            "slots": slots,
        },
        "ruleExamples": [],
        "linkedContext": {"callees": list(calls or []), "symbols": [],
                          "data_objects": list(tables or [])},
    }


def _entity_frame(target_id: str, family: str, meaning: str) -> tuple[dict, str]:
    target_ref = f"{target_id}::TARGET"
    fact_ref = f"{target_id}::{family}"
    slot_id = f"{target_id}::{family}::DESCRIPTION"
    target = {
        "id": target_id, "type": family, "owner_id": "db:orders",
        "file": "(database-metadata)", "start_line": 0, "end_line": 0,
    }
    frame = {
        "schema": "semantic-frame/v1", "profile_schema": "structural-profile/v1",
        "target": target,
        "profile": {
            "schema": "structural-profile/v1", "target": target,
            "evidence": {
                target_ref: {
                    "id": target_ref, "kind": "TARGET", "owner_id": target_id,
                    "attributes": {"type": family},
                },
                fact_ref: {
                    "id": fact_ref, "kind": family, "owner_id": target_id,
                    "attributes": {"name": target_id.split(".")[-1]},
                },
            },
        },
        "slots": {
            slot_id: {
                "slot_id": slot_id, "family": family, "role": "DESCRIPTION",
                "target_ref": target_ref, "evidence_refs": [target_ref, fact_ref],
                "meaning": meaning, "status": "sufficient", "missing_context": [],
            },
        },
    }
    return frame, slot_id


def test_packet_deduplicates_by_node_id_and_keeps_richest_gwt_detail():
    node_id = "code:x.c:f"
    short = _gwt_item(node_id, "short")
    rich = _gwt_item(
        node_id, "complete source",
        rules=[_rule(node_id, "R-3", "r")], calls=[{
            "evidence_id": f"{node_id}::call::out::code:x.c:g", "name": "g",
        }],
    )
    refs = [
        {"stage": "DISCOVER", "retrieves": [{"inspections": [short]}]},
        {"stage": "TACTICAL", "retrieves": [{"inspections": [
            rich, {"nodeId": "code:x.c:failed", "ok": False, "view": "gwt"},
        ]}]},
    ]

    packet = build_evidence_packet(refs)

    assert [item["nodeId"] for item in packet] == ["code:x.c:f"]
    assert len(packet[0]["semanticFrame"]["slots"]) == 1
    assert "source" not in packet[0]


def test_packet_rejects_wrong_schema_or_broken_evidence_ref():
    valid = _gwt_item("code:x.c:f", "1 | return 0;")
    v1 = {**valid, "schemaVersion": ""}
    tampered = json.loads(json.dumps(valid))
    next(iter(tampered["semanticFrame"]["slots"].values()))["evidence_refs"] = ["missing"]
    refs = [{"retrieves": [{"inspections": [v1, tampered]}]}]

    assert build_evidence_packet(refs) == []


def test_packet_validates_and_indexes_nested_table_and_column_frames():
    node_id = "code:x.c:load"
    rule = _rule(node_id, "R-1", "PAID 상태 주문을 조회한다.", condition="status == PAID")
    table_frame, table_slot = _entity_frame("db:orders", "TABLE", "주문 상태를 보관한다")
    column_frame, column_slot = _entity_frame(
        "db:orders.status", "COLUMN", "PAID는 결제 완료 상태다",
    )
    table = {
        "evidence_id": f"{node_id}::table::db:orders", "id": "db:orders",
        "name": "orders", "access": ["READ"], "semantic_frame": table_frame,
        "columns": [{
            "id": "db:orders.status", "name": "status",
            "semantic_frame": column_frame,
        }],
    }
    packet = build_evidence_packet([{
        "retrieves": [{"inspections": [_gwt_item(node_id, "source", rules=[rule], tables=[table])]}],
    }])
    assert len(packet) == 1

    command = {
        "nodeLabel": "Command", "nodeTitle": "Load",
        "legacyRefs": [
            {"nodeId": node_id}, {"nodeId": "db:orders"},
            {"nodeId": "db:orders.status"},
        ],
        "gwt": [{
            "scenario": "paid", "evidenceRefs": [rule["evidence_id"], table_slot, column_slot],
            "given": {"name": "order", "fieldValues": {"status": "PAID"}},
            "when": {"name": "load", "fieldValues": {}},
            "then": {"name": "result", "fieldValues": {}},
        }],
    }
    assert gwt_evidence_ref_errors([command], packet) == []
    assert ungrounded_gwt_values([command], packet) == []

    broken = json.loads(json.dumps(packet[0]))
    broken["linkedContext"]["data_objects"][0]["semantic_frame"]["target"]["id"] = "db:other"
    assert build_evidence_packet([{"retrieves": [{"inspections": [broken]}]}]) == []


def test_prompt_block_explains_authority_and_structured_first_usage():
    item = _gwt_item("code:x.c:f", "1 | return 0;")
    block = json.loads(evidence_prompt_block([item]))

    assert block["contract"] == "semantic-frame-packet/v1"
    assert block["authorityOrder"][0].startswith("semanticFrame.profile.evidence")
    assert "do not expect or invent a RULE narrative slot" in block["usage"]
    assert "Do not request" in block["usage"]


def test_packet_ignores_search_only_and_non_gwt_inspections():
    refs = [{"stage": "PLAN", "retrieves": [{
        "searchedNodes": [{"id": "code:x.c:search-only"}],
        "inspections": [{"nodeId": "code:x.c:full", "ok": True}],
    }]}]

    assert build_evidence_packet(refs) == []


def test_gwt_scalar_gate_rejects_invented_representative_value_only():
    node_id = "code:x.c:calc"
    rule = _rule(node_id, "R-3", "등급 없으면 GRADE와 0을 반환한다",
                 condition="coupon_cd == CPN10OFF and order_amt < 5000",
                 effects=["disc = 0", "limit = 10000"])
    packet = [_gwt_item(node_id, "source", rules=[rule])]
    tactical = [{
        "nodeLabel": "Command", "nodeTitle": "Calculate",
        "legacyRefs": [{"nodeId": node_id, "evidenceId": rule["evidence_id"]}],
        "gwt": [{
            "scenario": "low amount", "evidenceRefs": [rule["evidence_id"]],
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
    node_id = "code:x.c:calc"
    rule = _rule(node_id, "R-1", "할인 상한을 적용한다.", effects=["disc = 20,000"])
    packet = [_gwt_item(node_id, "source", rules=[rule])]
    tactical = [{
        "nodeLabel": "Command", "nodeTitle": "Calculate", "legacyRefs": [], "gwt": [{
            "scenario": "known values", "evidenceRefs": [rule["evidence_id"]],
            "given": {"name": "input", "fieldValues": {"coupon_cd": "CPN5000"}},
            "when": {"name": "calculate", "fieldValues": {}},
            "then": {"name": "return", "fieldValues": {"disc": 20000}},
        }],
    }]

    assert ungrounded_gwt_values(
        tactical, packet, {"acceptanceCriteria": ["CPN5000을 지원한다"]},
    ) == []


def test_gwt_scalar_gate_does_not_borrow_value_from_unrelated_function():
    calc_id = "code:x.c:calc"
    calc_rule = _rule(calc_id, "R-1", "CPN10OFF는 10000을 설정한다.",
                      effects=["discount = 10000"])
    lookup_id = "code:y.c:lookup"
    lookup_rule = _rule(lookup_id, "R-2", "코드 4000을 오류명으로 변환한다.",
                        condition="code == 4000")
    packet = [
        _gwt_item(calc_id, "calc source", rules=[calc_rule]),
        _gwt_item(lookup_id, "lookup source", rules=[lookup_rule]),
    ]
    tactical = [{
        "nodeLabel": "Command", "nodeTitle": "Calculate",
        "legacyRefs": [{
            "nodeId": calc_id, "evidenceId": calc_rule["evidence_id"],
        }],
        "gwt": [{
            "scenario": "invented amount", "evidenceRefs": [calc_rule["evidence_id"]],
            "given": {"name": "input", "fieldValues": {"order_amt": 4000}},
            "when": {"name": "calculate", "fieldValues": {}},
            "then": {"name": "return", "fieldValues": {"disc": 10000}},
        }],
    }]

    errors = ungrounded_gwt_values(tactical, packet)

    assert len(errors) == 1
    assert "order_amt=4000" in errors[0]


def test_command_evidence_gate_requires_exact_rule_and_all_direct_tables():
    node_id = "code:x.c:load"
    rule = _rule(node_id, "R-3", "입력이 비면 RET_INVALID를 반환한다.")
    packet = [_gwt_item(node_id, "source", rules=[rule], tables=[
        {"evidence_id": f"{node_id}::table::db:orders", "id": "db:orders", "access": ["READ"]},
        {"evidence_id": f"{node_id}::table::db:audit", "id": "db:audit", "access": ["WRITE"]},
    ])]
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
        {"nodeId": "code:x.c:load", "evidenceId": rule["evidence_id"]},
        {"nodeId": "db:audit", "role": "writes"},
    ])
    assert tactical_evidence_ref_errors([command], packet) == []


def test_command_evidence_gate_does_not_promote_callee_table_to_direct_read():
    calc_id = "code:x.c:calc"
    lookup_id = "code:y.c:lookup"
    calc_rule = _rule(calc_id, "R-1", "계산 결과를 반환한다.")
    packet = [
        _gwt_item(calc_id, "calc source", rules=[calc_rule]),
        _gwt_item(lookup_id, "lookup source", rules=[_rule(lookup_id, "R-2", "코드를 조회한다.")],
                  tables=[{"evidence_id": f"{lookup_id}::table::db:codes",
                           "id": "db:codes", "access": ["READ"]}]),
    ]
    command = {"nodeLabel": "Command", "nodeTitle": "Calculate", "legacyRefs": [
        {"nodeId": "code:x.c:calc", "evidenceId": calc_rule["evidence_id"]},
        {"nodeId": "code:y.c:lookup", "role": "derived-from"},
    ]}

    assert tactical_evidence_ref_errors([command], packet) == []


def test_command_evidence_gate_accepts_resolved_rule_child_with_frame_parent():
    node_id = "code:x.c:load"
    rule = _rule(node_id, "R-3", "입력을 조회한다.")
    packet = [_gwt_item(node_id, "source", rules=[rule])]
    command = {"nodeLabel": "Command", "nodeTitle": "Load", "legacyRefs": [{
        "nodeId": rule["evidence_id"],
        "parentId": node_id,
        "role": "rule",
        "evidenceId": rule["evidence_id"],
    }]}

    assert tactical_evidence_ref_errors([command], packet) == []


def test_gwt_source_membership_accepts_resolved_rule_parent():
    node_id = "code:x.c:load"
    rule = _rule(node_id, "R-3", "입력을 조회한다.")
    packet = [_gwt_item(node_id, "source", rules=[rule])]
    command = {
        "nodeLabel": "Command", "nodeTitle": "Load",
        "legacyRefs": [{
            "nodeId": rule["evidence_id"], "parentId": node_id,
            "role": "rule", "evidenceId": rule["evidence_id"],
        }],
        "gwt": [{"scenario": "lookup", "evidenceRefs": [rule["evidence_id"]]}],
    }

    assert gwt_evidence_ref_errors([command], packet) == []


def test_legacy_evidence_gates_are_noops_without_analyzer_packet():
    command = {
        "nodeLabel": "Command", "nodeTitle": "Standalone",
        "gwt": [{"scenario": "normal", "evidenceRefs": []}],
        "legacyRefs": [],
    }

    assert gwt_evidence_ref_errors([command], []) == []
    assert tactical_evidence_ref_errors([command], []) == []


def test_exact_evidence_id_authoritatively_corrects_a_wrong_root_ref():
    root_id = "code:x.c:load"
    child_id = "code:x.c:load:IF@3"
    rule = _rule(child_id, "R-3", "입력이 비면 거부한다.")
    packet = [
        _gwt_item(root_id, "root"),
        _gwt_item(child_id, "child", rules=[rule]),
    ]
    command = {
        "nodeLabel": "Command", "nodeTitle": "Load",
        "legacyRefs": [{"nodeId": root_id, "evidenceId": rule["evidence_id"]}],
        "gwt": [{"scenario": "reject", "evidenceRefs": [rule["evidence_id"]]}],
    }

    assert gwt_evidence_ref_errors([command], packet) == []
    assert tactical_evidence_ref_errors([command], packet) == []


def test_each_gwt_scenario_requires_exact_rule_and_used_table_evidence_refs():
    node_id = "code:x.c:load"
    rule = _rule(node_id, "R-3", "PAID 주문을 조회한다.", condition="status == PAID")
    table_id = f"{node_id}::table::db:orders"
    packet = [_gwt_item(node_id, "source", rules=[rule], tables=[{
        "evidence_id": table_id, "id": "db:orders", "access": ["READ"],
        "sample": {"sample_rows": [{"status": "PAID"}]},
    }])]
    command = {
        "nodeLabel": "Command", "nodeTitle": "Load",
        "legacyRefs": [{"nodeId": node_id}],
        "gwt": [{"scenario": "paid", "evidenceRefs": [rule["evidence_id"], table_id]}],
    }

    assert gwt_evidence_ref_errors([command], packet) == []
    command["gwt"][0]["evidenceRefs"] = [table_id]
    assert any("RULE evidenceRef" in error for error in gwt_evidence_ref_errors([command], packet))
    command["gwt"][0]["evidenceRefs"] = ["unknown"]
    assert any("unknown evidenceRef" in error for error in gwt_evidence_ref_errors([command], packet))
