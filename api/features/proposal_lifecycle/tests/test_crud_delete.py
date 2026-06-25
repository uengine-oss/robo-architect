"""Proposal 영구 삭제 엔드포인트 단위 테스트 (Neo4j 불필요, monkeypatch).

삭제는 path id 와 본문 confirmId 가 일치해야 하며(오삭제 방지), ACCEPTED 는 거절,
없는 id 는 404, 일치하면 DETACH DELETE 가 실행됨을 확인한다.
"""

import asyncio
from contextlib import contextmanager

import pytest
from fastapi import HTTPException

from api.features.proposal_lifecycle.proposal_contracts import DeleteProposalRequest
from api.features.proposal_lifecycle.routes import proposals_crud as crud


class _FakeSession:
    def __init__(self, sink):
        self._sink = sink

    def run(self, query, **params):
        self._sink.append((query, params))
        return None


def _patch_db(monkeypatch, row):
    """_get_proposal_row 를 고정 row 로, get_session 을 실행 쿼리 수집기로 대체."""
    runs = []
    monkeypatch.setattr(crud, "_get_proposal_row", lambda pid: row)

    @contextmanager
    def fake_session():
        yield _FakeSession(runs)

    monkeypatch.setattr(crud, "get_session", fake_session)
    return runs


class _Req:
    class state:
        actor = None


def _call(pid, confirm):
    return asyncio.run(
        crud.delete_proposal(pid, DeleteProposalRequest(confirmId=confirm), _Req())
    )


def test_delete_id_mismatch_rejected(monkeypatch):
    _patch_db(monkeypatch, {"id": "PRO-001", "status": "DRAFT"})
    with pytest.raises(HTTPException) as exc:
        _call("PRO-001", "PRO-002")
    assert exc.value.status_code == 400
    assert exc.value.detail["reason"] == "id_mismatch"


def test_delete_not_found(monkeypatch):
    _patch_db(monkeypatch, None)
    with pytest.raises(HTTPException) as exc:
        _call("PRO-404", "PRO-404")
    assert exc.value.status_code == 404


def test_delete_accepted_blocked(monkeypatch):
    _patch_db(monkeypatch, {"id": "PRO-007", "status": "ACCEPTED"})
    with pytest.raises(HTTPException) as exc:
        _call("PRO-007", "PRO-007")
    assert exc.value.status_code == 423


def test_delete_success_detaches_node(monkeypatch):
    runs = _patch_db(monkeypatch, {"id": "PRO-009", "status": "DRAFT"})
    assert _call("PRO-009", "PRO-009") is None
    assert any("DETACH DELETE" in q for q, _ in runs)
    assert all(p.get("id") == "PRO-009" for _, p in runs)
