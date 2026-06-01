"""Tests for 035 — conversational (chat) edit scope I/O, contracts, wiring.

The live propose→apply→history round-trip is verified end-to-end against a
running backend + LLM. These lock in the scope→field mapping, the contract
defaults, and that the chat-edit routes are registered.
"""

from __future__ import annotations

from api.features.requirements.chat_edit import scope_io
from api.features.requirements.requirements_contracts import (
    ChatEditApplyRequest,
    ChatEditLogEntry,
    ChatEditProposal,
    EditHistoryItemDTO,
)
from api.features.requirements.router import router


def test_scope_field_mapping():
    assert scope_io.LABELS == {
        "epic": "BoundedContext", "feature": "Feature", "user-story": "UserStory"
    }
    assert scope_io.all_fields("epic") == ["name", "description"]
    assert "acceptanceCriteria" in scope_io.all_fields("user-story")
    assert "edgeCases" in scope_io.all_fields("feature")
    # list vs scalar partition is consistent
    for scope in scope_io.LABELS:
        overlap = set(scope_io.SCALAR_FIELDS[scope]) & set(scope_io.LIST_FIELDS[scope])
        assert not overlap


def test_chat_edit_contracts_defaults():
    p = ChatEditProposal()
    assert p.fields == {} and p.conflicts == []
    req = ChatEditApplyRequest(fields={"name": "X"})
    assert req.feedback == "" and req.baseUpdatedAt is None
    entry = ChatEditLogEntry(at="2026-05-31T00:00")
    assert entry.applied is True and entry.userName == "unknown"
    # legacy history entries carry no chat attribution
    h = EditHistoryItemDTO(id="h", timestamp="t", userName="u", userEmail="e", changes={})
    assert h.source is None and h.feedback is None


def test_chat_edit_routes_registered():
    paths = {r.path for r in router.routes}
    for suffix in ("stream", "apply", "log", "history"):
        assert f"/api/requirements/chat-edit/{{scope}}/{{node_id}}/{suffix}" in paths
