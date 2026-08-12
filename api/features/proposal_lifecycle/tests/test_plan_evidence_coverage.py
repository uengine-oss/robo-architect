from api.features.proposal_lifecycle.services.plan_runner import (
    _build_plan_prompt,
    missing_plan_legacy_refs,
    normalize_tactical_diff,
    tactical_contract_errors,
)
from api.features.proposal_lifecycle.services.stage_runners.tactical import _has_complete_commands


def _strategic():
    return {
        "userStories": [{
            "tempId": "US-1",
            "legacyRefs": [
                {"nodeId": "code:shop/calc_discount"},
                {"nodeId": "code:shop/load_target_orders"},
                {"nodeId": "code:shop/get_code_name"},
            ],
        }],
    }


def test_missing_plan_refs_reports_exact_silent_omissions():
    tactical = [{
        "nodeLabel": "Command",
        "legacyRefs": [{"nodeId": "code:shop/calc_discount"}],
    }]

    assert missing_plan_legacy_refs(_strategic(), tactical) == [
        "code:shop/get_code_name",
        "code:shop/load_target_orders",
    ]


def test_all_strategic_refs_carried_once_or_more_passes():
    tactical = [{
        "nodeLabel": "Command",
        "legacyRefs": [
            "code:shop/calc_discount",
            {"nodeId": "code:shop/load_target_orders"},
            {"nodeId": "code:shop/get_code_name"},
        ],
    }]

    assert missing_plan_legacy_refs(_strategic(), tactical) == []


def test_resolved_rule_child_counts_as_its_inspected_parent_function_for_coverage():
    strategic = {"userStories": [{"legacyRefs": [{
        "nodeId": "code:shop/calc::R-12", "parentId": "code:shop/calc",
        "role": "rule", "evidenceId": "code:shop/calc::R-12",
    }]}]}
    tactical = [{"nodeLabel": "Command", "legacyRefs": [{"nodeId": "code:shop/calc"}]}]

    assert missing_plan_legacy_refs(strategic, tactical) == []


def test_plan_prompt_contains_machine_countable_required_manifest(monkeypatch):
    from api.features.constitution.services import constitution_store
    monkeypatch.setattr(constitution_store, "get_project_strategic_memory", lambda: {})
    prompt = _build_plan_prompt("PRO-X", _strategic(), "constitution", [])

    assert "Strategic legacyRefs 보존 필수 목록" in prompt
    assert prompt.count('"code:shop/calc_discount"') >= 2
    assert "각 ID를 의미상 대응하는 tactical 요소" in prompt


def test_plan_prompt_explains_evidence_input_and_does_not_require_duplicate_lookup(monkeypatch):
    from api.features.constitution.services import constitution_store
    monkeypatch.setattr(constitution_store, "get_project_strategic_memory", lambda: {})
    packet = [{
        "nodeId": "code:shop/calc_discount", "ok": True, "view": "frame",
        "schemaVersion": "semantic-frame-packet/v1",
        "semanticFrame": {"schema": "semantic-frame/v1", "slots": {
            "SL:discount": {"meaning": "쿠폰 코드가 비면 0을 반환한다"},
        }},
        "linkedContext": {"callees": [], "symbols": [], "data_objects": []},
    }]

    prompt = _build_plan_prompt("PRO-X", _strategic(), "constitution", [], evidence_packet=packet)

    assert "[INPUT MEANING]" in prompt
    assert "code:shop/calc_discount" in prompt
    assert "packet에 있는 nodeId는 재조회하지 말고" in prompt
    assert "예시 스키마의 이름·상태·숫자를 복사하지 않는다" in prompt
    assert "slot meaning은" in prompt
    assert '"evidenceRefs"' in prompt


def test_tactical_contract_requires_command_story_refs_and_structured_gwt():
    errors = tactical_contract_errors([{
        "nodeLabel": "Command", "nodeTitle": "Calculate", "userStoryRefs": [],
    }])
    assert any("userStoryRefs" in error for error in errors)
    assert any("gwt" in error for error in errors)

    assert tactical_contract_errors([{
        "nodeLabel": "Command", "nodeTitle": "Calculate", "userStoryRefs": ["us:calc"],
        "gwt": [{
            "scenario": "empty input", "evidenceRefs": ["code:x::R-1"],
            "given": {"name": "input", "fieldValues": {}},
            "when": {"name": "calculate", "fieldValues": {}},
            "then": {"name": "return", "fieldValues": {"value": 0}},
        }, {
            "scenario": "valid input", "evidenceRefs": ["code:x::R-2"],
            "given": {"name": "input", "fieldValues": {}},
            "when": {"name": "calculate", "fieldValues": {}},
            "then": {"name": "return", "fieldValues": {}},
        }],
    }]) == []


def test_normalize_tactical_diff_lifts_transport_fields_without_duplication():
    scenarios = [{
        "scenario": "empty input", "evidenceRefs": ["code:x::R-1"],
        "given": {"name": "input", "fieldValues": {}},
        "when": {"name": "calculate", "fieldValues": {}},
        "then": {"name": "return", "fieldValues": {}},
    }, {
        "scenario": "valid input", "evidenceRefs": ["code:x::R-2"],
        "given": {"name": "input", "fieldValues": {}},
        "when": {"name": "calculate", "fieldValues": {}},
        "then": {"name": "return", "fieldValues": {}},
    }]
    [command] = normalize_tactical_diff([{
        "entityType": "command",
        "entityTitle": "Calculate",
        "fields": {
            "inputSchema": {"value": "number"},
            "properties": [{"name": "value", "type": "number"}],
            "userStoryRefs": ["us:calc"],
            "gwt": scenarios,
            "legacyRefs": [{"nodeId": "code:x.c:calc"}],
        },
    }])

    assert command["fields"] == {"inputSchema": {"value": "number"}}
    assert command["properties"] == [{"name": "value", "type": "number"}]
    assert command["userStoryRefs"] == ["us:calc"]
    assert command["gwt"] == scenarios
    assert command["legacyRefs"] == [{"nodeId": "code:x.c:calc"}]


def test_detailed_tactical_contract_requires_scenario_evidence_refs():
    artifact = {"aggregates": [{"handledCommands": [{
        "name": "Calculate", "userStoryRefs": ["us:calc"],
        "gwt": [{
            "scenario": name, "evidenceRefs": [f"code:x::{name}"],
            "given": {"name": "input", "fieldValues": {}},
            "when": {"name": "calculate", "fieldValues": {}},
            "then": {"name": "return", "fieldValues": {}},
        } for name in ("normal", "boundary")],
    }]}]}

    assert _has_complete_commands(artifact, {"us:calc"}) is True
    artifact["aggregates"][0]["handledCommands"][0]["gwt"][0].pop("evidenceRefs")
    assert _has_complete_commands(artifact, {"us:calc"}) is False
