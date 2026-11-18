"""B-4 ⑧ / D-5 ⑰ ③ — 데이터 오버레이(탐색기·Data 미리보기)에 UI · ReadModel · Policy 를 더한다.

예전 overlay_apply 는 신규 항목 중 Aggregate/Command/Event 만 트리에 꽂아, 제안이 만든 UI 는
Accept 전 미리보기에 아예 없었다. 또 BC 를 거르지 않아, 전체 미리보기(BC 마다 투영)에서
신규 Aggregate 가 모든 BC 밑에 똑같이 나타날 수 있었다.
"""

from __future__ import annotations

from api.features.proposal_lifecycle.services.overlay_apply import (
    SOURCE_LIVE,
    SOURCE_MODIFIED,
    SOURCE_TEMPORARY,
    apply_data_overlay,
    temp_id,
)


def _tree(bc="BC-a"):
    return {
        "id": bc, "name": bc, "type": "BoundedContext",
        "aggregates": [
            {"id": f"AGG-{bc}", "name": "주문", "type": "Aggregate", "commands": [], "events": []},
        ],
        "userStories": [], "policies": [],
        "readmodels": [{"id": "RM-live", "name": "주문목록"}],
        "uis": [{"id": "UI-live", "name": "주문 화면"}],
    }


def _tactical():
    return [
        {"nodeId": None, "nodeLabel": "UI", "nodeTitle": "환불 신청 화면", "changeType": "CREATE",
         "boundedContextId": "BC-a", "description": "환불 사유를 입력한다", "commandId": "CMD-1"},
        {"nodeId": None, "nodeLabel": "ReadModel", "nodeTitle": "환불 내역", "changeType": "CREATE",
         "boundedContextId": "BC-a"},
        {"nodeId": None, "nodeLabel": "Policy", "nodeTitle": "환불 시 포인트 회수", "changeType": "CREATE",
         "boundedContextId": "BC-a", "triggerEventId": "EVT-1", "invokeCommandId": "CMD-2"},
        {"nodeId": None, "nodeLabel": "Aggregate", "nodeTitle": "배송", "changeType": "CREATE",
         "boundedContextId": "BC-b"},
        {"nodeId": None, "nodeLabel": "Command", "nodeTitle": "배송시작", "changeType": "CREATE",
         "aggregateId": "AGG-BC-b"},
        {"nodeId": "UI-live", "nodeLabel": "UI", "changeType": "MODIFY",
         "fields": {"description": {"after": "바뀐 설명"}}},
    ]


def test_create_ui_readmodel_policy_land_in_bc_lists():
    tree, meta = apply_data_overlay(_tree("BC-a"), "PRO-1", _tactical())
    ui = next(u for u in tree["uis"] if u["id"] == temp_id("PRO-1", 0))
    assert ui["source"] == SOURCE_TEMPORARY and ui["badge"] == "신규"
    assert ui["description"] == "환불 사유를 입력한다"
    assert ui["attachedToId"] == "CMD-1"
    rm = next(r for r in tree["readmodels"] if r["id"] == temp_id("PRO-1", 1))
    assert rm["source"] == SOURCE_TEMPORARY
    pol = next(p for p in tree["policies"] if p["id"] == temp_id("PRO-1", 2))
    assert pol["triggerEventId"] == "EVT-1" and pol["invokeCommandId"] == "CMD-2"
    ids = {m["nodeId"] for m in meta if m["source"] == SOURCE_TEMPORARY}
    assert {temp_id("PRO-1", 0), temp_id("PRO-1", 1), temp_id("PRO-1", 2)} <= ids


def test_live_bc_lists_are_tagged_and_modify_applies():
    tree, _ = apply_data_overlay(_tree("BC-a"), "PRO-1", _tactical())
    rm_live = next(r for r in tree["readmodels"] if r["id"] == "RM-live")
    assert rm_live["source"] == SOURCE_LIVE
    ui_live = next(u for u in tree["uis"] if u["id"] == "UI-live")
    assert ui_live["source"] == SOURCE_MODIFIED and ui_live["description"] == "바뀐 설명"


def test_other_bc_items_do_not_leak():
    tree_a, _ = apply_data_overlay(_tree("BC-a"), "PRO-1", _tactical())
    assert not any(a["name"] == "배송" for a in tree_a["aggregates"])
    # aggregateId 가 이 트리에 없는 Command 는 첫 Aggregate 에 엉뚱하게 붙지 않는다
    assert not any(c["name"] == "배송시작" for a in tree_a["aggregates"] for c in a.get("commands", []))

    tree_b, _ = apply_data_overlay(_tree("BC-b"), "PRO-1", _tactical())
    assert any(a["name"] == "배송" for a in tree_b["aggregates"])
    agg_b = next(a for a in tree_b["aggregates"] if a["id"] == "AGG-BC-b")
    assert any(c["name"] == "배송시작" for c in agg_b["commands"])
    # BC-a 소속 UI 는 BC-b 에 없다
    assert not any(u.get("name") == "환불 신청 화면" for u in tree_b["uis"])
