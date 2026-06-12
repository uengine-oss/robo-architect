"""Contract tests for the BPM-task design-trace route (spec 039).

Mirrors the fake-session + monkeypatch pattern used elsewhere in the hybrid
suite (no live Neo4j). The full frontier expansion is covered by the shared
`_expand_trace` (exercised by the User-Story trace tests); here we stub it and
focus on the route's contract: 404 / empty / depth-clamp / read-only / shape.
"""

from __future__ import annotations

import asyncio

import pytest

from api.features.canvas_graph.routes import bpm_task_trace


class _Result:
    def __init__(self, rows):
        self._rows = rows

    def single(self):
        return self._rows[0] if self._rows else None

    def __iter__(self):
        return iter(self._rows)


class _Session:
    """Scripts responses by query content; records every query for read-only assertions."""

    def __init__(self, *, task_exists: bool, promoted_cmd_ids: list[str]):
        self.task_exists = task_exists
        self.promoted_cmd_ids = promoted_cmd_ids
        self.queries: list[str] = []

    def run(self, query, **params):
        self.queries.append(query)
        if "RETURN t.id AS id" in query:  # existence check
            return _Result([{"id": "t1"}] if self.task_exists else [])
        if "RETURN cid" in query:  # root Command ids (PROMOTED_TO / PROMOTED_FROM union)
            return _Result([{"cid": c} for c in self.promoted_cmd_ids])
        return _Result([])


class _Ctx:
    def __init__(self, s):
        self.s = s

    def __enter__(self):
        return self.s

    def __exit__(self, exc_type, exc, tb):
        return False


def _patch(monkeypatch, session, expand_capture=None):
    monkeypatch.setattr(bpm_task_trace, "get_session", lambda: _Ctx(session))
    monkeypatch.setattr(bpm_task_trace, "http_context", lambda r: {})

    def _fake_expand(sess, root_ids, depth):
        if expand_capture is not None:
            expand_capture["root_ids"] = root_ids
            expand_capture["depth"] = depth
        # minimal non-empty graph so the route returns the expanded shape
        nodes = {cid: {"id": cid, "type": "Command"} for cid in root_ids}
        return nodes, []

    monkeypatch.setattr(bpm_task_trace, "_expand_trace", _fake_expand)


def _call(task_id, depth=2):
    return asyncio.run(
        bpm_task_trace.get_bpm_task_design_trace(task_id, request=None, depth=depth)
    )


def test_missing_task_returns_404(monkeypatch):
    from fastapi import HTTPException

    sess = _Session(task_exists=False, promoted_cmd_ids=[])
    _patch(monkeypatch, sess)
    with pytest.raises(HTTPException) as ei:
        _call("nope")
    assert ei.value.status_code == 404


def test_task_with_no_promoted_command_is_empty(monkeypatch):
    sess = _Session(task_exists=True, promoted_cmd_ids=[])
    _patch(monkeypatch, sess)
    resp = _call("t1")
    assert resp.empty is True
    assert resp.nodes == []
    assert resp.relationships == []
    assert resp.rootCommandId is None


def test_task_with_commands_returns_trace(monkeypatch):
    sess = _Session(task_exists=True, promoted_cmd_ids=["cmd_a", "cmd_b"])
    _patch(monkeypatch, sess)
    resp = _call("t1")
    assert resp.empty is False
    assert resp.rootCommandId == "cmd_a"
    ids = {n["id"] for n in resp.nodes}
    assert {"cmd_a", "cmd_b"} <= ids


def test_depth_is_clamped_to_five(monkeypatch):
    cap = {}
    sess = _Session(task_exists=True, promoted_cmd_ids=["cmd_a"])
    _patch(monkeypatch, sess, expand_capture=cap)
    _call("t1", depth=99)
    assert cap["depth"] == 5


def test_route_is_read_only(monkeypatch):
    sess = _Session(task_exists=True, promoted_cmd_ids=["cmd_a"])
    _patch(monkeypatch, sess)
    _call("t1")
    joined = "\n".join(sess.queries).upper()
    for forbidden in ("MERGE", "CREATE", "DELETE", " SET "):
        assert forbidden not in joined, f"read-only violated: {forbidden} present"
