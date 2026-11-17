# -*- coding: utf-8 -*-
"""**중재가 근거를 지우지 않는다** — 진 쪽은 보조 근거로 남는다 (2026-09-30).

## 왜 바꿨나

지우던 때의 실측(hr-sample, 프로세스 3개, task 29개):

    검증기가 수락한 매핑        81
    그래프에 남은 것           35      ← 43개를 중재가 지웠다
    매핑된 task              17 / 29  ← **12개가 근거를 통째로 잃었다**

그 12개는 **전부 중재에서만** 잃었다 — Step 1·문턱 단계 손실은 0건이고
(`recall@20 = 19/19`, `RESCUED 0건`) 모든 task 가 `accepted ≥ 1` 을 받았다.

원인은 레거시의 룰 단위가 설계의 task 단위보다 **굵다**는 것이다. `applyLeave` 한
메서드가 입력 검증·DTO·상태·저장을 다 하므로 그 룰은 `사전 신청 기한 확인`·
`증빙 서류 확인`·`중복 신청 확인` 의 **유일한** 근거였다. 1:1 을 강제하면 굵은 룰
하나당 task N−1 개가 반드시 빈다.

## 여기서 재는 것

  ① 경합에서 진 쪽을 **지우지 않는다** — `supporting` 으로 내린다
  ② 이긴 쪽은 `primary` 다
  ③ `verdict.reject`(횡단 유틸 판정)는 **그대로 지운다** — "집이 어디냐" 가 아니라
     "근거가 아니다" 라는 판정이다
  ④ 새로 저장되는 매핑은 `primary` 로 시작한다
  ⑤ 승격이 역할을 이어 나른다 — `(UserStory)-[:SOURCED_FROM {evidence_role}]->(Rule)`

①이 핵심이다. ②만 재면 진 쪽을 지우면서도 통과한다.
"""

from __future__ import annotations

import asyncio
import pathlib
from contextlib import contextmanager

import pytest

from api.features.ingestion.hybrid import contracts, explore_service
from api.features.ingestion.hybrid.mapper.cross_process_arbitrator import ArbitrationVerdict
from api.features.ingestion.hybrid.ontology import neo4j_ops

SID = "sess_test"
RULE = "rule_applyleave"


def _process() -> contracts.BpmProcess:
    return contracts.BpmProcess(id="proc_1", name="휴가신청", session_id=SID)


def _task(tid: str, name: str) -> contracts.BpmTaskDTO:
    return contracts.BpmTaskDTO(id=tid, name=name, process_id="proc_1")


def _rule() -> contracts.RuleDTO:
    return contracts.RuleDTO(
        id=RULE, given="신청이 들어오면", when="applyLeave 를 부르면", then="저장한다",
        source_function="applyLeave",
    )


class _Recorder:
    """중재가 무엇을 호출했는지만 모은다."""

    def __init__(self) -> None:
        self.roles: list[tuple[str, str]] = []   # (task_id, role)
        self.deletes: list[str] = []             # task_id

    def set_role(self, sid, task_id, rule_id, role, rationale=None):
        self.roles.append((task_id, role))

    def delete(self, sid, task_id, rule_id):
        self.deletes.append(task_id)


@pytest.fixture
def wired(monkeypatch: pytest.MonkeyPatch) -> _Recorder:
    """세 task 가 같은 룰을 다투는 상황을 만든다. 그래프는 건드리지 않는다."""
    rec = _Recorder()
    claims = [
        {"process_id": "proc_1", "task_id": "t_home", "rationale": "", "score": 0.6},
        {"process_id": "proc_1", "task_id": "t_lose1", "rationale": "", "score": 0.5},
        {"process_id": "proc_1", "task_id": "t_lose2", "rationale": "", "score": 0.4},
    ]
    tasks = {
        "t_home": _task("t_home", "휴가 신청서 접수"),
        "t_lose1": _task("t_lose1", "증빙 서류 확인"),
        "t_lose2": _task("t_lose2", "중복 신청 확인"),
    }
    monkeypatch.setattr(explore_service, "_detect_contested_claims",
                        lambda sid: [(RULE, claims)])
    monkeypatch.setattr(explore_service, "_build_session_dtos",
                        lambda sid: ({}, {"proc_1": _process()}, {},
                                     [_rule()], tasks, {}))
    monkeypatch.setattr(explore_service, "build_rule_contexts", lambda rules: [])
    monkeypatch.setattr(explore_service, "set_task_rule_mapping_role", rec.set_role)
    monkeypatch.setattr(explore_service, "delete_task_rule_mapping", rec.delete)
    return rec


def _run() -> dict:
    """`asyncio.run` 으로 돈다 — 이 저장소에는 pytest-asyncio 가 없다."""
    events: list[dict] = []

    async def sink(ev):
        events.append(ev)

    async def go():
        return await explore_service.post_explore_arbitration(SID, sink=sink)

    out = asyncio.run(go())
    out["_events"] = events
    return out


