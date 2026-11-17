"""/accept · /destroy · /revoke · /retry-merge 라우트 게이팅 단위 테스트 (Neo4j·git 불필요).

라우트 함수를 직접 호출한다(test_crud_delete.py 와 같은 방식). 그래프는 FakeGraph,
dual merge / revoke 서비스와 SandboxManager 는 기록용 대역으로 바꾼다.
"""

from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from api.features.proposal_lifecycle.proposal_contracts import (
    AcceptProposalRequest,
    DestroyProposalRequest,
    RevokeProposalRequest,
)
from api.features.proposal_lifecycle.routes import proposals_acceptance as acc
from api.features.proposal_lifecycle.tests.lifecycle_fakes import (
    FakeGraph,
    FakeSandbox,
    capture_logs,
    forbid_real_backends,
)

PID = "PRO-007"
ALL_STATUSES = ["DRAFT", "SUBMITTED", "IMPLEMENTING", "TESTING", "PENDING_ACCEPTANCE",
                "ACCEPTED", "DESTROYED", "MERGE_FAILED"]


class _Req:
    def __init__(self, role=None, email="po@example.com"):
        actor = SimpleNamespace(email=email, role=role) if (role or email) else None
        self.state = SimpleNamespace(actor=actor)
        self.method = "POST"
        self.url = SimpleNamespace(path=f"/api/proposals/{PID}")
        self.query_params = {}
        self.path_params = {"proposal_id": PID}
        self.client = None


def _row(status, **extra):
    row = {"id": PID, "title": "부분 환불", "originalPrompt": "부분 환불 지원", "author": "dev@example.com",
           "createdAt": "2026-10-30T00:00:00+00:00", "status": status, "statusHistory": "[]",
           "projectRoot": "/work/shop"}
    row.update(extra)
    return row


@pytest.fixture
def env(monkeypatch):
    forbid_real_backends(monkeypatch)
    capture_logs(monkeypatch)
    state = SimpleNamespace(graph=FakeGraph(None), sandbox=FakeSandbox(), merges=[], revokes=[],
                            merge_raises=None, revoke_raises=None)

    def set_row(row):
        state.graph.proposal = dict(row) if row is not None else None
        return state.graph

    async def fake_dual_merge(proposal_id, actor, comment=None):
        state.merges.append({"id": proposal_id, "actor": actor, "comment": comment})
        if state.merge_raises:
            raise state.merge_raises
        state.graph.proposal["status"] = "ACCEPTED"

    async def fake_revoke(proposal_id, actor, revert_code, comment=None):
        state.revokes.append({"id": proposal_id, "actor": actor, "revertCode": revert_code,
                              "comment": comment})
        if state.revoke_raises:
            raise state.revoke_raises
        state.graph.proposal["status"] = "PENDING_ACCEPTANCE"
        return {"reverted": 0, "errors": [], "codeRevert": None}

    monkeypatch.setattr(acc, "get_session", lambda *a, **k: state.graph.session())
    monkeypatch.setattr(acc, "_sandbox", state.sandbox)
    monkeypatch.setattr(acc, "execute_dual_merge", fake_dual_merge)
    monkeypatch.setattr(acc, "execute_revoke", fake_revoke)
    state.set_row = set_row
    return state


def _accept(body=None, req=None):
    return asyncio.run(acc.accept_proposal(PID, body or AcceptProposalRequest(), req or _Req()))


def _destroy(reason=None, req=None):
    return asyncio.run(acc.destroy_proposal(PID, DestroyProposalRequest(reason=reason), req or _Req()))


def _revoke(body=None, req=None):
    return asyncio.run(acc.revoke_proposal(PID, body or RevokeProposalRequest(), req or _Req()))


def _retry(req=None):
    async def run():
        resp = await acc.retry_merge(PID, req or _Req())
        chunks = [c async for c in resp.body_iterator]
        return resp, "".join(c.decode() if isinstance(c, bytes) else c for c in chunks)
    return asyncio.run(run())


def _sse_events(text):
    events = []
    for block in text.strip().split("\n\n"):
        lines = dict(line.split(": ", 1) for line in block.splitlines())
        events.append((lines["event"], json.loads(lines["data"])))
    return events


# ── Accept ───────────────────────────────────────────────────────────────────

def test_accept_unknown_proposal_is_404(env):
    env.set_row(None)
    with pytest.raises(HTTPException) as exc:
        _accept()
    assert exc.value.status_code == 404
    assert env.merges == []


@pytest.mark.parametrize("status", ["TESTING", "PENDING_ACCEPTANCE"])
def test_accept_allowed_after_implementation_completes(env, status):
    env.set_row(_row(status))
    resp = _accept(AcceptProposalRequest(comment="좋습니다"))
    assert env.merges == [{"id": PID, "actor": "po@example.com", "comment": "좋습니다"}]
    assert resp.status.value == "ACCEPTED"


@pytest.mark.parametrize("status", [s for s in ALL_STATUSES if s not in ("TESTING", "PENDING_ACCEPTANCE")])
def test_accept_rejected_in_other_states(env, status):
    env.set_row(_row(status))
    with pytest.raises(HTTPException) as exc:
        _accept()
    assert exc.value.status_code == 409
    assert status in exc.value.detail
    assert env.merges == []


