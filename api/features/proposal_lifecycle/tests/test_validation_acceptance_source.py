import json

from api.features.proposal_lifecycle.services.test_runner import (
    _acceptance_scenario_count,
    _criteria_from_strategic_diff,
    _criteria_from_tactical_diff,
)


def test_tactical_command_gwt_is_deterministic_acceptance_source():
    tactical = [{
        "nodeLabel": "Command",
        "nodeId": "cmd:PlaceOrder",
        "nodeTitle": "PlaceOrder",
        "gwt": [
            {"scenario": "normal", "given": {}, "when": {}, "then": {}},
            {"scenario": "failure", "given": {}, "when": {}, "then": {}},
        ],
    }, {
        "nodeLabel": "Event",
        "nodeId": "evt:OrderPlaced",
        "nodeTitle": "OrderPlaced",
    }]

    stories = _criteria_from_tactical_diff(json.dumps(tactical))

    assert stories == [{
        "storyId": "cmd:PlaceOrder",
        "storyTitle": "PlaceOrder",
        "criteria": tactical[0]["gwt"],
    }]
    assert _acceptance_scenario_count(stories) == 2


def test_tactical_source_ignores_commands_without_gwt():
    assert _criteria_from_tactical_diff([
        {"nodeLabel": "Command", "nodeId": "cmd:x", "gwt": []},
        {"nodeLabel": "Aggregate", "nodeId": "agg:x", "gwt": [{"scenario": "x"}]},
    ]) == []


def test_strategic_user_story_is_last_resort_source():
    strategic = {"userStories": [{
        "tempId": "us:review",
        "entityTitle": "Review order",
        "acceptanceCriteria": ["Given order When review Then shown"],
    }]}

    stories = _criteria_from_strategic_diff(strategic)

    assert stories[0]["storyId"] == "us:review"
    assert _acceptance_scenario_count(stories) == 1
