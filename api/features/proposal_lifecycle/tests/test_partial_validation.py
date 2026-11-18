"""D-2 ⑭ 부분 재검증 — `?scenarioIds=` 로 고른 항목만 다시 재고 기존 결과에 **병합**한다.

Neo4j·Claude CLI 없이 돈다: 세션은 Proposal 한 줄을 흉내 내는 가짜, 스킬 실행은
미리 정한 JSON 을 내는 가짜로 바꾼다.
"""

from __future__ import annotations

import asyncio
import json
import re
from contextlib import contextmanager

import pytest
from fastapi import HTTPException

from api.features.proposal_lifecycle.routes import proposals_testing as routes
from api.features.proposal_lifecycle.services import test_runner as tr

PID = "PRO-021"


def _existing():
    return {
        "proposalId": PID, "totalScenarios": 3, "passed": 1, "failed": 1, "skipped": 1,
        "items": [
            {"scenarioId": "SC-001", "category": "acceptance", "storyId": "us:1", "storyTitle": "주문",
             "scenario": "주문하면 생성", "result": "PASS", "reason": None},
            {"scenarioId": "SC-002", "category": "acceptance", "storyId": "us:2", "storyTitle": "환불",
             "scenario": "환불하면 취소", "result": "FAIL", "reason": "환불 API 없음"},
            {"scenarioId": "SC-003", "category": "structural", "storyId": "agg:refund", "storyTitle": "환불 Aggregate",
             "scenario": "PartialRefundAmount VO", "result": "SKIPPED", "reason": "파일 못 찾음"},
        ],
    }


# ── 순수 로직 ──────────────────────────────────────────────────────────────

def test_parse_scenario_ids_accepts_comma_and_repeat():
    assert tr.parse_scenario_ids(None) == []
    assert tr.parse_scenario_ids("SC-003, SC-007,,SC-003") == ["SC-003", "SC-007"]
    assert tr.parse_scenario_ids(["SC-001", "SC-002,SC-001"]) == ["SC-001", "SC-002"]


def test_merge_replaces_only_selected_and_keeps_the_rest():
    existing = tr.stamp_attempts(_existing())
    fresh = {"items": [{"scenarioId": "SC-002", "result": "PASS", "reason": None, "scenario": "환불하면 취소"}]}

    merged = tr.merge_partial_results(existing, fresh, ["SC-002"])

    by = {it["scenarioId"]: it for it in merged["items"]}
    assert [it["scenarioId"] for it in merged["items"]] == ["SC-001", "SC-002", "SC-003"]
    assert by["SC-002"]["result"] == "PASS"
    assert by["SC-002"]["attempts"] == 2
    # 통과해도 직전 실패 사유는 남는다 — 무엇이 고쳐졌는지 보이게.
    assert by["SC-002"]["lastReason"] == "환불 API 없음"
    # 고르지 않은 항목은 그대로.
    assert by["SC-001"] == {**_existing()["items"][0], "attempts": 1, "lastReason": None}
    assert by["SC-003"]["result"] == "SKIPPED" and by["SC-003"]["attempts"] == 1
    assert (merged["totalScenarios"], merged["passed"], merged["failed"], merged["skipped"]) == (3, 2, 0, 1)
    # 원본은 건드리지 않는다.
    assert existing["items"][1]["result"] == "FAIL"


def test_merge_keeps_previous_verdict_when_item_missing_from_fresh():
    """새 결과에 그 항목이 없으면 FAIL 을 유지한다 — SKIP 으로 바뀌어 Accept 게이트를 빠져나가지 않게."""
    merged = tr.merge_partial_results(_existing(), {"items": []}, ["SC-002"])
    it = next(i for i in merged["items"] if i["scenarioId"] == "SC-002")
    assert it["result"] == "FAIL"
    assert it["attempts"] == 2
    assert "이전 판정을 유지" in it["lastReason"]
    assert merged["failed"] == 1


