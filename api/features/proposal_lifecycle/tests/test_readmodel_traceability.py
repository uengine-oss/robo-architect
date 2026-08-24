"""ReadModel 도 어느 UserStory 를 충족하는지 밝혀야 한다.

실측(PRO-002 accept 후): "설계에 반영되지 않은 User Story 28건" 중 **25건이
조회·추적성**(search/view/track/review/export)이었다. 판정은 느슨한 편인데도
(Aggregate·Command·Event·Policy·ReadModel 중 하나라도 연결되면 반영으로 간주)
남았다.

원인은 계약 구멍이다 — `userStoryRefs` 를 Command 에만 요구했다. 조회 스토리는
Command 없이 ReadModel+UI 로 충족하는 것이 정상 설계인데, 그 연결을 밝힐 의무가
없으니 모델이 채우지 않았고 `IMPLEMENTS` 가 생기지 않았다. 저장 측
(`proposal_apply._link_user_stories`)은 라벨을 가리지 않으므로 데이터만 오면 된다.
"""
from api.features.proposal_lifecycle.services.plan_runner import (
    readmodel_traceability_errors,
    tactical_contract_errors,
)


def _rm(title, refs=None):
    item = {"nodeLabel": "ReadModel", "nodeTitle": title}
    if refs is not None:
        item["userStoryRefs"] = refs
    return item


def _cmd(title):
    return {
        "nodeLabel": "Command", "nodeTitle": title,
        "fields": {"inputSchema": {}}, "properties": [],
        "userStoryRefs": ["US-1"],
        "gwt": [{"scenario": "s",
                 "given": {"name": "g", "fieldValues": {}},
                 "when": {"name": "w", "fieldValues": {}},
                 "then": {"name": "t", "fieldValues": {}}}],
    }


def test_readmodel_with_refs_passes():
    assert readmodel_traceability_errors([_rm("OrderSearchView", ["US-order-search"])]) == []


def test_readmodel_without_refs_is_reported():
    out = readmodel_traceability_errors([_rm("OrderSearchView", [])])
    assert len(out) == 1 and "OrderSearchView" in out[0]


def test_readmodel_missing_key_is_reported():
    out = readmodel_traceability_errors([_rm("OrderSearchView")])
    assert len(out) == 1


def test_multiple_readmodels_each_reported():
    out = readmodel_traceability_errors([_rm("A", []), _rm("B", ["US-1"]), _rm("C")])
    assert len(out) == 2
    assert any("A" in e for e in out) and any("C" in e for e in out)


def test_other_labels_are_ignored():
    """Command/Event/Aggregate 는 이 검사의 대상이 아니다."""
    items = [
        {"nodeLabel": "Command", "nodeTitle": "PlaceOrder"},
        {"nodeLabel": "Event", "nodeTitle": "OrderPlaced"},
        {"nodeLabel": "Aggregate", "nodeTitle": "Order"},
        {"nodeLabel": "UI", "nodeTitle": "주문화면"},
    ]
    assert readmodel_traceability_errors(items) == []


def test_empty_input_is_safe():
    assert readmodel_traceability_errors([]) == []


def test_contract_check_still_focuses_on_commands():
    """ReadModel 검사는 별도 함수다 — 기존 Command 계약은 그대로."""
    assert tactical_contract_errors([_cmd("PlaceOrder")]) == []
    assert tactical_contract_errors([_rm("OnlyReadModel", ["US-1"])]) == [
        "tacticalDiff contains no Command"
    ]
