"""Dual Merge(Accept) · Revoke 서비스 단위 테스트 (Neo4j·git 불필요).

execute_dual_merge 의 계약:
  1. projectRoot 확인 → git merge (실패 시 MERGE_FAILED)
  2. Strategic/Tactical diff 를 설계 그래프에 반영 + 검증 + ACCEPTED (실패 시 git reset + MERGE_FAILED)
  3. worktree 정리 (실패해도 Accept 유지)

그래프는 FakeGraph(쿼리 기록 + 최소 Cypher 흉내), git 은 FakeSandbox 로 대체한다.
diff 반영은 실제 proposal_apply 코드를 그대로 통과시켜 "무엇이 그래프에 쓰였는지"를 본다.
"""

from __future__ import annotations

import asyncio
import json

import pytest

from api.features.proposal_lifecycle.services import dual_merge
from api.features.proposal_lifecycle.services.dual_merge import DualMergeFailed
from api.features.proposal_lifecycle.tests.lifecycle_fakes import (
    FakeGraph,
    FakeSandbox,
    capture_logs,
    forbid_real_backends,
)

PID = "PRO-001"
ROOT = "/work/shop"

STRATEGIC = {
    "epics": [{"op": "CREATE", "tempId": "EP-001", "entityTitle": "환불",
               "reason": "부분 환불 도입", "impactLevel": "HIGH"}],
    "features": [{"op": "CREATE", "tempId": "FT-001", "epicId": "EP-001",
                  "entityTitle": "부분 환불"}],
    "userStories": [{"op": "CREATE", "tempId": "US-001", "featureId": "FT-001",
                     "entityTitle": "고객: 주문 금액 일부만 환불을 요청한다",
                     "acceptanceCriteria": ["환불 금액은 결제 금액 이하"]}],
}
TACTICAL = [{"nodeLabel": "Aggregate", "changeType": "CREATE", "nodeId": "AGG-TMP-1",
             "nodeTitle": "Refund", "boundedContextId": "EP-001"}]


def _proposal(status="PENDING_ACCEPTANCE", strategic=STRATEGIC, tactical=TACTICAL, **extra):
    row = {
        "id": PID, "title": "부분 환불", "status": status, "projectRoot": ROOT,
        "strategicDiff": json.dumps(strategic, ensure_ascii=False),
        "tacticalDiff": json.dumps(tactical, ensure_ascii=False),
        "journeys": None, "statusHistory": "[]",
    }
    row.update(extra)
    return row


@pytest.fixture
def env(monkeypatch):
    """FakeGraph + FakeSandbox 를 dual_merge·proposal_apply 에 꽂는다."""
    forbid_real_backends(monkeypatch)
    logs = capture_logs(monkeypatch)
    graph = FakeGraph(_proposal())
    sandbox = FakeSandbox()
    spec_docs: list[str] = []
    monkeypatch.setattr(dual_merge, "get_session", graph.session)
    monkeypatch.setattr(dual_merge, "_sandbox", sandbox)
    # 실제 구현은 robo-architect 저장소의 specs/proposal-changes.md 에 append 한다 — 테스트에서는 기록만.
    monkeypatch.setattr(dual_merge, "_update_spec_docs", lambda pid: spec_docs.append(pid))

    class Env:
        pass

    e = Env()
    e.graph, e.sandbox, e.logs, e.spec_docs, e.mp = graph, sandbox, logs, spec_docs, monkeypatch
    return e


def _accept(actor="po@example.com", comment=None):
    return asyncio.run(dual_merge.execute_dual_merge(PID, actor, comment=comment))


# ── 성공 경로: 그래프에 쓰는 내용 ─────────────────────────────────────────────