def test_merge_single_target_tolerates_renumbered_id_and_drops_extras():
    fresh = {"items": [{"scenarioId": "SC-999", "result": "FAIL", "reason": "여전히 없음"}]}
    merged = tr.merge_partial_results(_existing(), fresh, ["SC-002"])
    it = next(i for i in merged["items"] if i["scenarioId"] == "SC-002")
    assert it["result"] == "FAIL" and it["reason"] == "여전히 없음" and it["lastReason"] == "여전히 없음"
    assert len(merged["items"]) == 3  # SC-999 는 새 항목으로 끼지 않는다


def test_partial_prompt_lists_only_targets_and_filters_tactical():
    targets, missing = tr.select_partial_targets(_existing(), ["SC-002", "SC-003"])
    assert missing == []
    tactical = json.dumps([
        {"nodeId": "agg:refund", "nodeLabel": "Aggregate", "nodeTitle": "환불 Aggregate"},
        {"nodeId": "agg:order", "nodeLabel": "Aggregate", "nodeTitle": "주문 Aggregate"},
    ], ensure_ascii=False)

    prompt = tr._build_partial_prompt(PID, targets, "/wt", tactical)

    assert "SC-002" in prompt and "SC-003" in prompt and "SC-001" not in prompt
    assert "agg:refund" in prompt and "agg:order" not in prompt
    assert "주어진 값 그대로" in prompt


# ── 세션 가짜 ──────────────────────────────────────────────────────────────

class _Rec(dict):
    def get(self, k, d=None):
        return super().get(k, d)


class _Res:
    def __init__(self, rec):
        self._rec = rec

    def single(self):
        return self._rec

    def data(self):
        return [] if self._rec is None else [self._rec]


class FakeProposalSession:
    """`MATCH (p:Proposal {id: $id}) RETURN p.x AS y` 와 `SET p.x = ...` 만 흉내 낸다."""

    def __init__(self, row):
        self.row = dict(row)
        self.writes: list[dict] = []

    @contextmanager
    def __call__(self, *a, **kw):
        yield self

    def run(self, query, **params):
        q = " ".join(query.split())
        if "EFFECT" in q:
            return _Res(None)
        if " SET " in f" {q} ":
            sets = re.findall(r"p\.(\w+) = (\$\w+|'[^']*'|null)", q)
            change = {}
            for field, val in sets:
                if val.startswith("$"):
                    change[field] = params[val[1:]]
                elif val == "null":
                    change[field] = None
                else:
                    change[field] = val.strip("'")
            self.row.update(change)
            self.writes.append(change)
            return _Res(None)
        aliases = re.findall(r"p\.(\w+) AS (\w+)", q)
        return _Res(_Rec({alias: self.row.get(field) for field, alias in aliases}))


@pytest.fixture
def fake(monkeypatch):
    row = {"id": PID, "status": "PENDING_ACCEPTANCE", "statusHistory": "[]",
           "testResults": json.dumps(tr.stamp_attempts(_existing()), ensure_ascii=False),
           "sandboxWorktreePath": None, "tacticalDiff": "[]", "strategicDiff": "{}"}
    sess = FakeProposalSession(row)
    monkeypatch.setattr(tr, "get_session", sess)
    monkeypatch.setattr(routes, "get_session", sess)
    prompts: list[str] = []
    reply = {"items": [{"scenarioId": "SC-002", "category": "acceptance", "result": "PASS", "reason": None}]}

    async def fake_lines(root, name, prompt, **kw):
        prompts.append(prompt)
        for line in json.dumps(reply, ensure_ascii=False).splitlines():
            yield line

    async def fake_once(root, name, prompt, **kw):
        prompts.append(prompt)
        return json.dumps(reply, ensure_ascii=False)

    monkeypatch.setattr(tr, "run_skill_lines", fake_lines)
    monkeypatch.setattr(tr, "run_skill_once", fake_once)
    monkeypatch.setattr(tr.SmartLogger, "log", lambda *a, **k: None)
    monkeypatch.setattr(routes.SmartLogger, "log", lambda *a, **k: None)
    return sess, prompts


