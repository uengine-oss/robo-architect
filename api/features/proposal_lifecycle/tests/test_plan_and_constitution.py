"""041 — Constitution + Plan stage 단위 테스트 (Neo4j 불필요, 순수 로직)."""

import json

from api.features.proposal_lifecycle.proposal_contracts import (
    ImplementationPlan, ArchitectureDecision, ProposalResponse,
    REQUIRED_ARCHITECTURE_ASPECTS, MICROSERVICE_REQUIRED_ASPECTS,
    constitution_hash, InterContextIntegration, ServiceDevEnvironment,
)


def _plan_with(aspects, **kw):
    return ImplementationPlan(
        architectureDecisions=[ArchitectureDecision(aspect=a, decision="x") for a in aspects],
        **kw,
    )


def test_constitution_hash_stable_and_differs():
    assert constitution_hash(None) is None
    assert constitution_hash("a") == constitution_hash("a")
    assert constitution_hash("a") != constitution_hash("b")


def test_monolith_plan_complete_with_five_aspects():
    plan = _plan_with(REQUIRED_ARCHITECTURE_ASPECTS)
    assert plan.is_complete("MONOLITH", 1) is True


def test_microservices_requires_extra_aspects():
    plan = _plan_with(REQUIRED_ARCHITECTURE_ASPECTS)
    # 5개만으로는 마이크로서비스+다수컨텍스트 완전성 미충족 (SC-003)
    assert plan.is_complete("MICROSERVICES", 3) is False
    full = _plan_with(
        REQUIRED_ARCHITECTURE_ASPECTS + MICROSERVICE_REQUIRED_ASPECTS,
        messagingChannel="Kafka",
        interContextIntegrations=[
            InterContextIntegration(fromContext="Ordering", toContext="Payment",
                                    message="ChargePayment", kind="COMMAND", sync=True)
        ],
        serviceDevEnvironments=[
            ServiceDevEnvironment(service="Ordering", dependencies=["kafka"])
        ],
    )
    assert full.is_complete("MICROSERVICES", 3) is True


def test_gap_counts_as_covered():
    plan = _plan_with([a for a in REQUIRED_ARCHITECTURE_ASPECTS if a != "INGRESS"],
                      constitutionGaps=["INGRESS"])
    assert plan.is_complete("MONOLITH", 1) is True


def _node(**over):
    base = {
        "id": "PRO-001", "title": "t", "originalPrompt": "p", "author": "a",
        "status": "DRAFT",
    }
    base.update(over)
    return base


def test_plan_stale_on_constitution_hash_mismatch():
    plan = _plan_with(REQUIRED_ARCHITECTURE_ASPECTS)
    plan_dict = json.loads(plan.model_dump_json())
    plan_dict["constitutionHash"] = "OLD"
    node = _node(
        implementationPlan=json.dumps(plan_dict),
        constitutionHash="NEW",
        strategicDiff=json.dumps({"version": 1}),
    )
    resp = ProposalResponse.from_neo4j(node, [])
    assert resp.planStale is True


def test_plan_not_stale_when_hash_and_version_match():
    plan = _plan_with(REQUIRED_ARCHITECTURE_ASPECTS, strategicVersion=2)
    plan_dict = json.loads(plan.model_dump_json())
    plan_dict["constitutionHash"] = "H"
    node = _node(
        implementationPlan=json.dumps(plan_dict),
        constitutionHash="H",
        strategicDiff=json.dumps({"version": 2}),
    )
    resp = ProposalResponse.from_neo4j(node, [])
    assert resp.planStale is False


def test_plan_stale_when_strategic_version_advances():
    plan = _plan_with(REQUIRED_ARCHITECTURE_ASPECTS, strategicVersion=1)
    plan_dict = json.loads(plan.model_dump_json())
    plan_dict["constitutionHash"] = "H"
    node = _node(
        implementationPlan=json.dumps(plan_dict),
        constitutionHash="H",
        strategicDiff=json.dumps({"version": 3}),  # intent 재실행으로 버전 상승
    )
    resp = ProposalResponse.from_neo4j(node, [])
    assert resp.planStale is True


def test_plan_draft_is_preserved_without_becoming_confirmed_plan():
    draft = {
        "implementationPlan": json.loads(_plan_with(REQUIRED_ARCHITECTURE_ASPECTS).model_dump_json()),
        "tacticalDiff": [{"nodeId": "AGG-cart", "nodeLabel": "Aggregate", "nodeTitle": "Cart"}],
        "impactMap": [],
        "confirmed": False,
    }
    resp = ProposalResponse.from_neo4j(_node(planDraft=json.dumps(draft)), [])
    assert resp.implementationPlan is None
    assert resp.planDraft["tacticalDiff"][0]["nodeTitle"] == "Cart"


def test_plan_tactical_normalization_recovers_required_display_fields():
    from api.features.proposal_lifecycle.services.plan_runner import normalize_tactical_diff

    raw = [
        {"type": "aggregate", "name": "Cart"},
        {"entityType": "command", "entityTitle": "AddItemToCart", "op": "CREATE"},
        {"label": "event", "title": "ItemAddedToCart", "impactLevel": "none"},
    ]

    normalized = normalize_tactical_diff(raw)

    assert [item["nodeLabel"] for item in normalized] == ["Aggregate", "Command", "Event"]
    assert [item["nodeTitle"] for item in normalized] == ["Cart", "AddItemToCart", "ItemAddedToCart"]
    assert all(item["nodeId"] and item["nodeId"] != "undefined:undefined" for item in normalized)


