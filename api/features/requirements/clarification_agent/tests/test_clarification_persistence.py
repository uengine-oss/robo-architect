"""D-4 ① — 명확화 flags · coverage 가 **백엔드를 다시 띄워도** 남는다.

그래프 저장소를 가짜(dict)로 갈아 끼우고, 메모리(`_FLAGS`/`_COVERAGE`)를 비워
"재시작" 을 흉내 낸다. 재시작 뒤에도 그래프에서 읽혀야 한다.
Cypher 모양은 FakeSession 으로 잰다(Ontological 호환: 단순 MATCH/MERGE/SET).
"""

from __future__ import annotations

import pytest

from api.features.requirements.clarification_agent import clarification_coverage as cov
from api.features.requirements.clarification_agent import clarification_flags as flags
from api.features.requirements.clarification_agent import clarity_score as cs
from api.features.requirements.clarification_contracts import (
    AmbiguityCategory,
    ClarificationQuestionDTO,
    CoverageRow,
    CoverageStatus,
    QuestionType,
)


class FakeFlagStore:
    def __init__(self):
        self.props: dict[str, str] = {}  # usId -> JSON
        self.loads = 0

    def load_all(self):
        self.loads += 1
        return {k: flags.FlagInfo.from_json(k, v) for k, v in self.props.items()}

    def write(self, infos):
        for i in infos:
            self.props[i.userStoryId] = i.to_json()

    def clear(self, ids):
        for i in ids:
            self.props.pop(i, None)


class FakeCoverageStore:
    def __init__(self):
        self.props: dict[str, str] = {}

    def load(self, st, sid):
        return cov.ScopeCoverage.from_json(st, sid, self.props.get(f"{st}:{sid}"))

    def save(self, c):
        self.props[f"{c.scopeType}:{c.scopeId}"] = c.to_json()

    def clear(self, st, sid):
        self.props.pop(f"{st}:{sid}", None)


@pytest.fixture
def stores(monkeypatch):
    fs, cstore = FakeFlagStore(), FakeCoverageStore()
    monkeypatch.setattr(flags, "_GRAPH", fs)
    monkeypatch.setattr(cov, "_GRAPH", cstore)
    monkeypatch.setattr(flags, "_FLAGS", {})
    monkeypatch.setattr(cov, "_COVERAGE", {})
    return fs, cstore


def _restart(monkeypatch):
    monkeypatch.setattr(flags, "_FLAGS", {})
    monkeypatch.setattr(cov, "_COVERAGE", {})


def _q(qid, ids, cat):
    return ClarificationQuestionDTO(
        questionId=qid, category=cat, questionType=QuestionType.short_answer,
        questionText="?", referencedRequirementIds=ids,
    )


def test_flags_survive_restart(stores, monkeypatch):
    flags.record_flags(
        session_id="s1", scope_type="feature", scope_id="f1",
        questions=[_q("q1", ["us-a", "us-b"], AmbiguityCategory.functional_scope)],
    )
    _restart(monkeypatch)
    snap = flags.snapshot()
    assert set(snap) == {"us-a", "us-b"}
    assert snap["us-a"].categories == [AmbiguityCategory.functional_scope.value]
    assert snap["us-a"].scopeId == "f1"


def test_flag_merge_reads_graph_after_restart(stores, monkeypatch):
    flags.record_flags(session_id="s1", scope_type="feature", scope_id="f1",
                       questions=[_q("q1", ["us-a"], AmbiguityCategory.functional_scope)])
    _restart(monkeypatch)
    flags.record_flags(session_id="s1", scope_type="feature", scope_id="f1",
                       questions=[_q("q2", ["us-a"], AmbiguityCategory.non_functional)])
    info = flags.snapshot()["us-a"]
    assert info.questionIds == ["q1", "q2"]


def test_clear_flag_and_session_persist(stores, monkeypatch):
    fs, _ = stores
    flags.record_flags(session_id="s1", scope_type="feature", scope_id="f1",
                       questions=[_q("q1", ["us-a", "us-b"], AmbiguityCategory.functional_scope)])
    flags.record_flags(session_id="s2", scope_type="feature", scope_id="f1",
                       questions=[_q("q9", ["us-c"], AmbiguityCategory.functional_scope)])
    flags.clear_flag("us-a")
    _restart(monkeypatch)
    flags.clear_session_flags("s2")  # 메모리가 비어도 그래프에서 찾아 지운다
    assert set(fs.props) == {"us-b"}


