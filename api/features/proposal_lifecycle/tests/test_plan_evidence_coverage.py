from api.features.proposal_lifecycle.services.plan_runner import (
    _build_plan_prompt,
    missing_plan_legacy_refs,
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