def test_진_쪽은_지우지_않고_보조로_내린다(wired, monkeypatch):
    async def verdict(rule, ctx, entries):
        return ArbitrationVerdict(reject=False, home_process_id="proc_1",
                                  home_task_id="t_home", rationale="applyLeave 가 접수다")
    monkeypatch.setattr(explore_service, "arbitrate_rule_home", verdict)

    out = _run()

    assert wired.deletes == [], f"진 쪽을 지웠다: {wired.deletes} — task 가 근거를 잃는다"
    assert dict(wired.roles) == {
        "t_home": "primary", "t_lose1": "supporting", "t_lose2": "supporting",
    }
    assert out["demoted"] == 2
    assert out["deleted"] == 0
    assert out["resolved"] == 1


def test_전부물림은_그대로_지운다(wired, monkeypatch):
    """횡단 유틸 판정은 '근거가 아니다' 이므로 남기지 않는다."""
    async def verdict(rule, ctx, entries):
        return ArbitrationVerdict(reject=True, rationale="로깅 유틸이다")
    monkeypatch.setattr(explore_service, "arbitrate_rule_home", verdict)

    out = _run()

    assert sorted(wired.deletes) == ["t_home", "t_lose1", "t_lose2"]
    assert wired.roles == [], "전부물림인데 역할을 적었다"
    assert out["deleted"] == 3
    assert out["demoted"] == 0
    assert out["rejected"] == 1


def test_요약_로그가_보조와_삭제를_따로_센다(wired, monkeypatch):
    async def verdict(rule, ctx, entries):
        return ArbitrationVerdict(reject=False, home_process_id="proc_1",
                                  home_task_id="t_home", rationale="r")
    monkeypatch.setattr(explore_service, "arbitrate_rule_home", verdict)

    lines: list[str] = []
    monkeypatch.setattr(explore_service.SmartLogger, "log",
                        classmethod(lambda cls, level, msg, **kw: lines.append(msg)))

    _run()

    end = [x for x in lines if x.startswith("중재 끝")]
    assert end, "마무리 요약이 없다 — 손실 규모를 사후에 되짚을 수 없다"
    assert "보조로 내린 매핑 2개" in end[0]
    assert "삭제한 매핑 0개" in end[0]


# ── 쓰기 쪽: 그래프에 무엇을 적는가 ────────────────────────────────────────


class _FakeSession:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict]] = []

    def run(self, query: str, **params):
        self.calls.append((query, params))
        return _FakeResult()


class _FakeResult:
    def single(self):
        return {"n": 0}


@pytest.fixture
def fake_graph(monkeypatch: pytest.MonkeyPatch) -> _FakeSession:
    s = _FakeSession()

    @contextmanager
    def _session():
        yield s

    monkeypatch.setattr(neo4j_ops, "get_session", _session)
    return s


def test_역할을_엣지와_감사노드에_같이_적는다(fake_graph):
    neo4j_ops.set_task_rule_mapping_role(SID, "t_lose1", RULE, "supporting", "사유")

    text = " ".join(q for q, _ in fake_graph.calls)
    assert "rel.evidence_role = $role" in text
    assert "am.evidence_role = $role" in text
    assert all(p.get("role") == "supporting" for _, p in fake_graph.calls)
    # 감사 노드만 바뀌고 엣지가 안 바뀌면 화면과 그래프가 어긋난다.
    assert len(fake_graph.calls) == 2


def test_모르는_역할은_거부한다(fake_graph):
    with pytest.raises(ValueError):
        neo4j_ops.set_task_rule_mapping_role(SID, "t", RULE, "primaryy")
    assert fake_graph.calls == [], "거부하면서 쓰기도 했다"


def test_새로_저장되는_매핑은_primary_다(fake_graph):
    neo4j_ops.save_mappings(SID, [contracts.ActivityRuleMapping(
        task_id="t_home", rule_id=RULE, score=0.6, method="agentic", reviewed=True,
    )])
    text = " ".join(q for q, _ in fake_graph.calls)
    assert "rel.evidence_role = 'primary'" in text
    assert "am.evidence_role = 'primary'" in text


# ── 읽기·승격 쪽: 역할이 이어지는가 ────────────────────────────────────────


def test_승격이_역할을_이어_나른다():
    """`(UserStory)-[:SOURCED_FROM]->(Rule)` 이 REALIZED_BY 의 역할을 복사한다."""
    src = pathlib.Path(
        "api/features/ingestion/hybrid/event_storming_bridge/promote_to_es.py"
    ).read_text(encoding="utf-8")
    assert "rel.evidence_role = coalesce(m.evidence_role, 'primary')" in src, (
        "승격에서 역할이 끊기면 ES 요소의 출처가 주/보조를 구분하지 못한다"
    )


def test_스냅샷과_출처_조회가_역할을_내보낸다():
    ops = pathlib.Path(
        "api/features/ingestion/hybrid/ontology/neo4j_ops.py"
    ).read_text(encoding="utf-8")
    assert "coalesce(link.evidence_role, 'primary') AS evidence_role" in ops
    assert '"evidence_role": row.get("evidence_role") or "primary"' in ops

    trace = pathlib.Path(
        "api/features/canvas_graph/routes/traceability.py"
    ).read_text(encoding="utf-8")
    assert "coalesce(sf.evidence_role, 'primary') AS evidence_role" in trace
    # 주 근거가 먼저 보여야 한다.
    # 정렬 키는 갈래마다 다르다 — 재는 것은 **주 근거가 먼저 온다**는 것뿐이다.
    assert "ORDER BY evidence_role" in trace