def test_accept_requires_po_role(env):
    env.set_row(_row("PENDING_ACCEPTANCE"))
    with pytest.raises(HTTPException) as exc:
        _accept(req=_Req(role="DEVELOPER"))
    assert exc.value.status_code == 403
    assert env.merges == []


def test_accept_defaults_to_po_when_no_role_is_attached(env):
    """인증 미도입 상태의 기본 PO 정책 — actor 가 없어도 anonymous PO 로 Accept 된다."""
    env.set_row(_row("PENDING_ACCEPTANCE"))
    _accept(req=_Req(role=None, email=None))
    assert env.merges[0]["actor"] == "anonymous"


@pytest.mark.parametrize("raw", [
    json.dumps({"passed": 3, "failed": 2}),
    {"passed": 3, "failed": 2},  # 드라이버가 dict 로 돌려주는 경우
])
def test_accept_blocked_when_verification_has_failures(env, raw):
    env.set_row(_row("PENDING_ACCEPTANCE", testResults=raw))
    with pytest.raises(HTTPException) as exc:
        _accept()
    assert exc.value.status_code == 400
    assert "2 test(s) failed" in exc.value.detail
    assert "forceAcceptWithFailures" in exc.value.detail
    assert env.merges == []


def test_accept_with_failures_proceeds_when_po_acknowledges(env):
    """화면의 '실패 항목을 인지하고 진행' 체크 → forceAcceptWithFailures=true."""
    env.set_row(_row("PENDING_ACCEPTANCE", testResults=json.dumps({"passed": 1, "failed": 4})))
    resp = _accept(AcceptProposalRequest(forceAcceptWithFailures=True, comment="알고 진행"))
    assert env.merges == [{"id": PID, "actor": "po@example.com", "comment": "알고 진행"}]
    assert resp.status.value == "ACCEPTED"


@pytest.mark.parametrize("raw", [
    None,
    json.dumps({"passed": 5, "failed": 0}),
    json.dumps({"totalScenarios": 0, "items": []}),
])
def test_accept_without_failures_needs_no_force(env, raw):
    env.set_row(_row("PENDING_ACCEPTANCE", testResults=raw))
    _accept()
    assert len(env.merges) == 1


@pytest.mark.xfail(strict=True, reason=(
    "BUG(낮음): failed 수를 비교할 때 타입 오류를 except Exception: pass 로 삼켜 게이트가 열린다 "
    "(proposals_acceptance.py accept_proposal 의 testResults 검사). 검증 결과는 스킬(LLM) JSON 그대로 "
    "저장되므로 \"failed\": \"2\" 같은 문자열이면 실패가 있어도 force 없이 Accept 된다."))
def test_accept_failure_gate_does_not_fail_open_on_string_count(env):
    env.set_row(_row("PENDING_ACCEPTANCE", testResults=json.dumps({"passed": 1, "failed": "2"})))
    with pytest.raises(HTTPException) as exc:
        _accept()
    assert exc.value.status_code == 400


def test_accept_merge_failure_is_500_with_detail(env):
    env.set_row(_row("PENDING_ACCEPTANCE"))
    env.merge_raises = RuntimeError("DualMerge failed at git_merge: CONFLICT")
    with pytest.raises(HTTPException) as exc:
        _accept()
    assert exc.value.status_code == 500
    assert "CONFLICT" in exc.value.detail


# ── Destroy ──────────────────────────────────────────────────────────────────

def test_destroy_unknown_is_404(env):
    env.set_row(None)
    with pytest.raises(HTTPException) as exc:
        _destroy()
    assert exc.value.status_code == 404


def test_destroy_accepted_is_locked(env):
    env.set_row(_row("ACCEPTED", sandboxBranch=f"proposal/{PID}"))
    with pytest.raises(HTTPException) as exc:
        _destroy()
    assert exc.value.status_code == 423
    assert env.sandbox.calls == []
    assert env.graph.proposal["status"] == "ACCEPTED"


@pytest.mark.parametrize("status", [s for s in ALL_STATUSES if s != "ACCEPTED"])
def test_destroy_allowed_in_non_accepted_states(env, status):
    env.set_row(_row(status))
    resp = _destroy(reason="방향 변경")
    p = env.graph.proposal
    assert p["status"] == "DESTROYED" and p["sandboxStatus"] == "DESTROYED" and p.get("destroyedAt")
    assert resp.status.value == "DESTROYED"
    last = env.graph.history()[-1]
    assert (last["from_status"], last["to_status"], last["comment"]) == (status, "DESTROYED", "방향 변경")


def test_destroy_removes_worktree_in_target_project(env):
    env.set_row(_row("TESTING", sandboxBranch=f"proposal/{PID}",
                     sandboxWorktreePath=f"/work/shop/.sandbox/proposal/{PID}"))
    _destroy()
    assert env.sandbox.calls == [("remove_worktree", PID, "/work/shop")]


