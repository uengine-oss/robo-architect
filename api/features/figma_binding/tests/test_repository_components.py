"""Unit tests for the :FigmaComponent CRUD helpers added in spec 024.

These use a mocked neo4j session so they don't require a live database.
The intent is to lock the Cypher contract (parameters passed, dict shape
returned) — not to exercise the database itself.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from api.features.figma_binding import repository


class _FakeRecord(dict):
    """A neo4j-style record exposing the same `r["key"]` and `r.get(key)` API."""

    def __init__(self, mapping: dict):
        super().__init__(mapping)


class _FakeSession:
    def __init__(self, single_value=None, data_value=None):
        self._single_value = single_value
        self._data_value = data_value or []
        self.last_query = None
        self.last_params = None

    def run(self, query, **params):
        self.last_query = query
        self.last_params = params
        return _FakeQueryResult(self._single_value, self._data_value)

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class _FakeQueryResult:
    def __init__(self, single_value, data_value):
        self._single = single_value
        self._data = data_value

    def single(self):
        return self._single

    def data(self):
        return self._data


def test_upsert_figma_component_passes_expected_params():
    fake_session = _FakeSession(
        single_value=_FakeRecord({"c": {"name": "btn", "figmaNodeId": "1:1"}})
    )
    with patch.object(repository, "get_session", return_value=fake_session):
        out = repository.upsert_figma_component(
            binding_file_key="file-1",
            figma_node_id="1:1",
            name="btn-primary",
            page_name="Components",
            width_px=120,
            height_px=40,
            vlm_description="A primary button.",
        )
    assert out["name"] == "btn"
    assert fake_session.last_params["fk"] == "file-1"
    assert fake_session.last_params["nid"] == "1:1"
    assert fake_session.last_params["name"] == "btn-primary"
    assert fake_session.last_params["desc"] == "A primary button."
    assert fake_session.last_params["w"] == 120
    assert fake_session.last_params["h"] == 40


def test_count_figma_components_returns_zero_when_no_binding():
    with patch.object(repository, "get_active_binding", return_value=None):
        assert repository.count_figma_components() == 0


def test_list_figma_components_returns_empty_when_no_binding():
    with patch.object(repository, "get_active_binding", return_value=None):
        assert repository.list_figma_components() == []


def test_delete_stale_figma_components_passes_kept_list():
    fake_session = _FakeSession(single_value=_FakeRecord({"n": 3}))
    with patch.object(repository, "get_session", return_value=fake_session):
        out = repository.delete_stale_figma_components("file-1", ["1:1", "1:2"])
    assert out == 3
    assert fake_session.last_params["fk"] == "file-1"
    assert fake_session.last_params["kept"] == ["1:1", "1:2"]
