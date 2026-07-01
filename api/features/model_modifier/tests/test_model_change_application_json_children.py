from __future__ import annotations

import json

from api.features.model_modifier.model_change_application import _apply_json_backed_change_tx


class _Result:
    def __init__(self, record=None):
        self._record = record

    def single(self):
        return self._record


class _Tx:
    def __init__(self, *, enumerations=None, value_objects=None):
        self.enumerations = enumerations or []
        self.value_objects = value_objects or []

    def run(self, query, **params):
        if "RETURN agg.enumerations AS enumerations" in query:
            return _Result(
                {
                    "enumerations": json.dumps(self.enumerations, ensure_ascii=False),
                    "valueObjects": json.dumps(self.value_objects, ensure_ascii=False),
                }
            )
        if "SET agg.enumerations = $enumerations" in query:
            self.enumerations = json.loads(params["enumerations"])
            self.value_objects = json.loads(params["value_objects"])
            return _Result()
        raise AssertionError(f"unexpected query: {query}")


def test_updates_enum_items_inside_aggregate_json():
    tx = _Tx(enumerations=[{"name": "OrderStatus", "items": ["PLACEMENT_PENDING"]}])

    change = {
        "action": "update",
        "targetType": "Enumeration",
        "targetId": "enum-agg-1-0",
        "targetName": "OrderStatus",
        "updates": {"itemsToAdd": ["REFUNDED"], "itemsToRemove": ["PLACEMENT_PENDING"]},
    }

    assert _apply_json_backed_change_tx(tx, change) is True
    assert tx.enumerations == [{"name": "OrderStatus", "items": ["REFUNDED"]}]
    assert change["aggregateId"] == "agg-1"


def test_creates_value_object_inside_aggregate_json():
    tx = _Tx()

    change = {
        "action": "create",
        "targetType": "ValueObject",
        "targetId": "vo-temp",
        "targetName": "Money",
        "updates": {
            "aggregateId": "agg-1",
            "fields": [{"name": "amount", "type": "BigDecimal"}, {"name": "currency", "type": "String"}],
        },
    }

    assert _apply_json_backed_change_tx(tx, change) is True
    assert tx.value_objects == [
        {
            "name": "Money",
            "alias": "Money",
            "fields": [{"name": "amount", "type": "BigDecimal"}, {"name": "currency", "type": "String"}],
        }
    ]
    assert change["targetId"] == "vo-agg-1-0"


def test_creates_value_object_field_inside_parent_value_object_json():
    tx = _Tx(value_objects=[{"name": "OrderAmount", "fields": [{"name": "amount", "type": "BigDecimal"}]}])

    change = {
        "action": "create",
        "targetType": "Property",
        "targetId": "prop-temp",
        "targetName": "taxAmount",
        "updates": {
            "parentType": "ValueObject",
            "parentId": "vo-agg-1-0",
            "name": "taxAmount",
            "type": "BigDecimal",
            "isRequired": False,
        },
    }

    assert _apply_json_backed_change_tx(tx, change) is True
    assert tx.value_objects[0]["fields"] == [
        {"name": "amount", "type": "BigDecimal"},
        {
            "name": "taxAmount",
            "type": "BigDecimal",
            "description": "",
            "isKey": False,
            "isForeignKey": False,
            "isRequired": False,
        },
    ]
