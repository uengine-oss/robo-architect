"""`fetch_classifier_view` 회귀 테스트.

이 함수는 두 가지로 고장나 있었고, 둘 다 **오류를 내지 않는 고장**이었다.

1. 관계 타입 제한이 없는 `(u:UI)<-[*1..30]-(c:Command)` 를 실패 UI 마다 돌았다.
   `/failures` 가 이 경로를 타는 순간 백엔드가 통째로 멈췄다.
2. `UNWIND` 로 펼친 스트림에 `WITH uid, c LIMIT 1` 을 걸어, id 를 몇 개 넘기든
   "스토리보드 보관됨" 판정을 받을 수 있는 UI 가 **최대 한 건**이었다.

그래서 테스트도 두 가지를 잰다 — 무거운 패턴을 다시 쓰지 않는 것, 그리고
판정이 **넘긴 id 전부**에 대해 나오는 것.
"""
from __future__ import annotations

import re
from unittest.mock import patch

from api.features.figma_binding import repository


class _FakeResult:
    def __init__(self, data):
        self._data = data

    def data(self):
        return self._data


class _FakeSession:
    """질의 텍스트로 응답을 고르는 세션. 오간 질의를 전부 기록한다."""

    def __init__(self, present_ids, archived_command_ids):
        self.present_ids = set(present_ids)
        self.archived_command_ids = list(archived_command_ids)
        self.queries: list[str] = []

    def run(self, query, **params):
        self.queries.append(query)
        if "StoryboardPageMapping" in query:
            return _FakeResult([{"commandId": c} for c in self.archived_command_ids])
        ids = params.get("ids", [])
        return _FakeResult(
            [{"id": i, "present": i in self.present_ids} for i in ids]
        )

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def _run(ui_ids, present_ids, archived_command_ids, owner_of):
    session = _FakeSession(present_ids, archived_command_ids)
    seen_entry_args = []

    def fake_resolve(uid, entry_commands=None):
        seen_entry_args.append(entry_commands)
        return owner_of.get(uid)

    with patch.object(repository, "get_session", return_value=session),          patch(
             "api.features.figma_binding.storyboard_resolver.resolve_storyboard_for_ui",
             side_effect=fake_resolve,
         ),          patch(
             "api.features.figma_binding.storyboard_resolver.list_entry_commands",
             return_value=[{"id": "cmd-A"}, {"id": "cmd-B"}],
         ):
        out = repository.fetch_classifier_view(ui_ids)
    return out, session, seen_entry_args


def test_archived_verdict_is_per_ui_not_just_the_first():
    """예전 `LIMIT 1` 은 한 건만 판정했다. 셋을 넘기면 셋 다 나와야 한다."""
    out, _session, _ = _run(
        ui_ids=["ui-1", "ui-2", "ui-3"],
        present_ids=["ui-1", "ui-2", "ui-3"],
        archived_command_ids=["cmd-A"],
        owner_of={"ui-1": "cmd-A", "ui-2": "cmd-A", "ui-3": "cmd-B"},
    )
    assert out["storyboard_archived"] == {
        "ui-1": True,
        "ui-2": True,
        "ui-3": False,
    }


def test_no_unbounded_variable_length_pattern_is_issued():
    """관계 타입 제한 없는 가변 길이 패턴을 다시 쓰지 않는다."""
    _out, session, _ = _run(
        ui_ids=["ui-1"],
        present_ids=["ui-1"],
        archived_command_ids=["cmd-A"],
        owner_of={"ui-1": "cmd-A"},
    )
    for q in session.queries:
        assert not re.search(r"\[\s*\*\s*\d", q), f"타입 없는 가변 길이 패턴: {q}"
        assert "*1..30" not in q


def test_missing_ui_is_not_asked_about():
    """사라진 UI 는 분류기가 앞 단계에서 잡는다 — 탐색까지 갈 이유가 없다."""
    out, _session, seen = _run(
        ui_ids=["ui-1", "gone"],
        present_ids=["ui-1"],
        archived_command_ids=["cmd-A"],
        owner_of={"ui-1": "cmd-A"},
    )
    assert out["ui_present"] == {"ui-1": True, "gone": False}
    assert "gone" not in out["storyboard_archived"]
    assert len(seen) == 1


def test_entry_command_list_is_fetched_once_and_shared():
    """UI 마다 entry command 를 다시 뽑지 않는다."""
    _out, _session, seen = _run(
        ui_ids=["ui-1", "ui-2", "ui-3"],
        present_ids=["ui-1", "ui-2", "ui-3"],
        archived_command_ids=["cmd-A"],
        owner_of={"ui-1": "cmd-A", "ui-2": "cmd-B", "ui-3": "cmd-A"},
    )
    assert len(seen) == 3
    assert all(s is seen[0] for s in seen)


def test_no_archived_storyboards_skips_traversal_entirely():
    """보관된 스토리보드가 없으면 판정할 것도 없다 — 탐색을 아예 안 한다."""
    out, _session, seen = _run(
        ui_ids=["ui-1", "ui-2"],
        present_ids=["ui-1", "ui-2"],
        archived_command_ids=[],
        owner_of={"ui-1": "cmd-A", "ui-2": "cmd-B"},
    )
    assert out["storyboard_archived"] == {}
    assert seen == []


def test_empty_input_short_circuits():
    out = repository.fetch_classifier_view([])
    assert out == {"ui_present": {}, "storyboard_archived": {}}