def _collect(agen):
    async def go():
        return [ev async for ev in agen]
    return asyncio.run(go())


def test_stream_partial_merges_into_saved_results(fake):
    sess, prompts = fake
    events = _collect(tr.stream_validation(PID, ["SC-002"]))

    names = [e for e, _ in events]
    assert names[0] == "phase" and names[-1] == "done"
    results = next(d for e, d in events if e == "results")
    assert len(results["items"]) == 3
    assert results["passed"] == 2 and results["failed"] == 0
    assert events[-1][1]["scenarioIds"] == ["SC-002"]

    saved = json.loads(sess.row["testResults"])
    assert next(i for i in saved["items"] if i["scenarioId"] == "SC-002")["attempts"] == 2
    assert sess.row["status"] == "PENDING_ACCEPTANCE"
    # 결과를 비우는 쓰기(testResults = null)가 한 번도 없었다.
    assert all(w.get("testResults", "x") is not None for w in sess.writes)
    assert len(prompts) == 1 and "SC-001" not in prompts[0]


def test_stream_partial_rejects_unknown_id_without_touching_results(fake):
    sess, prompts = fake
    before = sess.row["testResults"]
    events = _collect(tr.stream_validation(PID, ["SC-404"]))
    assert events[-1][0] == "error" and events[-1][1]["status"] == 400
    assert sess.row["testResults"] == before and prompts == []


def test_stream_partial_requires_existing_results(fake):
    sess, _ = fake
    sess.row["testResults"] = None
    events = _collect(tr.stream_validation(PID, ["SC-002"]))
    assert events[-1][0] == "error" and events[-1][1]["status"] == 409


def test_full_stream_stamps_attempts(fake):
    sess, _ = fake
    sess.row["tacticalDiff"] = json.dumps([{"nodeLabel": "Aggregate", "nodeId": "agg:x"}])
    events = _collect(tr.stream_validation(PID))
    results = next(d for e, d in events if e == "results")
    assert results["items"][0]["attempts"] == 1


def test_post_validate_partial_route(fake):
    sess, prompts = fake

    async def go():
        out = await routes.validate_proposal(PID, scenarioIds=["SC-002"])
        await asyncio.sleep(0)  # create_task 로 띄운 실행을 한 번 돌린다
        for _ in range(5):
            await asyncio.sleep(0)
        return out

    out = asyncio.run(go())
    assert out == {"proposalId": PID, "status": "VALIDATING", "scenarioIds": ["SC-002"]}
    saved = json.loads(sess.row["testResults"])
    assert len(saved["items"]) == 3
    assert next(i for i in saved["items"] if i["scenarioId"] == "SC-002")["result"] == "PASS"


def test_post_validate_partial_route_errors(fake):
    sess, _ = fake
    with pytest.raises(HTTPException) as e:
        asyncio.run(routes.validate_proposal(PID, scenarioIds=["SC-404"]))
    assert e.value.status_code == 400
    sess.row["status"] = "DRAFT"
    with pytest.raises(HTTPException) as e:
        asyncio.run(routes.validate_proposal(PID, scenarioIds=["SC-002"]))
    assert e.value.status_code == 400


def test_sandbox_head_without_worktree(fake):
    out = asyncio.run(routes.get_sandbox_head(PID))
    assert out == {"proposalId": PID, "head": None}


def test_sandbox_head_reads_worktree_commit(fake, tmp_path):
    import shutil
    import subprocess

    if not shutil.which("git"):
        pytest.skip("git 없음")
    sess, _ = fake
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    (tmp_path / "a.txt").write_text("x", encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=tmp_path, check=True)
    subprocess.run(["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "init"],
                   cwd=tmp_path, check=True)
    sha = subprocess.run(["git", "rev-parse", "HEAD"], cwd=tmp_path, capture_output=True,
                         text=True, check=True).stdout.strip()
    sess.row["sandboxWorktreePath"] = str(tmp_path)
    assert asyncio.run(routes.get_sandbox_head(PID))["head"] == sha
