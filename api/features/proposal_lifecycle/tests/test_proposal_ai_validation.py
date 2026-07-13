import pytest

from api.features.proposal_lifecycle.services.proposal_ai_validation import (
    SkillScenario,
    retry_count_for_scenario,
    validate_plan_output,
    validate_stage_artifact,
    validate_strategic_output,
    validate_tactical_output,
)


def test_retry_policy_by_scenario():
    assert retry_count_for_scenario(SkillScenario.SIMPLIFIED_STRATEGIC) == 1
    assert retry_count_for_scenario(SkillScenario.SIMPLIFIED_TACTICAL) == 1
    assert retry_count_for_scenario(SkillScenario.DETAILED_STRATEGIC_FROM_DDD) == 2
    assert retry_count_for_scenario(SkillScenario.DETAILED_TACTICAL_FROM_DDD) == 2


def test_strategic_validator_accepts_canonical_output():
    result = validate_strategic_output({
        "action": "done",
        "strategicDiff": {
            "version": 1,
            "epics": [
                {"op": "CREATE", "entityType": "BoundedContext", "tempId": "EP-order", "entityTitle": "주문"}
            ],
            "features": [
                {"op": "CREATE", "entityType": "Feature", "tempId": "FT-order", "entityTitle": "주문 관리", "epicId": "EP-order"}
            ],
            "userStories": [
                {
                    "op": "CREATE",
                    "entityType": "UserStory",
                    "tempId": "US-place-order",
                    "entityTitle": "고객: 주문한다",
                    "featureId": "FT-order",
                    "boundedContextId": "EP-order",
                    "role": "고객",
                    "action": "주문한다",
                    "benefit": "상품을 구매하기 위해",
                }
            ],
            "processes": [],
        },
    })

    assert result.valid is True


def test_strategic_validator_rejects_invalid_op():
    result = validate_strategic_output({
        "action": "done",
        "strategicDiff": {
            "version": 1,
            "epics": [
                {"op": "NONE", "entityType": "BoundedContext", "tempId": "EP-order", "entityTitle": "주문"}
            ],
            "features": [],
            "userStories": [],
            "processes": [],
        },
    })

    assert result.valid is False
    assert result.violations[0]["path"] == "strategicDiff.epics[0].op"


def test_stage_validator_blocks_missing_required_array_and_warns_quality():
    blocked = validate_stage_artifact("DISCOVER", {"events": []})
    assert blocked.valid is False
    assert blocked.violations[0]["path"] == "DISCOVER.events"

    warn = validate_stage_artifact("TACTICAL", {"aggregates": [{"name": "Order", "invariants": ["one"]}]})
    assert warn.valid is True
    assert warn.warnings and warn.warnings[0]["severity"] == "warning"


def test_plan_validator_rejects_invalid_tactical_before_save():
    result = validate_plan_output({
        "tacticalDiff": [{"nodeLabel": "Aggregate", "nodeTitle": "Order"}],
        "implementationPlan": {"version": 1, "architectureDecisions": []},
    })

    assert result.valid is False
    codes = {v["code"] for v in result.violations}
    assert "required" in codes


def test_tactical_validator_accepts_canonical_minimum():
    result = validate_tactical_output({
        "tacticalDiff": [
            {
                "nodeId": "AGG-order",
                "nodeLabel": "Aggregate",
                "nodeTitle": "Order",
                "changeType": "CREATE",
                "impactLevel": "MEDIUM",
                "boundedContextId": "EP-order",
                "fields": {"rootEntity": "Order"},
                "properties": [
                    {"name": "orderId", "type": "UUID"},
                    {"name": "totalAmount", "type": "Money"},
                    {"name": "status", "type": "OrderStatus"},
                ],
            },
            # 015-issue2: Aggregate 가 있으면 VO/Enum 노드가 필수이며, 선언 타입은 속성으로 쓰여야 한다.
            {
                "nodeId": "VO-money",
                "nodeLabel": "ValueObject",
                "nodeTitle": "금액",
                "changeType": "CREATE",
                "impactLevel": "LOW",
                "aggregateId": "AGG-order",
                "fields": {"typeName": "Money"},
                "properties": [{"name": "amount", "type": "BigDecimal"},
                               {"name": "currency", "type": "String"}],
            },
            {
                "nodeId": "ENUM-order-status",
                "nodeLabel": "Enumeration",
                "nodeTitle": "주문 상태",
                "changeType": "CREATE",
                "impactLevel": "LOW",
                "aggregateId": "AGG-order",
                "fields": {"typeName": "OrderStatus", "items": ["PLACED", "CANCELLED"]},
            },
            {
                "nodeId": "CMD-place-order",
                "nodeLabel": "Command",
                "nodeTitle": "PlaceOrder",
                "changeType": "CREATE",
                "impactLevel": "MEDIUM",
                "aggregateId": "AGG-order",
                "fields": {"inputSchema": {"customerId": "UUID"}},
                "properties": [{"name": "customerId", "type": "UUID"}],
                "userStoryRefs": ["US-place-order"],
                "gwt": [{
                    "given": {"fieldValues": {"orderId": "new"}},
                    "when": {"fieldValues": {"customerId": "c-1"}},
                    "then": {"fieldValues": {"orderId": "o-1"}},
                }],
            },
            {
                "nodeId": "EVT-order-placed",
                "nodeLabel": "Event",
                "nodeTitle": "OrderPlaced",
                "changeType": "CREATE",
                "impactLevel": "MEDIUM",
                "commandId": "CMD-place-order",
                "fields": {"payload": {"orderId": "UUID"}},
                "properties": [{"name": "orderId", "type": "UUID"}],
            },
            {
                "nodeId": "RM-order-status",
                "nodeLabel": "ReadModel",
                "nodeTitle": "OrderStatus",
                "changeType": "CREATE",
                "impactLevel": "LOW",
                "boundedContextId": "EP-order",
                "fields": {"description": "주문 상태"},
                "properties": [{"name": "orderId", "type": "UUID"}],
                "userStoryRefs": ["US-track-order"],
            },
        ]
    })

    assert result.valid is True


@pytest.mark.asyncio
async def test_runner_retries_with_validator_feedback(monkeypatch):
    from api.features.proposal_lifecycle.services import proposal_ai_runner
    from api.features.proposal_lifecycle.services.proposal_ai_validation import ValidationResult

    prompts = []
    outputs = iter([
        '{"bad": true}',
        '{"ok": true}',
    ])

    async def fake_run_skill_once(skill_root, skill_name, human_prompt, timeout=120, add_dirs=None):
        prompts.append(human_prompt)
        return next(outputs)

    def validator(data):
        if data.get("ok"):
            return ValidationResult(True, normalized_output=data)
        return ValidationResult(False, violations=[{"path": "result.ok", "code": "required", "message": "ok is required"}])

    monkeypatch.setattr(proposal_ai_runner, "run_skill_once", fake_run_skill_once)

    result = await proposal_ai_runner.run_validated_skill_once(
        skill_name="robo-proposal",
        prompt_builder=lambda feedback: f"prompt\n{feedback or ''}",
        validator=validator,
        proposal_id="PRO-test",
        scenario=SkillScenario.SIMPLIFIED_TACTICAL.value,
        max_retries=1,
    )

    assert result.valid is True
    assert "result.ok" in prompts[1]
