"""evlink SPEC2 T3 — ODA 저장 경로가 요소별 legacyRefs 관문을 지나는지 검증.

ODA 실생성은 표준 지식베이스($ODA_KNOWLEDGE_ROOT: sid/ + repo/usecase-library/)가 있는
환경에서만 가능하므로, 이 환경에서는 저장 경로의 관문 배선을 단위로 잠근다.
"""
from __future__ import annotations

import json

from api.features.proposal_lifecycle.services import oda_runner


def test_save_intent_passes_refs_gate(monkeypatch):
    seen = {}

    def fake_enforce(proposal_id, strategic_diff=None, tactical_diff=None):
        seen["intent"] = (proposal_id, strategic_diff, tactical_diff)
        # 관문이 요소를 제자리 정규화한다는 계약 재현
        if isinstance(strategic_diff, dict):
            for entries in strategic_diff.values():
                if isinstance(entries, list):
                    for e in entries:
                        if isinstance(e, dict) and not isinstance(e.get("legacyRefs"), list):
                            e["legacyRefs"] = []
        return []

    monkeypatch.setattr(
        "api.features.proposal_lifecycle.services.legacy_element_refs.enforce_proposal_refs",
        fake_enforce,
    )
    captured = {}
    monkeypatch.setattr(oda_runner, "get_session", lambda: _FakeSession(captured))

    sd = {"epics": [{"tempId": "EP-1", "entityTitle": "요금제"}]}
    oda_runner._save_intent("PRO-X", {"strategicDiff": sd, "journeys": [],
                                      "alignment": {}, "conformance": {}})

    assert seen["intent"][0] == "PRO-X"
    assert seen["intent"][1] is sd                      # 관문이 실제 diff 객체를 받았다
    assert sd["epics"][0]["legacyRefs"] == []           # 정규화 결과가 저장 대상에 반영
    assert json.loads(captured["params"]["sd"])["epics"][0]["legacyRefs"] == []


def test_save_plan_passes_refs_gate(monkeypatch):
    seen = {}

    def fake_enforce(proposal_id, strategic_diff=None, tactical_diff=None):
        seen["plan"] = (proposal_id, tactical_diff)
        return []

    monkeypatch.setattr(
        "api.features.proposal_lifecycle.services.legacy_element_refs.enforce_proposal_refs",
        fake_enforce,
    )
    monkeypatch.setattr(oda_runner, "get_session", lambda: _FakeSession({}))

    td = [{"nodeId": "AGG-1", "nodeLabel": "Aggregate", "nodeTitle": "Subscription"}]
    oda_runner._save_plan("PRO-Y", {"tacticalDiff": td, "artifacts": {}, "conformance": {}})

    assert seen["plan"] == ("PRO-Y", td)


class _FakeSession:
    """with get_session() as s: s.run(...) 만 흉내내는 최소 더블."""

    def __init__(self, captured):
        self._captured = captured

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def run(self, query, **params):
        self._captured["query"] = query
        self._captured["params"] = params
        return None
