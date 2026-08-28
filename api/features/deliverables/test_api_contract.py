from __future__ import annotations

import pytest

from api.features.deliverables.api_contract import build_api_contracts, pluralize


@pytest.mark.parametrize(
    "word,expected",
    [
        ("autoDebitApplication", "autoDebitApplications"),
        ("policy", "policies"),          # 자음 + y
        ("day", "days"),                 # 모음 + y
        ("status", "statuses"),          # s
        ("catalog", "catalogs"),
        ("", ""),
    ],
)
def test_pluralize(word, expected):
    assert pluralize(word) == expected


def _tree(commands, readmodels=None):
    return {
        "id": "bc-1",
        "name": "OrderManagement",
        "displayName": "주문 관리",
        "aggregates": [{"id": "agg-1", "name": "Order", "commands": commands}],
        "readmodels": readmodels or [],
    }


def _cmd(name, category, **extra):
    return {"id": f"c-{name}", "name": name, "displayName": name, "category": category, **extra}


def test_method_and_path_by_category():
    trees = [_tree([
        _cmd("PlaceOrder", "Create"),
        _cmd("CancelOrder", "Update"),
        _cmd("ValidateOrder", "Business Logic"),
        _cmd("ReturnResult", "Process"),
    ])]
    eps = {e["commandName"]: e for e in build_api_contracts(trees)["contexts"][0]["commandEndpoints"]}

    assert (eps["PlaceOrder"]["method"], eps["PlaceOrder"]["path"]) == ("POST", "/orders")
    assert (eps["CancelOrder"]["method"], eps["CancelOrder"]["path"]) == ("PUT", "/orders/{id}")
    assert (eps["ValidateOrder"]["method"], eps["ValidateOrder"]["path"]) == ("POST", "/orders/{id}/validateOrder")
    assert (eps["ReturnResult"]["method"], eps["ReturnResult"]["path"]) == ("POST", "/orders/{id}/returnResult")


def test_external_integration_is_not_an_endpoint():
    """외부 연동 Command 는 이 시스템이 제공하는 API 가 아니다."""
    trees = [_tree([_cmd("RequestVerification", "External Integration")])]
    ep = build_api_contracts(trees)["contexts"][0]["commandEndpoints"][0]

    assert ep["direction"] == "outbound"
    assert ep["method"] == ""
    assert ep["path"] == ""
    assert build_api_contracts(trees)["summary"]["outboundCommands"] == 1


def test_unknown_category_falls_back_to_sub_resource():
    trees = [_tree([_cmd("DoSomething", "")])]
    ep = build_api_contracts(trees)["contexts"][0]["commandEndpoints"][0]

    assert (ep["method"], ep["path"]) == ("POST", "/orders/{id}/doSomething")
    assert ep["category"] == "(미지정)"


def test_colliding_paths_are_disambiguated():
    """같은 Aggregate 의 Update Command 둘은 규칙상 같은 경로가 된다."""
    trees = [_tree([_cmd("CancelOrder", "Update"), _cmd("HoldOrder", "Update")])]
    result = build_api_contracts(trees)
    paths = {e["commandName"]: e["path"] for e in result["contexts"][0]["commandEndpoints"]}

    assert paths["CancelOrder"] == "/orders/{id}/cancelOrder"
    assert paths["HoldOrder"] == "/orders/{id}/holdOrder"
    assert len(set(paths.values())) == 2
    assert result["summary"]["pathCollisionsResolved"] == 2


def test_parameters_prefer_properties_over_input_schema():
    """리뷰 §4.6 — inputSchema 만 파싱해 요청 필드가 비던 문제의 정규화."""
    cmd = _cmd(
        "PlaceOrder", "Create",
        inputSchema='{"ignored": {"type": "string"}}',
        properties=[{"name": "orderId", "type": "String", "isRequired": True, "description": "주문 번호"}],
    )
    ep = build_api_contracts([_tree([cmd])])["contexts"][0]["commandEndpoints"][0]

    assert ep["parameters"] == [
        {"name": "orderId", "type": "String", "required": True, "description": "주문 번호", "source": "properties"}
    ]


def test_parameters_fall_back_to_input_schema():
    cmd = _cmd("PlaceOrder", "Create", inputSchema='{"orderId": {"type": "string"}}')
    ep = build_api_contracts([_tree([cmd])])["contexts"][0]["commandEndpoints"][0]

    assert [(p["name"], p["type"], p["source"]) for p in ep["parameters"]] == [("orderId", "string", "inputSchema")]


def test_broken_input_schema_yields_no_parameters():
    cmd = _cmd("PlaceOrder", "Create", inputSchema="{not json")
    ep = build_api_contracts([_tree([cmd])])["contexts"][0]["commandEndpoints"][0]

    assert ep["parameters"] == []
    assert build_api_contracts([_tree([cmd])])["summary"]["commandsWithoutParameters"] == 1


def test_readmodel_query_endpoints():
    trees = [_tree([], readmodels=[
        {"id": "rm-1", "name": "OrderDetail", "isMultipleResult": "single result"},
        {"id": "rm-2", "name": "OrderHistory", "isMultipleResult": "list"},
    ])]
    qs = {q["readModelName"]: q for q in build_api_contracts(trees)["contexts"][0]["queryEndpoints"]}

    assert (qs["OrderDetail"]["method"], qs["OrderDetail"]["path"]) == ("GET", "/orderDetails/{id}")
    assert qs["OrderDetail"]["resultType"] == "단건"
    assert (qs["OrderHistory"]["method"], qs["OrderHistory"]["path"]) == ("GET", "/orderHistories")
    assert qs["OrderHistory"]["resultType"] == "목록"


def test_endpoints_are_marked_as_derived():
    """규칙으로 도출한 값이지 구현 확정이 아님을 문서가 구분할 수 있어야 한다."""
    trees = [_tree([_cmd("PlaceOrder", "Create")], readmodels=[{"id": "rm", "name": "OrderDetail"}])]
    ctx = build_api_contracts(trees)["contexts"][0]

    assert ctx["commandEndpoints"][0]["provenance"] == "derived"
    assert ctx["queryEndpoints"][0]["provenance"] == "derived"