def test_accept_writes_strategic_and_tactical_nodes_with_hierarchy(env):
    _accept(comment="LGTM")
    g = env.graph

    [bc] = g.nodes_of("BoundedContext")
    [feat] = g.nodes_of("Feature")
    [story] = g.nodes_of("UserStory")
    [agg] = g.nodes_of("Aggregate")
    assert bc["name"] == "환불" and feat["name"] == "부분 환불" and agg["name"] == "Refund"
    assert {n["proposalSource"] for n in (bc, feat, story, agg)} == {PID}

    # tempId(EP-001/FT-001) 가 실제 id 로 해소되어 계층 관계가 연결된다
    rel = {(r["type"], r["from"], r["to"]) for r in g.rels}
    assert ("HAS_FEATURE", bc["id"], feat["id"]) in rel
    assert ("HAS_USER_STORY", feat["id"], story["id"]) in rel
    assert ("IMPLEMENTS", story["id"], bc["id"]) in rel  # BC 는 Feature 의 BC 에서 유도
    assert ("HAS_AGGREGATE", bc["id"], agg["id"]) in rel  # strategic→tactical ref_map 공유

    # UserStory 는 "역할: 행동" 제목에서 role/action 을 뽑고 AC 를 그대로 싣는다
    [(_q, us_params)] = g.queries("CREATE (us:UserStory {")
    assert us_params["role"] == "고객"
    assert us_params["action"] == "주문 금액 일부만 환불을 요청한다"
    assert us_params["ac"] == ["환불 금액은 결제 금액 이하"]

    # 생성된 4개 노드 모두에 EFFECT(CREATE) 가 남는다 — revoke 의 근거
    effects = [r for r in g.rels_of("EFFECT") if r["from"] == PID]
    assert {r["to"] for r in effects} == {bc["id"], feat["id"], story["id"], agg["id"]}
    assert {r["props"]["changeType"] for r in effects} == {"CREATE"}
    bc_effect = next(r for r in effects if r["to"] == bc["id"])
    assert json.loads(bc_effect["props"]["diff"])["createdNodeId"] == bc["id"]


def test_accept_marks_proposal_accepted_with_history(env):
    _accept(actor="po@example.com", comment="LGTM")
    p = env.graph.proposal
    assert p["status"] == "ACCEPTED"
    assert p["sandboxStatus"] == "DESTROYED"
    assert p.get("acceptedAt")
    last = env.graph.history()[-1]
    assert (last["from_status"], last["to_status"]) == ("PENDING_ACCEPTANCE", "ACCEPTED")
    assert last["actor"] == "po@example.com" and last["comment"] == "LGTM"
    assert env.spec_docs == [PID]


def test_accept_order_is_merge_then_graph_then_cleanup(env):
    _accept()
    assert env.sandbox.names() == ["merge_to_main", "cleanup_worktree"]
    assert env.sandbox.calls[0] == ("merge_to_main", PID, ROOT)
    assert env.sandbox.calls[1] == ("cleanup_worktree", PID, ROOT)
    # ACCEPTED 전환은 diff 반영(노드 생성) 뒤에 마지막으로 실행된다
    idx_accept = next(i for i, (q, _) in enumerate(env.graph.runs) if "SET p.status = 'ACCEPTED'" in q)
    idx_last_create = max(i for i, (q, _) in enumerate(env.graph.runs) if "CREATE (" in q or "MERGE (n:" in q)
    assert idx_last_create < idx_accept


def test_accept_from_testing_records_testing_as_from_status(env):
    """검증을 생략하고 TESTING 에서 바로 Accept 한 경우 이력의 출발 상태가 TESTING."""
    env.graph.proposal["status"] = "TESTING"
    _accept()
    last = env.graph.history()[-1]
    assert (last["from_status"], last["to_status"]) == ("TESTING", "ACCEPTED")


def test_cleanup_failure_does_not_undo_accept(env):
    env.sandbox.cleanup_raises = RuntimeError("worktree locked")
    _accept()
    assert env.graph.proposal["status"] == "ACCEPTED"
    assert any(entry["category"] == "proposal_lifecycle.merge.cleanup_warn" for entry in env.logs)


def test_spec_docs_failure_does_not_undo_accept(env):
    def boom(_pid):
        raise OSError("read-only install")

    env.mp.setattr(dual_merge, "_update_spec_docs", boom)
    _accept()
    assert env.graph.proposal["status"] == "ACCEPTED"
    assert any(entry["category"] == "proposal_lifecycle.merge.spec_update_warn" for entry in env.logs)


# ── 실패 경로: MERGE_FAILED ───────────────────────────────────────────────────

def test_missing_project_root_fails_before_git(env):
    env.graph.proposal["projectRoot"] = None
    with pytest.raises(DualMergeFailed) as exc:
        _accept()
    assert exc.value.step == "git_merge"
    assert env.sandbox.calls == []
    assert env.graph.proposal["status"] == "MERGE_FAILED"
    assert "projectRoot" in env.graph.history()[-1]["comment"]


