"""Property 정규화 — 스킬이 문자열 배열을 내도 필드가 유실되지 않아야 한다.

배경: Plan/스킬이 `["orderId"]` 같은 문자열 배열을 내는데 _create_properties 가
객체 배열만 받아 `isinstance(p, dict)` 로 전량 폐기했다. 실측(PRO-001)에서
Command 65/65 · Aggregate 13/13 이 properties 를 갖고 있었음에도 그래프의
Property 노드는 0개였다. MCP get_bc_design 이 빈 properties 를 반환하면
/robo-implement 가 빈 스텁만 스캐폴드한다.
"""
from api.features.proposal_lifecycle.services.proposal_apply import (
    _create_properties,
    _normalize_property,
)


class _FakeSession:
    """session.run(cypher, **params) 호출만 기록하는 최소 대역."""

    def __init__(self):
        self.calls = []

    def run(self, _cypher, **params):
        self.calls.append(params)
        return None


# ── _normalize_property ────────────────────────────────────────────────

def test_string_property_keeps_its_name():
    assert _normalize_property("orderId") == {"name": "orderId"}


def test_string_property_is_trimmed():
    assert _normalize_property("  orderId  ") == {"name": "orderId"}


def test_blank_string_is_dropped():
    assert _normalize_property("   ") is None


def test_object_property_passes_through_untouched():
    src = {"name": "orderId", "type": "UUID", "isKey": True}
    assert _normalize_property(src) is src


def test_object_without_name_is_dropped():
    assert _normalize_property({"type": "String"}) is None


def test_non_string_non_dict_is_dropped():
    assert _normalize_property(42) is None
    assert _normalize_property(None) is None


def test_type_is_not_invented_for_string_entries():
    """이름만 있을 때 타입·isKey 를 추론하지 않는다(없는 의미를 만들지 않는다)."""
    out = _normalize_property("orderId")
    assert "type" not in out
    assert "isKey" not in out


# ── _create_properties ─────────────────────────────────────────────────

def test_string_array_creates_property_nodes():
    """실측에서 유실됐던 형태 — 문자열 배열."""
    s = _FakeSession()
    n = _create_properties(s, "Command", "cmd-createorder", ["orderId", "actor"], "PRO-001")
    assert n == 2
    assert [c["name"] for c in s.calls] == ["orderId", "actor"]


def test_string_entries_get_safe_defaults():
    s = _FakeSession()
    _create_properties(s, "Command", "cmd-x", ["orderId"], "PRO-001")
    call = s.calls[0]
    assert call["type"] == "String"
    assert call["isKey"] is False
    assert call["isFk"] is False
    assert call["parent"] == "cmd-x"
    assert call["ptype"] == "Command"
    assert call["pid"] == "PRO-001"


def test_object_array_still_honors_declared_metadata():
    s = _FakeSession()
    _create_properties(
        s, "Aggregate", "agg-order",
        [{"name": "orderId", "type": "UUID", "isKey": True, "isRequired": True}],
        "PRO-001",
    )
    call = s.calls[0]
    assert call["type"] == "UUID"
    assert call["isKey"] is True
    assert call["isReq"] is True


def test_mixed_array_keeps_both_shapes():
    s = _FakeSession()
    n = _create_properties(
        s, "Aggregate", "agg-order",
        ["status", {"name": "orderId", "type": "UUID", "isKey": True}],
        "PRO-001",
    )
    assert n == 2
    assert [c["name"] for c in s.calls] == ["status", "orderId"]


def test_unusable_entries_are_skipped_not_fatal():
    s = _FakeSession()
    n = _create_properties(s, "Command", "cmd-x", ["ok", "", None, 7, {"type": "String"}], "PRO-001")
    assert n == 1
    assert s.calls[0]["name"] == "ok"


def test_non_list_input_is_a_noop():
    s = _FakeSession()
    assert _create_properties(s, "Command", "cmd-x", None, "PRO-001") == 0
    assert _create_properties(s, "Command", "cmd-x", "orderId", "PRO-001") == 0
    assert s.calls == []


# ── property_shape_warnings — 계약 형태 경고(실패 아님) ─────────────────

from api.features.proposal_lifecycle.services.plan_runner import (
    property_shape_warnings,
    tactical_contract_errors,
)


def _cmd(title, props):
    return {"nodeLabel": "Command", "nodeTitle": title, "properties": props}


def test_typed_object_properties_produce_no_warning():
    out = property_shape_warnings([
        _cmd("PlaceOrder", [{"name": "menuId", "type": "UUID", "isKey": False}]),
    ])
    assert out == []


def test_string_properties_are_warned_as_untyped():
    out = property_shape_warnings([_cmd("CreateOrder", ["orderId"])])
    assert len(out) == 1
    assert "type" in out[0] and "CreateOrder" in out[0]


def test_empty_properties_are_warned_as_bare_node():
    out = property_shape_warnings([_cmd("CreateOrder", [])])
    assert len(out) == 1
    assert "비어" in out[0]


def test_missing_properties_key_is_warned():
    out = property_shape_warnings([{"nodeLabel": "Aggregate", "nodeTitle": "Order"}])
    assert len(out) == 1


def test_partially_typed_properties_report_the_ratio():
    out = property_shape_warnings([
        _cmd("PlaceOrder", [{"name": "a", "type": "UUID"}, "b", "c"]),
    ])
    assert "2/3" in out[0]


def test_labels_without_domain_properties_are_ignored():
    """Invariant/UI/Policy 등은 properties 대상이 아니다."""
    out = property_shape_warnings([
        {"nodeLabel": "Invariant", "nodeTitle": "감사 추적"},
        {"nodeLabel": "Policy", "nodeTitle": "Order lifecycle"},
        {"nodeLabel": "UI", "nodeTitle": "주문 화면"},
    ])
    assert out == []


def test_warnings_do_not_raise_on_odd_input():
    assert property_shape_warnings([]) == []
    assert len(property_shape_warnings([_cmd("X", None)])) == 1


def test_plan_contract_blocks_empty_aggregate_properties():
    errors = tactical_contract_errors([
        {"nodeLabel": "Aggregate", "nodeTitle": "Order", "properties": []},
        {
            "nodeLabel": "Command", "nodeTitle": "PlaceOrder",
            "fields": {"inputSchema": {}}, "properties": [], "userStoryRefs": ["US-1"],
            "gwt": [{"scenario": "ok", "given": {"name": "g", "fieldValues": {}},
                     "when": {"name": "w", "fieldValues": {}},
                     "then": {"name": "t", "fieldValues": {}}}],
        },
    ])
    assert "Aggregate Order requires non-empty properties" in errors
