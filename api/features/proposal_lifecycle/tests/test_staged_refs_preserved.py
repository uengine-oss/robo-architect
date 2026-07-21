"""evlink SPEC2 T2-1 — 스테이지 산출물의 legacyRefs 가 수렴(consolidate) 재구성에서
떨어지지 않고 요소별로 운반되는지 검증(부정 케이스 포함)."""
from __future__ import annotations

from api.features.proposal_lifecycle.services.staged_consolidate import (
    _build_strategic,
    _build_tactical,
)

REF_A = {"nodeId": "code:x.c:fa", "role": "derived-from", "evidence": "a"}
REF_B = {"nodeId": "db:shop.t1", "role": "reads"}


def _arts():
    return {
        "DEFINE": {"contexts": [
            {"name": "배송", "purpose": "배송 관리", "legacyRefs": [REF_A, REF_B]},
            {"name": "알림", "purpose": "알림"},  # 근거 없는 컨텍스트(스킬 미확장/신규)
        ]},
        "DISCOVER": {"events": [
            {"name": "배송상태변경됨", "legacyRefs": [REF_A]},
            {"name": "알림발송됨", "legacyRefs": [{"nodeId": "code:x.c:fa"}]},  # 중복 nodeId
        ]},
        "TACTICAL": {"aggregates": [{
            "name": "배송",
            "legacyRefs": [REF_A],
            "handledCommands": [
                {"name": "배송상태변경", "legacyRefs": [REF_B]},  # 객체형 command
                "배송취소",  # 문자열형 command(구 산출물 호환)
            ],
            "createdEvents": [{"name": "배송상태변경됨", "legacyRefs": [REF_A]}],
            "invariants": ["전이 규칙 준수"],
        }]},
    }


def test_strategic_carries_refs_per_element():
    strategic = _build_strategic({"strategic": {}, "prompt": ""}, _arts())
    epics = {e["entityTitle"]: e for e in strategic["epics"]}
    assert epics["배송"]["legacyRefs"] == [REF_A, REF_B]
    assert "legacyRefs" not in epics["알림"]  # 없으면 생략 → 관문의 [] 폴백에 위임
    features = {e["entityTitle"]: e for e in strategic["features"]}
    assert features["배송 관리"]["legacyRefs"] == [REF_A, REF_B]
    # Process 는 discover 이벤트 근거의 합집합(중복 nodeId 는 1회)
    process = strategic["processes"][0]
    assert process["legacyRefs"] == [REF_A]


def test_tactical_carries_refs_including_dict_commands():
    tactical = _build_tactical(_arts())
    by_title = {t["nodeTitle"]: t for t in tactical}
    assert by_title["배송"]["legacyRefs"] == [REF_A]
    assert by_title["배송상태변경"]["legacyRefs"] == [REF_B]
    assert "legacyRefs" not in by_title["배송취소"]  # 문자열형 — 근거 자리 없음, 생략
    assert by_title["배송상태변경됨"]["legacyRefs"] == [REF_A]
    # 문자열/객체 혼용에도 명칭·참조 구조는 온전
    assert by_title["배송취소"]["aggregateId"] == by_title["배송상태변경"]["aggregateId"]


def test_no_refs_anywhere_is_safe():
    arts = {
        "DEFINE": {"contexts": [{"name": "주문", "purpose": "p"}]},
        "TACTICAL": {"aggregates": [{"name": "주문", "handledCommands": ["주문접수"],
                                     "createdEvents": ["주문접수됨"]}]},
    }
    strategic = _build_strategic({"strategic": {}, "prompt": ""}, arts)
    tactical = _build_tactical(arts)
    assert all("legacyRefs" not in e for e in strategic["epics"] + strategic["features"])
    assert all("legacyRefs" not in t for t in tactical)