@pytest.mark.parametrize("git_error, expected_comment", [
    ("CONFLICT (content): Merge conflict in src/refund.py", "CONFLICT (content): Merge conflict in src/refund.py"),
    (None, "git merge 실패"),
    ("", "git merge 실패"),
])
def test_git_merge_failure_marks_merge_failed_and_skips_graph(env, git_error, expected_comment):
    env.sandbox.merge_ok, env.sandbox.merge_error = False, git_error
    with pytest.raises(DualMergeFailed) as exc:
        _accept()
    assert exc.value.step == "git_merge"
    g = env.graph
    assert g.proposal["status"] == "MERGE_FAILED"
    last = g.history()[-1]
    assert last["to_status"] == "MERGE_FAILED" and last["comment"] == expected_comment
    # 설계 그래프에는 아무것도 쓰지 않았고 worktree 도 남겨 둔다(재시도용)
    assert g.nodes == {} and g.rels == []
    assert env.sandbox.names() == ["merge_to_main"]
    assert env.spec_docs == []


def test_graph_failure_resets_git_merge_and_marks_merge_failed(env):
    def boom(*_a, **_k):
        raise RuntimeError("Neo4j unavailable")

    env.mp.setattr(dual_merge, "apply_tactical_diff", boom)
    with pytest.raises(DualMergeFailed) as exc:
        _accept()
    assert exc.value.step == "graph_update" and "Neo4j unavailable" in exc.value.detail
    assert env.sandbox.names() == ["merge_to_main", "reset_merge"]  # 정리는 하지 않는다
    assert env.graph.proposal["status"] == "MERGE_FAILED"
    assert "Neo4j unavailable" in env.graph.history()[-1]["comment"]
    assert not env.graph.queries("SET p.status = 'ACCEPTED'")


def test_strategic_modify_without_entity_id_blocks_accept(env):
    """MODIFY 인데 entityId 가 없으면 아무것도 반영되지 않는다 → 조용히 ACCEPTED 되지 않아야 한다."""
    env.graph.proposal.update(_proposal(
        strategic={"features": [{"op": "MODIFY", "entityTitle": "부분 환불"}]}, tactical=[]))
    with pytest.raises(DualMergeFailed) as exc:
        _accept()
    assert exc.value.step == "graph_update"
    assert "Strategic diff produced no live graph changes" in exc.value.detail
    assert env.graph.proposal["status"] == "MERGE_FAILED"
    assert "reset_merge" in env.sandbox.names()


def test_aggregate_not_linked_to_bounded_context_blocks_accept(env):
    """Aggregate 가 BC 에 HAS_AGGREGATE 로 매달리지 않으면 live projection 검증이 막는다."""
    orphan = [{"nodeLabel": "Aggregate", "changeType": "CREATE", "nodeTitle": "Refund"}]
    env.graph.proposal.update(_proposal(tactical=orphan))
    with pytest.raises(DualMergeFailed) as exc:
        _accept()
    assert "not linked to BoundedContext" in exc.value.detail
    assert env.graph.proposal["status"] == "MERGE_FAILED"


# ── 재시도 (MERGE_FAILED → retry) ────────────────────────────────────────────

def test_retry_from_merge_failed_succeeds(env):
    env.sandbox.merge_ok, env.sandbox.merge_error = False, "CONFLICT in a.py"
    with pytest.raises(DualMergeFailed):
        _accept()
    assert env.graph.proposal["status"] == "MERGE_FAILED"

    env.sandbox.merge_ok, env.sandbox.merge_error = True, None  # 사용자가 충돌 해결
    _accept(actor="po@example.com")
    g = env.graph
    assert g.proposal["status"] == "ACCEPTED"
    assert [h["to_status"] for h in g.history()] == ["MERGE_FAILED", "ACCEPTED"]
    assert g.history()[-1]["from_status"] == "MERGE_FAILED"
    assert len(g.nodes_of("BoundedContext")) == 1
    assert env.sandbox.names()[-2:] == ["merge_to_main", "cleanup_worktree"]


@pytest.mark.xfail(strict=True, reason=(
    "BUG: _set_merge_failed 는 출발 상태를 항상 'PENDING_ACCEPTANCE' 로 기록한다 "
    "(dual_merge.py _set_merge_failed). TESTING 에서 Accept 하다 실패하면 이력이 사실과 다르다."))
def test_merge_failed_history_records_actual_from_status(env):
    env.graph.proposal["status"] = "TESTING"
    env.sandbox.merge_ok, env.sandbox.merge_error = False, "CONFLICT"
    with pytest.raises(DualMergeFailed):
        _accept()
    assert env.graph.history()[-1]["from_status"] == "TESTING"


