from api.features.proposal_lifecycle.services.plan_runner import (
    _build_plan_prompt,
    missing_plan_legacy_refs,
    normalize_tactical_diff,
    tactical_contract_errors,
)


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
        "nodeId": "code:shop/calc_discount", "ok": True, "view": "gwt",
        "source": {"start_line": 10, "end_line": 20},
        "rules": [{"line": 12, "text": "쿠폰 코드가 비면 0을 반환한다"}],
        "calls": [], "tables": [],
    }]

    prompt = _build_plan_prompt("PRO-X", _strategic(), "constitution", [], evidence_packet=packet)

    assert "[INPUT MEANING]" in prompt
    assert "code:shop/calc_discount" in prompt
    assert "packet에 있는 nodeId는 재조회하지 말고" in prompt
    assert "예시 스키마의 이름·상태·숫자를 복사하지 않는다" in prompt


def test_tactical_contract_requires_command_story_refs_and_structured_gwt():
    errors = tactical_contract_errors([{
        "nodeLabel": "Command", "nodeTitle": "Calculate", "userStoryRefs": [],
    }])
    assert any("userStoryRefs" in error for error in errors)
    assert any("gwt" in error for error in errors)

    assert tactical_contract_errors([{
        "nodeLabel": "Command", "nodeTitle": "Calculate", "userStoryRefs": ["us:calc"],
        "gwt": [{
            "scenario": "empty input", "given": {"name": "input", "fieldValues": {}},
            "when": {"name": "calculate", "fieldValues": {}},
            "then": {"name": "return", "fieldValues": {"value": 0}},
        }, {
            "scenario": "valid input", "given": {"name": "input", "fieldValues": {}},
            "when": {"name": "calculate", "fieldValues": {}},
            "then": {"name": "return", "fieldValues": {}},
        }],
    }]) == []


def test_normalize_tactical_diff_lifts_transport_fields_without_duplication():
    scenarios = [{
        "scenario": "empty input",
        "given": {"name": "input", "fieldValues": {}},
        "when": {"name": "calculate", "fieldValues": {}},
        "then": {"name": "return", "fieldValues": {}},
    }, {
        "scenario": "valid input",
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
