from __future__ import annotations

from api.features.deliverables.aggregate_export import build_aggregate_payloads, omit_empty


def _tree(aggregate):
    return {
        "id": "bc-1",
        "name": "OrderManagement",
        "displayName": "주문 관리",
        "aggregates": [aggregate],
    }


def _aggregate(**overrides):
    base = {
        "id": "agg-1",
        "name": "Order",
        "displayName": "주문",
        "rootEntity": "Order",
        "properties": [
            {"name": "id", "type": "String", "isKey": True, "isRequired": True,
             "displayName": "주문 번호", "description": "주문 식별자"},
            {"name": "shippingAddress", "type": "Object", "isKey": False, "isRequired": False},
        ],
        "enumerations": [{"name": "OrderStatus", "displayName": "주문 상태", "items": ["PLACED", "SHIPPED"]}],
        "valueObjects": [{
            "name": "ShippingAddress", "displayName": "배송지",
            "fields": [{"name": "zipCode", "type": "String"}, {"name": "street", "type": "String"}],
        }],
        "invariants": [{"declaration": "주문은 한 번만 접수된다."}],
        "exceptions": [],
    }
    base.update(overrides)
    return base


def test_payload_keeps_reference_template_shape():
    payload = build_aggregate_payloads([_tree(_aggregate())])["aggregates"][0]

    assert payload["id"] == "agg-1"
    assert payload["name"] == "Order"
    assert payload["displayName"] == "주문"
    assert payload["namePlural"] == "orders"
    assert payload["namePascalCase"] == "Order"
    assert payload["nameCamelCase"] == "order"
    assert payload["boundedContextId"] == "bc-1"
    assert payload["boundedContextName"] == "주문 관리"
    assert set(payload["aggregateRoot"]) == {"fieldDescriptors", "entities"}


def test_field_descriptor_maps_required_to_nullable():
    """기준 구현은 nullable 기준으로 표현하므로 isRequired 를 뒤집는다."""
    fields = build_aggregate_payloads([_tree(_aggregate())])["aggregates"][0]["aggregateRoot"]["fieldDescriptors"]
    by_name = {f["name"]: f for f in fields}

    assert by_name["id"]["isKey"] is True
    assert by_name["id"]["isNullable"] is False
    assert by_name["id"]["className"] == "String"
    assert by_name["id"]["description"] == "주문 식별자"
    assert by_name["shippingAddress"]["isNullable"] is True


def test_generic_typed_property_links_to_value_object():
    """`Object` 로만 저장된 속성을 이름이 정확히 일치하는 VO 에 연결한다."""
    result = build_aggregate_payloads([_tree(_aggregate())])
    fields = {f["name"]: f for f in result["aggregates"][0]["aggregateRoot"]["fieldDescriptors"]}

    assert fields["shippingAddress"]["className"] == "ShippingAddress"
    assert fields["shippingAddress"]["referenceClass"] == "ShippingAddress"
    assert fields["shippingAddress"]["isVO"] is True
    assert result["summary"]["resolvedReferences"] == 1


def test_generic_typed_property_without_match_is_left_alone():
    """부분 일치로 억지 연결하지 않는다 — 틀린 연결이 빈 값보다 나쁘다."""
    agg = _aggregate(properties=[{"name": "status", "type": "String", "isKey": False, "isRequired": True}])
    result = build_aggregate_payloads([_tree(agg)])
    field = result["aggregates"][0]["aggregateRoot"]["fieldDescriptors"][0]

    # 'status' → 'Status' 는 'OrderStatus' 와 일치하지 않는다.
    assert field["className"] == "String"
    assert "referenceClass" not in field
    assert result["summary"]["resolvedReferences"] == 0


def test_entities_carry_enum_and_value_object():
    entities = build_aggregate_payloads([_tree(_aggregate())])["aggregates"][0]["aggregateRoot"]["entities"]
    by_name = {e["name"]: e for e in entities}

    assert by_name["OrderStatus"]["isEnum"] is True
    assert by_name["OrderStatus"]["items"] == [
        {"name": "PLACED", "value": "PLACED"},
        {"name": "SHIPPED", "value": "SHIPPED"},
    ]
    assert by_name["ShippingAddress"]["isVO"] is True
    assert [f["name"] for f in by_name["ShippingAddress"]["fieldDescriptors"]] == ["zipCode", "street"]


def test_duplicate_fields_are_removed():
    agg = _aggregate(properties=[
        {"name": "id", "type": "String", "isKey": True, "isRequired": True},
        {"name": "id", "type": "String", "isKey": True, "isRequired": True},
        {"name": "id", "type": "Long", "isKey": True, "isRequired": True},
    ])
    fields = build_aggregate_payloads([_tree(agg)])["aggregates"][0]["aggregateRoot"]["fieldDescriptors"]

    # name::className::isKey 기준 — 타입이 다르면 남는다.
    assert [f["className"] for f in fields] == ["String", "Long"]


def test_empty_collections_are_omitted():
    agg = _aggregate(enumerations=[], valueObjects=[], invariants=[], exceptions=[])
    payload = build_aggregate_payloads([_tree(agg)])["aggregates"][0]

    assert "entities" not in payload["aggregateRoot"]
    assert "invariants" not in payload
    assert "exceptions" not in payload


def test_false_values_survive_omit_empty():
    """`isKey: false` 는 '키 아님'이라는 정보라 지우면 안 된다."""
    assert omit_empty({"isKey": False, "count": 0, "blank": "", "none": None, "empty": []}) == {
        "isKey": False,
        "count": 0,
    }


def test_summary_counts():
    summary = build_aggregate_payloads([_tree(_aggregate()), _tree(_aggregate())])["summary"]

    assert summary["aggregates"] == 2
    assert summary["fields"] == 4
    assert summary["resolvedReferences"] == 2


def test_no_aggregates_yields_empty_export():
    result = build_aggregate_payloads([{"id": "bc-1", "name": "Empty", "aggregates": []}])

    assert result["aggregates"] == []
    assert result["summary"]["aggregates"] == 0