def test_coverage_survives_restart_and_feeds_radar(stores, monkeypatch):
    cov.record_coverage(
        session_id="s1", scope_type="bounded_context", scope_id="bc1",
        rows=[CoverageRow(category=AmbiguityCategory.functional_scope, status=CoverageStatus.outstanding)],
    )
    cov.mark_resolved("bounded_context", "bc1", AmbiguityCategory.functional_scope)
    _restart(monkeypatch)
    got = cov.get_coverage("bounded_context", "bc1")
    assert got is not None
    assert got.rows[AmbiguityCategory.functional_scope] == CoverageStatus.resolved

    # 레이더 읽기 자리 — 재시작 뒤에도 agent coverage 가 반영된다
    monkeypatch.setattr(cs, "read_scope_log", lambda _ids: [])
    scores = cs.compute_clarity_scores_for_scope(["us-a"], "bounded_context", "bc1")
    row = next(s for s in scores.scores if s.category == AmbiguityCategory.functional_scope)
    assert row.status == CoverageStatus.resolved


def test_sticky_resolved_across_sessions_after_restart(stores, monkeypatch):
    cov.record_coverage(session_id="s1", scope_type="project", scope_id="*",
                        rows=[CoverageRow(category=AmbiguityCategory.non_functional,
                                          status=CoverageStatus.resolved)])
    _restart(monkeypatch)
    cov.record_coverage(session_id="s2", scope_type="project", scope_id="*",
                        rows=[CoverageRow(category=AmbiguityCategory.non_functional,
                                          status=CoverageStatus.outstanding)])
    assert cov.get_coverage("project", "*").rows[AmbiguityCategory.non_functional] == CoverageStatus.resolved


def test_clarity_reads_flags_once(stores, monkeypatch):
    fs, _ = stores
    flags.record_flags(session_id="s1", scope_type="feature", scope_id="f1",
                       questions=[_q("q1", ["us-a"], AmbiguityCategory.functional_scope)])
    monkeypatch.setattr(cs, "read_scope_log", lambda _ids: [])
    before = fs.loads
    r = cs.compute_clarity_scores([f"us-{i}" for i in "abcdefgh"])
    assert r.flaggedUserStories == 1
    assert fs.loads - before == 1


def test_graph_failure_falls_back_to_memory(monkeypatch):
    class Boom:
        def __getattr__(self, _):
            def _f(*a, **k):
                raise RuntimeError("db down")
            return _f

    monkeypatch.setattr(flags, "_GRAPH", Boom())
    monkeypatch.setattr(flags, "_FLAGS", {})
    flags.record_flags(session_id="s1", scope_type="feature", scope_id="f1",
                       questions=[_q("q1", ["us-a"], AmbiguityCategory.functional_scope)])
    assert set(flags.snapshot()) == {"us-a"}


# ── 실제 Cypher 모양(Ontological 호환 — 단순 문법만) ─────────────────────


class FakeSession:
    def __init__(self, log):
        self.log = log

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def run(self, q, **params):
        self.log.append((q, params))

        class R(list):
            def single(self_inner):
                return None

        return R()


def test_graph_cypher_is_simple(monkeypatch):
    import api.platform.neo4j as neo

    log: list = []
    monkeypatch.setattr(neo, "get_session", lambda *a, **k: FakeSession(log))
    flags.GraphFlagStore().write([flags.FlagInfo(userStoryId="us-a", sessionId="s1")])
    flags.GraphFlagStore().clear(["us-a"])
    cov.GraphCoverageStore().save(cov.ScopeCoverage(scopeType="feature", scopeId="f1", sessionId="s1"))
    cov.GraphCoverageStore().save(cov.ScopeCoverage(scopeType="project", scopeId="*", sessionId="s1"))
    cov.GraphCoverageStore().save(
        cov.ScopeCoverage(scopeType="feature", scopeId="__unassigned__bc1", sessionId="s1"))
    assert cov.GraphCoverageStore().load("bounded_context", "bc1") is None
    qs = [q for q, _ in log]
    assert qs[0] == "MATCH (us:UserStory {id: $id}) SET us.clarificationFlag = $raw"
    assert qs[1] == "MATCH (us:UserStory {id: $id}) SET us.clarificationFlag = null"
    assert qs[2] == "MATCH (n:Feature {id: $id}) SET n.clarificationCoverage = $raw"
    assert qs[3] == "MERGE (n:ClarificationCoverage {id: $id}) SET n.coverage = $raw"
    assert log[3][1]["id"] == "project:*"
    assert qs[4].startswith("MERGE (n:ClarificationCoverage")
    assert qs[5] == "MATCH (n:BoundedContext {id: $id}) RETURN n.clarificationCoverage AS raw"
    for q in qs:
        assert "_id" not in q and "startNode" not in q
