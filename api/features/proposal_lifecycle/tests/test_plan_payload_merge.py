"""Plan 산출물이 여러 JSON 블록에 흩어져 나올 때의 보정.

실측(PRO-002): 파싱은 성공했는데 `rawItemCount: 0` — 즉 `tacticalDiff` 가 비어
있었다. extract_json 은 후보 중 **가장 큰 하나**만 돌려주므로, 모델이
tacticalDiff 와 implementationPlan 을 별도 ```json 블록으로 내면 한쪽이 통째로
버려진다. _merge_plan_payload 는 빠진 최상위 키만 다른 후보에서 채운다.
"""
import json

from api.features.proposal_lifecycle.services.plan_runner import _merge_plan_payload


def _fence(obj):
    return "```json\n" + json.dumps(obj, ensure_ascii=False) + "\n```\n"


def test_single_block_is_returned_as_is():
    payload = {"tacticalDiff": [{"nodeLabel": "Command"}], "implementationPlan": {"v": 1}}
    assert _merge_plan_payload(_fence(payload)) == payload


def test_split_blocks_are_merged():
    tac = {"tacticalDiff": [{"nodeLabel": "Command", "nodeTitle": "PlaceOrder"}] * 5}
    plan = {"implementationPlan": {"messagingChannel": "Kafka", "version": 1}}
    out = _merge_plan_payload("[전술] narration\n" + _fence(tac) + "설명\n" + _fence(plan))
    assert len(out["tacticalDiff"]) == 5
    assert out["implementationPlan"]["messagingChannel"] == "Kafka"


def test_split_blocks_merged_regardless_of_order():
    """작은 블록이 먼저 나와도 결과는 같다."""
    plan = {"implementationPlan": {"version": 1}}
    tac = {"tacticalDiff": [{"nodeLabel": "Command"}] * 10}
    out = _merge_plan_payload(_fence(plan) + _fence(tac))
    assert len(out["tacticalDiff"]) == 10
    assert out["implementationPlan"] == {"version": 1}


def test_existing_key_is_not_overwritten():
    """이미 값이 있으면 다른 블록이 덮어쓰지 않는다."""
    full = {"tacticalDiff": [{"nodeLabel": "Command"}], "implementationPlan": {"v": 1}}
    other = {"tacticalDiff": [{"nodeLabel": "Event"}] * 9}
    out = _merge_plan_payload(_fence(full) + _fence(other))
    assert out["tacticalDiff"] == [{"nodeLabel": "Command"}]


def test_empty_value_is_treated_as_missing():
    """빈 배열은 '없음'으로 보고 다른 후보에서 채운다."""
    empty = {"tacticalDiff": [], "implementationPlan": {"v": 1}, "pad": "x" * 400}
    tac = {"tacticalDiff": [{"nodeLabel": "Command"}]}
    out = _merge_plan_payload(_fence(empty) + _fence(tac))
    assert out["tacticalDiff"] == [{"nodeLabel": "Command"}]


def test_no_json_returns_none():
    assert _merge_plan_payload("설명만 있고 JSON 은 없다") is None
    assert _merge_plan_payload("") is None


def test_narration_with_odd_quote_still_works():
    """파서 회귀(#26)와 결합해도 동작한다."""
    payload = {"tacticalDiff": [{"nodeLabel": "Command"}], "implementationPlan": {"v": 1}}
    raw = '[전술] 인용부호가 하나: "미완결\n' + _fence(payload)
    assert _merge_plan_payload(raw) == payload


# ── 봉투 미착용 방어 (실측 PRO-002) ──────────────────────────────────

def test_envelopeless_plan_body_is_wrapped():
    """모델이 implementationPlan 본문만 최상위로 낸 경우.

    실측 dataKeys: ['architectureDecisions','constitutionGaps','interContextIntegrations',
    'messagingChannel','serviceDevEnvironments','tacticalSummary','version']
    그대로 두면 계획까지 버려져 진단이 흐려진다.
    """
    body = {"version": 1, "architectureDecisions": [{"aspect": "INGRESS"}],
            "messagingChannel": "Kafka", "constitutionGaps": [],
            "serviceDevEnvironments": [{"service": "Ordering"}]}
    out = _merge_plan_payload(_fence(body))
    assert out["implementationPlan"]["messagingChannel"] == "Kafka"
    assert not out.get("tacticalDiff")   # 없는 값을 만들어내지는 않는다


def test_proper_envelope_is_not_rewrapped():
    payload = {"tacticalDiff": [{"nodeLabel": "Command"}],
               "implementationPlan": {"messagingChannel": "Kafka",
                                      "architectureDecisions": []}}
    out = _merge_plan_payload(_fence(payload))
    assert out["tacticalDiff"] == [{"nodeLabel": "Command"}]
    assert out["implementationPlan"]["messagingChannel"] == "Kafka"


def test_unrelated_object_is_not_wrapped():
    """마커가 부족한 객체는 계획 본문으로 오인하지 않는다."""
    obj = {"version": 1, "note": "그냥 설명", "pad": "x" * 200}
    out = _merge_plan_payload(_fence(obj))
    assert "implementationPlan" not in out


def test_envelopeless_body_plus_separate_tactical_block():
    """본문만 낸 뒤 tacticalDiff 를 별도 블록으로 낸 혼합 케이스."""
    body = {"version": 1, "architectureDecisions": [], "messagingChannel": "Kafka",
            "serviceDevEnvironments": [], "constitutionGaps": []}
    tac = {"tacticalDiff": [{"nodeLabel": "Command"}] * 3}
    out = _merge_plan_payload(_fence(body) + _fence(tac))
    assert len(out["tacticalDiff"]) == 3
    assert out["implementationPlan"]["messagingChannel"] == "Kafka"