@pytest.mark.xfail(strict=True, reason=(
    "BUG: _apply_diffs_and_accept 의 그래프 반영은 트랜잭션이 아니다 — auto-commit session.run 의 연속이라 "
    "검증 실패(graph_update) 시 이미 만든 BC/Feature/UserStory/Aggregate·EFFECT 가 라이브 설계 그래프에 남고, "
    "retry-merge 때 strategic CREATE 가 새 id 로 다시 만들어져 노드가 중복된다 (dual_merge.py _apply_diffs_and_accept)."))
def test_graph_update_failure_leaves_no_partial_nodes_and_retry_does_not_duplicate(env):
    orphan = [{"nodeLabel": "Aggregate", "changeType": "CREATE", "nodeTitle": "Refund"}]
    env.graph.proposal.update(_proposal(tactical=orphan))
    with pytest.raises(DualMergeFailed):
        _accept()
    assert env.graph.proposal["status"] == "MERGE_FAILED"
    leftovers = [n for n in env.graph.nodes.values() if n.get("proposalSource") == PID]
    assert leftovers == [], f"MERGE_FAILED 인데 설계 그래프에 남은 노드: {[n['label'] for n in leftovers]}"

    env.graph.proposal.update({"tacticalDiff": json.dumps(TACTICAL)})
    _accept()
    assert len(env.graph.nodes_of("BoundedContext")) == 1


# ── Revoke (ACCEPTED → PENDING_ACCEPTANCE) ───────────────────────────────────

def _revoke(revert_code=False, comment=None):
    return asyncio.run(dual_merge.execute_revoke(PID, "po@example.com", revert_code, comment=comment))


def test_revoke_round_trip_removes_created_nodes(env):
    _accept()
    assert env.graph.nodes and env.graph.rels_of("EFFECT")
    env.sandbox.calls.clear()

    result = _revoke()
    g = env.graph
    assert result["reverted"] == 4 and result["errors"] == []
    assert result["codeRevert"] is None
    assert [n for n in g.nodes.values() if n.get("proposalSource") == PID] == []
    assert g.rels_of("EFFECT") == [] and g.rels_of("HAS_AGGREGATE") == []
    assert g.proposal["status"] == "PENDING_ACCEPTANCE"
    assert "acceptedAt" not in g.proposal
    last = g.history()[-1]
    assert (last["from_status"], last["to_status"], last["comment"]) == (
        "ACCEPTED", "PENDING_ACCEPTANCE", "수거(revoke)")
    assert env.sandbox.calls == []  # revertCode=False 면 git 은 건드리지 않는다


def test_revoke_restores_modified_field_on_existing_node(env):
    g = env.graph
    g.nodes["bc-pay"] = {"label": "BoundedContext", "id": "bc-pay", "name": "결제",
                         "description": "기존 결제"}
    modify = {"boundedContexts": [{"op": "MODIFY", "entityId": "bc-pay", "entityTitle": "결제",
                                   "fields": {"description": {"before": "기존 결제",
                                                              "after": "결제 + 부분 환불"}}}]}
    g.proposal.update(_proposal(strategic=modify, tactical=[]))
    _accept()
    assert g.nodes["bc-pay"]["description"] == "결제 + 부분 환불"
    [eff] = g.rels_of("EFFECT")
    assert eff["props"]["changeType"] == "MODIFY"

    _revoke()
    assert g.nodes["bc-pay"]["description"] == "기존 결제"  # 기존 노드는 지우지 않고 값만 되돌린다
    assert g.rels_of("EFFECT") == []


def test_revoke_with_code_revert_reports_git_result(env):
    env.graph.proposal["status"] = "ACCEPTED"
    env.sandbox.revert_ok, env.sandbox.revert_error = False, "revert conflict"
    result = _revoke(revert_code=True, comment="잘못 승인")
    assert env.sandbox.calls == [("revert_merge_commit", PID, ROOT)]
    assert result["codeRevert"] == {"success": False, "error": "revert conflict"}
    # 코드 되돌림이 실패해도 그래프 수거와 상태 전환은 진행된다(경고만)
    assert env.graph.proposal["status"] == "PENDING_ACCEPTANCE"
    assert env.graph.history()[-1]["comment"] == "잘못 승인"
    assert any(entry["category"] == "proposal_lifecycle.revoke.git_warn" for entry in env.logs)


def test_revoke_code_revert_without_project_root(env):
    env.graph.proposal.update({"status": "ACCEPTED", "projectRoot": None})
    result = _revoke(revert_code=True)
    assert result["codeRevert"] == {"success": False, "error": "projectRoot 없음"}
    assert env.sandbox.calls == []