@pytest.mark.parametrize("extra", [
    {},  # 구현을 시작하지 않아 worktree 가 없다
    {"sandboxBranch": f"proposal/{PID}", "projectRoot": None},  # 대상 프로젝트 경로 유실
])
def test_destroy_skips_worktree_cleanup_when_nothing_to_clean(env, extra):
    env.set_row(_row("SUBMITTED", **extra))
    _destroy()
    assert env.sandbox.calls == []
    assert env.graph.proposal["status"] == "DESTROYED"


def test_destroy_still_destroys_when_worktree_cleanup_fails(env):
    env.sandbox.remove_raises = RuntimeError("worktree locked")
    env.set_row(_row("TESTING", sandboxBranch=f"proposal/{PID}"))
    _destroy()
    assert env.graph.proposal["status"] == "DESTROYED"


@pytest.mark.xfail(strict=True, reason=(
    "BUG(권한): /destroy 는 역할을 확인하지 않는다 — /accept·/revoke 는 PO 가 아니면 403 인데 "
    "destroy_proposal 에는 _actor_role 검사가 없다 (proposals_acceptance.py destroy_proposal). "
    "docstring 은 'PO Destroy'."))
def test_destroy_requires_po_role(env):
    env.set_row(_row("PENDING_ACCEPTANCE"))
    with pytest.raises(HTTPException) as exc:
        _destroy(req=_Req(role="DEVELOPER"))
    assert exc.value.status_code == 403


# ── Revoke ───────────────────────────────────────────────────────────────────

def test_revoke_accepted_calls_service_with_flags(env):
    env.set_row(_row("ACCEPTED"))
    resp = _revoke(RevokeProposalRequest(revertCode=True, comment="잘못 승인"))
    assert env.revokes == [{"id": PID, "actor": "po@example.com", "revertCode": True,
                            "comment": "잘못 승인"}]
    assert resp.status.value == "PENDING_ACCEPTANCE"


@pytest.mark.parametrize("status", [s for s in ALL_STATUSES if s != "ACCEPTED"])
def test_revoke_only_from_accepted(env, status):
    env.set_row(_row(status))
    with pytest.raises(HTTPException) as exc:
        _revoke()
    assert exc.value.status_code == 409
    assert env.revokes == []


def test_revoke_requires_po_role(env):
    env.set_row(_row("ACCEPTED"))
    with pytest.raises(HTTPException) as exc:
        _revoke(req=_Req(role="DEVELOPER"))
    assert exc.value.status_code == 403
    assert env.revokes == []


def test_revoke_unknown_is_404(env):
    env.set_row(None)
    with pytest.raises(HTTPException) as exc:
        _revoke()
    assert exc.value.status_code == 404


def test_revoke_service_failure_is_500(env):
    env.set_row(_row("ACCEPTED"))
    env.revoke_raises = RuntimeError("neo4j down")
    with pytest.raises(HTTPException) as exc:
        _revoke()
    assert exc.value.status_code == 500 and "neo4j down" in exc.value.detail


# ── Retry merge (SSE) ────────────────────────────────────────────────────────

def test_retry_merge_streams_start_and_done(env):
    env.set_row(_row("MERGE_FAILED"))
    resp, body = _retry()
    assert resp.media_type == "text/event-stream"
    assert _sse_events(body) == [
        ("merge_retry_start", {"proposalId": PID}),
        ("merge_done", {"proposalId": PID, "status": "ACCEPTED"}),
    ]
    assert env.merges == [{"id": PID, "actor": "po@example.com", "comment": None}]


def test_retry_merge_streams_failure_instead_of_raising(env):
    env.set_row(_row("MERGE_FAILED"))
    env.merge_raises = RuntimeError("DualMerge failed at git_merge: still conflicted")
    _resp, body = _retry()
    events = _sse_events(body)
    assert [e for e, _ in events] == ["merge_retry_start", "merge_failed"]
    assert "still conflicted" in events[1][1]["error"]


@pytest.mark.parametrize("status", [s for s in ALL_STATUSES if s != "MERGE_FAILED"])
def test_retry_merge_only_from_merge_failed(env, status):
    env.set_row(_row(status))
    with pytest.raises(HTTPException) as exc:
        asyncio.run(acc.retry_merge(PID, _Req()))
    assert exc.value.status_code == 409
    assert env.merges == []


def test_retry_merge_unknown_is_404(env):
    env.set_row(None)
    with pytest.raises(HTTPException) as exc:
        asyncio.run(acc.retry_merge(PID, _Req()))
    assert exc.value.status_code == 404


@pytest.mark.xfail(strict=True, reason=(
    "BUG(권한): /retry-merge 는 역할을 확인하지 않는다 — 재시도가 곧 Accept(dual merge)인데 "
    "/accept 의 PO 검사가 retry_merge 에는 없다 (proposals_acceptance.py retry_merge)."))
def test_retry_merge_requires_po_role(env):
    env.set_row(_row("MERGE_FAILED"))
    with pytest.raises(HTTPException) as exc:
        asyncio.run(acc.retry_merge(PID, _Req(role="DEVELOPER")))
    assert exc.value.status_code == 403
