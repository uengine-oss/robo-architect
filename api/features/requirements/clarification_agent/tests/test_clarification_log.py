"""Tests for the persistent clarification log (030 — T032).

The log lives on `UserStory.clarifications` as a JSON-encoded array.
These tests stub `get_session()` so we exercise the JSON encode/decode +
sort behaviour without a live Neo4j connection.
"""

from __future__ import annotations

import json
from typing import Any
from unittest import mock

import pytest

from api.features.requirements.clarification_agent import clarification_log as clog
from api.features.requirements.clarification_contracts import (
    AmbiguityCategory,
    ClarificationLogEntry,
    UserStorySnapshot,
)


def _entry(
    *,
    session_id: str = "s-1",
    question_id: str = "q-1",
    user_story_id: str = "us-1",
    at: str = "2026-05-22T10:00:00+00:00",
    answer: str = "p95<1s",
) -> ClarificationLogEntry:
    return ClarificationLogEntry(
        sessionId=session_id,
        questionId=question_id,
        question="how fast?",
        answer=answer,
        category=AmbiguityCategory.non_functional,
        before=UserStorySnapshot(role="user", action="search", benefit=""),
        after=UserStorySnapshot(role="user", action="search in p95<1s", benefit=""),
        at=at,
    )


class _FakeRecord:
    def __init__(self, raw: Any):
        self._raw = raw

    def __getitem__(self, key: str) -> Any:
        if key == "raw":
            return self._raw
        if key == "userStoryId":
            return "us-1"
        raise KeyError(key)


class _FakeResult:
    def __init__(self, rec: _FakeRecord | None, records: list[_FakeRecord] | None = None):
        self._rec = rec
        self._records = records or ([rec] if rec is not None else [])

    def single(self) -> _FakeRecord | None:
        return self._rec

    def __iter__(self):
        return iter(self._records)


class _FakeSession:
    def __init__(self, store: dict[str, str]):
        self.store = store
        self.last_writes: list[tuple[str, dict[str, Any]]] = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):  # noqa: ANN001
        return False

    def run(self, query: str, **params: Any) -> _FakeResult:
        # Differentiate by query text: READ contains "RETURN", WRITE is "SET".
        if "$payload" in query:
            self.store[params["id"]] = params["payload"]
            return _FakeResult(rec=None)
        if "UNWIND" in query:
            # Scope read: emit one record per requested id.
            ids = params.get("ids", [])
            recs = []
            for _id in ids:
                raw = self.store.get(_id, "[]")
                rec = _FakeRecord(raw)
                rec._raw = raw  # type: ignore[attr-defined]
                # Override __getitem__ to return the right userStoryId per id.
                recs.append(_make_scope_record(_id, raw))
            return _FakeResult(rec=None, records=recs)
        # Per-id read: return one record.
        raw = self.store.get(params["id"], "[]")
        return _FakeResult(rec=_FakeRecord(raw))


def _make_scope_record(user_story_id: str, raw: str) -> _FakeRecord:
    rec = _FakeRecord(raw)
    rec_user_id = user_story_id

    def _gi(key: str) -> Any:
        if key == "raw":
            return raw
        if key == "userStoryId":
            return rec_user_id
        raise KeyError(key)

    rec.__getitem__ = _gi  # type: ignore[assignment]
    return rec


@pytest.fixture
def fake_db():
    """Stub `get_session()` so the log module talks to an in-memory dict."""
    store: dict[str, str] = {}
    session = _FakeSession(store)

    def _factory() -> _FakeSession:
        return session

    with mock.patch.object(clog, "get_session", _factory):
        yield store


# ── Append + read round-trip ────────────────────────────────────────────


def test_append_then_read_round_trip(fake_db: dict[str, str]) -> None:
    clog.append_log_entry("us-1", _entry(at="2026-05-22T10:00:00+00:00"))
    clog.append_log_entry("us-1", _entry(question_id="q-2", at="2026-05-22T10:05:00+00:00"))

    stored = json.loads(fake_db["us-1"])
    assert len(stored) == 2

    entries = clog.read_scope_log(["us-1"])
    assert [e.questionId for e in entries] == ["q-1", "q-2"]


# ── Scope aggregation chronological ordering ────────────────────────────


def test_scope_read_sorts_chronologically(fake_db: dict[str, str]) -> None:
    fake_db["us-1"] = json.dumps(
        [_entry(at="2026-05-22T11:00:00+00:00", question_id="late-1").model_dump(mode="json")]
    )
    fake_db["us-2"] = json.dumps(
        [
            _entry(at="2026-05-22T09:00:00+00:00", question_id="early-1").model_dump(mode="json"),
            _entry(at="2026-05-22T12:00:00+00:00", question_id="latest-1").model_dump(mode="json"),
        ]
    )
    entries = clog.read_scope_log(["us-1", "us-2"])
    assert [e.questionId for e in entries] == ["early-1", "late-1", "latest-1"]


# ── Revert flags every entry from the session for a user story ─────────


def test_revert_marks_session_entries_reverted(fake_db: dict[str, str]) -> None:
    fake_db["us-1"] = json.dumps(
        [
            _entry(session_id="s-1", question_id="q-1").model_dump(mode="json"),
            _entry(session_id="s-2", question_id="q-2").model_dump(mode="json"),
            _entry(session_id="s-1", question_id="q-3").model_dump(mode="json"),
        ]
    )
    clog.mark_log_entries_reverted("us-1", session_id="s-1")

    stored = json.loads(fake_db["us-1"])
    flags = {e["questionId"]: e.get("reverted", False) for e in stored}
    assert flags == {"q-1": True, "q-2": False, "q-3": True}
    # Each reverted entry must carry a `revertedAt` timestamp.
    for e in stored:
        if e["questionId"] in {"q-1", "q-3"}:
            assert e.get("revertedAt")


# ── Empty / absent property handled ────────────────────────────────────


def test_empty_property_yields_empty_list(fake_db: dict[str, str]) -> None:
    fake_db["us-1"] = "[]"
    assert clog.read_scope_log(["us-1"]) == []


def test_unknown_user_story_is_silently_skipped(fake_db: dict[str, str]) -> None:
    # No store entry for "ghost".
    entries = clog.read_scope_log(["ghost"])
    assert entries == []