def test_tactical_contract_rejects_legacy_plan_shape():
    from api.features.proposal_lifecycle.services.plan_runner import normalize_tactical_diff
    from api.features.proposal_lifecycle.services.tactical_contract import (
        validate_tactical_diff_contract,
    )

    malformed = normalize_tactical_diff([
        {
            "op": "CREATE",
            "entityType": "aggregate",
            "tempId": "AGG-order",
            "entityTitle": "Order",
            "boundedContext": "Order",
            "fields": {"description": {"after": "Order aggregate"}},
        },
        {
            "op": "CREATE",
            "entityType": "command",
            "tempId": "CMD-place-order",
            "entityTitle": "PlaceOrder",
            "aggregate": "AGG-order",
            "traces": ["US-place-order"],
            "fields": {"parameters": {"after": "cartId, customerId"}},
        },
        {
            "op": "CREATE",
            "entityType": "event",
            "tempId": "EVT-order-placed",
            "entityTitle": "OrderPlaced",
            "emittedBy": "CMD-place-order",
            "fields": {"payload": {"after": "orderId, items[productId,quantity]" }},
        },
    ])

    violations = validate_tactical_diff_contract(malformed)
    codes = {v["code"] for v in violations}
    paths = " ".join(v["path"] for v in violations)

    assert "legacy_alias" in codes
    assert "required" in codes
    assert "schema_object_required" in codes
    assert ".boundedContext" in paths
    assert ".aggregate" in paths
    assert ".emittedBy" in paths


def test_tactical_contract_accepts_canonical_order_preview_shape():
    from api.features.proposal_lifecycle.services.tactical_contract import (
        validate_tactical_diff_contract,
    )

    tactical = [
        {
            "nodeId": "AGG-order",
            "nodeLabel": "Aggregate",
            "nodeTitle": "Order",
            "changeType": "CREATE",
            "impactLevel": "MEDIUM",
            "boundedContextId": "EP-order",
            "fields": {"rootEntity": "Order", "description": "Order aggregate"},
            "properties": [
                {"name": "orderId", "type": "UUID", "isKey": True, "isRequired": True},
                {"name": "customerId", "type": "UUID", "isRequired": True},
                {"name": "status", "type": "OrderStatus", "isRequired": True},
                {"name": "totalAmount", "type": "Money", "isRequired": True},
                {"name": "placedAt", "type": "LocalDateTime", "isRequired": True},
            ],
            "semanticDiff": {"v": 1, "ops": [
                {"field": "valueObjects", "op": "obj_append", "obj_name": "Money",
                 "obj_data": {"name": "Money", "fields": [{"name": "amount", "type": "BigDecimal"}]}},
                {"field": "enumerations", "op": "obj_append", "obj_name": "OrderStatus",
                 "obj_data": {"name": "OrderStatus", "items": ["PLACED", "CANCELLED"]}},
            ]},
        },
        {
            "nodeId": "CMD-place-order",
            "nodeLabel": "Command",
            "nodeTitle": "PlaceOrder",
            "changeType": "CREATE",
            "impactLevel": "MEDIUM",
            "aggregateId": "AGG-order",
            "fields": {
                "actor": "customer",
                "category": "Create",
                "inputSchema": {"customerId": "UUID"},
            },
            "properties": [{"name": "customerId", "type": "UUID", "isRequired": True}],
            "userStoryRefs": ["US-place-order"],
            "gwt": [{
                "scenario": "normal order",
                "given": {"name": "Aggregate: Order", "fieldValues": {"status": "NONE"}},
                "when": {"name": "Command: PlaceOrder", "fieldValues": {"customerId": "c-1"}},
                "then": {"name": "Event: OrderPlaced", "fieldValues": {"status": "PLACED"}},
            }],
        },
        {
            "nodeId": "EVT-order-placed",
            "nodeLabel": "Event",
            "nodeTitle": "OrderPlaced",
            "changeType": "CREATE",
            "impactLevel": "MEDIUM",
            "commandId": "CMD-place-order",
            "fields": {"version": "1.0.0", "payload": {"orderId": "UUID", "status": "OrderStatus"}},
            "properties": [
                {"name": "orderId", "type": "UUID", "isKey": True, "isRequired": True},
                {"name": "status", "type": "OrderStatus", "isRequired": True},
            ],
        },
        {
            "nodeId": "RM-order-status",
            "nodeLabel": "ReadModel",
            "nodeTitle": "OrderStatusView",
            "changeType": "CREATE",
            "impactLevel": "LOW",
            "boundedContextId": "EP-order",
            "fields": {"actor": "customer", "isMultipleResult": False},
            "properties": [
                {"name": "orderId", "type": "UUID", "isKey": True, "isRequired": True},
                {"name": "status", "type": "OrderStatus", "isRequired": True},
            ],
            "userStoryRefs": ["US-track-order"],
        },
        {
            "nodeId": "POL-order-status-projection",
            "nodeLabel": "Policy",
            "nodeTitle": "주문 상태 조회 모델 갱신",
            "changeType": "CREATE",
            "impactLevel": "LOW",
            "boundedContextId": "EP-order",
            "triggerEventId": "EVT-order-placed",
            "invokeCommandId": "CMD-place-order",
            "fields": {"description": "Update read model", "condition": "OrderPlaced"},
        },
    ]

    assert validate_tactical_diff_contract(tactical) == []
