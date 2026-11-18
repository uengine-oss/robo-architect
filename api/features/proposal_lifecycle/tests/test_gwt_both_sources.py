"""B-3 ⑪ — 전술 GWT 가 있어도 Intent 의 인수조건을 **같이** 검증하고, 결과에 판정 기준 원문을 싣는다."""

from __future__ import annotations

import json
from contextlib import contextmanager

from api.features.proposal_lifecycle.services import test_runner as tr

TACTICAL = [
    {"nodeLabel": "Command", "nodeId": "cmd:Refund", "nodeTitle": "Refund",
     "gwt": [{"scenario": "정상 환불", "given": {"name": "주문 완료"}, "when": {"name": "환불 요청"},
              "then": {"name": "RefundRequested"}}]},
    {"nodeLabel": "Aggregate", "nodeId": "agg:refund", "nodeTitle": "환불 Aggregate", "changeType": "MODIFY",
     "semanticDiff": {"v": 1, "ops": [{"field": "valueObjects", "op": "obj_append", "obj_name": "PartialRefundAmount"}]}},
]
STRATEGIC = {"userStories": [{
    "tempId": "us:partial", "entityTitle": "부분 환불",
    "acceptanceCriteria": ["Given 주문 완료 When 일부 금액 환불 Then 남은 금액 유지"],
}]}


class _Res:
    def __init__(self, rec=None, rows=None):
        self._rec, self._rows = rec, rows or []

    def single(self):
        return self._rec

    def data(self):
        return self._rows


class _Sess:
    def __init__(self, graph_rows=None):
        self.graph_rows = graph_rows or []

    @contextmanager
    def __call__(self, *a, **k):
        yield self

    def run(self, q, **p):
        if "EFFECT" in q:
            return _Res(rows=self.graph_rows)
        return _Res({"tacticalDiff": json.dumps(TACTICAL, ensure_ascii=False),
                     "strategicDiff": json.dumps(STRATEGIC, ensure_ascii=False)})


def test_both_tactical_and_strategic_criteria_are_used(monkeypatch):
    monkeypatch.setattr(tr, "get_session", _Sess())
    stories = tr._fetch_acceptance_criteria("PRO-1")
    assert [s["source"] for s in stories] == ["tactical", "strategic"]
    assert stories[1]["storyId"] == "us:partial"


def test_graph_effect_stories_replace_strategic_diff_but_tactical_stays(monkeypatch):
    rows = [{"storyId": "US-9", "storyTitle": "적용된 스토리", "criteria": ["Given a When b Then c"]}]
    monkeypatch.setattr(tr, "get_session", _Sess(rows))
    stories = tr._fetch_acceptance_criteria("PRO-1")
    assert [(s["source"], s["storyId"]) for s in stories] == [("tactical", "cmd:Refund"), ("strategic", "US-9")]


def test_number_scenarios_assigns_ids_and_original_text():
    stories = tr._tag(tr._criteria_from_tactical_diff(TACTICAL), "tactical") + \
        tr._tag(tr._criteria_from_strategic_diff(STRATEGIC), "strategic")
    sc = tr.number_scenarios(stories)
    assert [s["scenarioId"] for s in sc] == ["SC-001", "SC-002"]
    assert sc[0]["criterion"] == "[정상 환불] Given 주문 완료 / When 환불 요청 / Then RefundRequested"
    assert sc[1]["criterion"].startswith("Given 주문 완료 When 일부")
    assert [s["criterionSource"] for s in sc] == ["tactical", "strategic"]


def test_prompt_carries_ids_sources_and_structural_numbering():
    stories = tr._tag(tr._criteria_from_tactical_diff(TACTICAL), "tactical") + \
        tr._tag(tr._criteria_from_strategic_diff(STRATEGIC), "strategic")
    prompt = tr._build_test_prompt("PRO-1", stories, "/wt", json.dumps(TACTICAL, ensure_ascii=False))
    assert '"scenarioId": "SC-001"' in prompt and '"scenarioId": "SC-002"' in prompt
    assert '"criterionSource": "strategic"' in prompt
    assert "SC-003 부터" in prompt


def test_annotate_attaches_criterion_to_acceptance_and_structural_items():
    stories = tr._tag(tr._criteria_from_tactical_diff(TACTICAL), "tactical") + \
        tr._tag(tr._criteria_from_strategic_diff(STRATEGIC), "strategic")
    sc = tr.number_scenarios(stories)
    result = {"items": [
        {"scenarioId": "SC-001", "category": "acceptance", "storyId": "cmd:Refund", "result": "PASS"},
        # LLM 이 번호를 바꿔 왔다 — storyId+순번으로 되찾는다.
        {"scenarioId": "SC-777", "category": "acceptance", "storyId": "us:partial", "result": "FAIL"},
        {"scenarioId": "SC-003", "category": "structural", "storyId": "agg:refund", "result": "FAIL"},
    ]}
    out = tr.annotate_criteria(result, sc, json.dumps(TACTICAL, ensure_ascii=False))
    a, b, c = out["items"]
    assert a["criterionSource"] == "tactical" and a["criterion"].startswith("[정상 환불]")
    assert b["criterionSource"] == "strategic" and "일부 금액" in b["criterion"]
    assert c["criterionSource"] == "tacticalDiff" and "PartialRefundAmount" in c["criterion"]


def test_format_criterion_handles_plain_and_odd_shapes():
    assert tr.format_criterion("  Given x  ") == "Given x"
    assert tr.format_criterion({"given": "a", "when": ["b", {"description": "c"}], "then": {"text": "d"}}) == \
        "Given a / When b, c / Then d"
    assert tr.format_criterion(3) == "3"
