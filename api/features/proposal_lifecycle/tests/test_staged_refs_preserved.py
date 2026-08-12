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
                {
                    "name": "배송상태변경", "legacyRefs": [REF_B],
                    "fields": {"inputSchema": {"status": "String"}},
                    "properties": [{"name": "status", "type": "String"}],
                    "userStoryRefs": ["us:배송상태변경"],
                    "gwt": [{
                        "scenario": "배송 상태 정상 변경",
                        "given": {"name": "Aggregate: 배송", "fieldValues": {"status": "READY"}},
                        "when": {"name": "Command: 배송상태변경", "fieldValues": {"status": "SHIPPED"}},
                        "then": {"name": "Event: 배송상태변경됨", "fieldValues": {"status": "SHIPPED"}},
                    }],
                },
            ],
            "createdEvents": [{
                "name": "배송상태변경됨", "legacyRefs": [REF_A],
                "fields": {"payload": {"status": "String"}},
                "properties": [{"name": "status", "type": "String"}],
            }],
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
    assert by_title["배송상태변경됨"]["legacyRefs"] == [REF_A]
    command = by_title["배송상태변경"]
    assert command["fields"]["inputSchema"] == {"status": "String"}
    assert command["properties"] == [{"name": "status", "type": "String"}]
    assert command["userStoryRefs"] == ["us:배송상태변경"]
    assert command["gwt"][0]["then"]["fieldValues"] == {"status": "SHIPPED"}
    assert by_title["배송상태변경됨"]["fields"]["payload"] == {"status": "String"}


def test_no_refs_anywhere_is_safe():
    arts = {
        "DEFINE": {"contexts": [{"name": "주문", "purpose": "p"}]},
        "TACTICAL": {"aggregates": [{"name": "주문", "handledCommands": [{
                                         "name": "주문접수", "userStoryRefs": ["us:order"],
                                         "gwt": [{
                                             "scenario": "접수", "given": {"name": "입력", "fieldValues": {}},
                                             "when": {"name": "접수", "fieldValues": {}},
                                             "then": {"name": "완료", "fieldValues": {}},
                                         }],
                                     }],
                                     "createdEvents": ["주문접수됨"]}]},
    }
    strategic = _build_strategic({"strategic": {}, "prompt": ""}, arts)
    tactical = _build_tactical(arts)
    assert all("legacyRefs" not in e for e in strategic["epics"] + strategic["features"])
    assert all("legacyRefs" not in t for t in tactical)


def test_define_user_stories_become_strategic_ids_used_by_commands():
    arts = {
        "DEFINE": {"contexts": [{
            "name": "쿠폰 할인", "purpose": "할인을 계산한다",
            "userStories": [{
                "id": "us:calculate-discount", "role": "주문자", "action": "할인을 계산한다",
                "benefit": "결제 금액을 안다", "acceptanceCriteria": ["빈 쿠폰이면 0"],
                "legacyRefs": [{"nodeId": "code:x.c:calc"}],
            }],
        }]},
        "TACTICAL": {"aggregates": [{
            "name": "Discount", "bcName": "쿠폰 할인", "invariants": ["a", "b"],
            "handledCommands": [{
                "name": "Calculate", "userStoryRefs": ["us:calculate-discount"],
                "gwt": [{
                    "scenario": "empty", "given": {"name": "input", "fieldValues": {}},
                    "when": {"name": "calculate", "fieldValues": {}},
                    "then": {"name": "return", "fieldValues": {"value": 0}},
                }], "legacyRefs": [{"nodeId": "code:x.c:calc"}],
            }], "createdEvents": [],
        }]},
    }
    state = {"strategic": {}, "prompt": "", "stageArtifacts": arts}

    strategic = _build_strategic(state, arts)
    tactical = _build_tactical(arts)

    assert strategic["userStories"][0]["tempId"] == "us:calculate-discount"
    assert strategic["userStories"][0]["acceptanceCriteria"] == ["빈 쿠폰이면 0"]
    command = next(item for item in tactical if item["nodeLabel"] == "Command")
    assert command["userStoryRefs"] == ["us:calculate-discount"]
