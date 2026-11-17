"""2026-09-29 재보정 가드 — 문턱이 정답을 잘라내던 자리.

**이 파일이 지키는 것은 숫자가 아니라 사건이다.** hr-sample(Java) 을 넣었을 때
월근태마감 프로세스의 task 8개가 전부 후보 0으로 끝났다. 어휘 문제가 아니라
Step 1 의 절대 코사인 문턱(0.45)이 그 corpus 의 분포 전체보다 높아서였다 —
정답인 `MonthlyClosingService` 의 메서드가 0.37~0.39 였다.

그래서 여기서는 **낮은 점수에서도 후보가 살아남는지를 행동으로 잰다.** 상수만
비교하면 누군가 값을 그대로 둔 채 `retrieve_top_modules` 안에 새 문턱을 넣는
경우를 못 잡는다.

순수 검사 — Neo4j·LLM·임베딩 API 를 타지 않는다.
"""

from __future__ import annotations

import asyncio
import math

import pytest

from api.features.ingestion.hybrid.contracts import (
    BpmProcess,
    BpmTaskDTO,
    RuleContext,
    RuleDTO,
)
from api.features.ingestion.hybrid.mapper import agentic_retriever as ar
from api.features.ingestion.hybrid.mapper import module_retriever as mr
from api.features.ingestion.hybrid.mapper.agent_validator import ValidationVerdict


# --------------------------------------------------------------------------
# 각도로 코사인을 정확히 지정하는 가짜 임베더. 2차원 단위벡터라서
# cos(a, b) = cos(θa - θb) 가 그대로 성립한다 — 근사값이 아니라 지정값이다.
# --------------------------------------------------------------------------
class AngleCache:
    def __init__(self, angles: dict[str, float]) -> None:
        self.angles = angles

    def _vec(self, text: str) -> list[float]:
        for key, theta in self.angles.items():
            if key in text:
                return [math.cos(theta), math.sin(theta)]
        return [math.cos(math.pi / 2), math.sin(math.pi / 2)]  # 직교 = 코사인 0

    def embed(self, text: str) -> list[float]:
        return self._vec(text) if (text or "").strip() else []

    def embed_many(self, texts):
        return [self.embed(t) for t in texts]


QUERY_MARK = "월 근태 마감"
MODULE_MARK = "MonthlyClosingService"
RULE_MARK = "마감 확정"


def _cache(module_cos: float, rule_cos: float) -> AngleCache:
    return AngleCache({
        QUERY_MARK: 0.0,
        MODULE_MARK: math.acos(module_cos),
        RULE_MARK: math.acos(rule_cos),
    })


def _fixture():
    process = BpmProcess(id="proc_1", name=QUERY_MARK, domain_keywords=[],
                         session_id="sess_1")
    task = BpmTaskDTO(id="task_1", name="확정", process_id="proc_1")
    rule = RuleDTO(id="rule_1", given="g", when="w", then="t",
                   source_function_id="m_1", source_function="confirmClosing",
                   title=RULE_MARK)
    ctx = RuleContext(rule_id="rule_1", given=RULE_MARK, when="w", then="t",
                      source_function_id="m_1", source_function="confirmClosing")
    rows = [{"fqn": "m_1", "name": "confirmClosing",
             "summary": f"{MODULE_MARK} 의 마감 확정 메서드", "stereotype": None}]
    return process, task, rule, ctx, rows


def _run(monkeypatch, module_cos: float, rule_cos: float,
         rows=None, containment=None, **kwargs):
    process, task, rule, ctx, default_rows = _fixture()
    monkeypatch.setattr(ar, "fetch_all_modules", lambda: rows or default_rows)
    monkeypatch.setattr(ar, "fetch_containment", lambda: containment or {})
    calls: list[int] = []

    async def fake_validate(_p, _t, candidates, **_kw):
        calls.append(len(candidates))
        return [ValidationVerdict(rule_id=c.rule.id, verdict="accept", rationale="r")
                for c in candidates]

    monkeypatch.setattr(ar, "validate_candidates", fake_validate)
    result = asyncio.run(ar.run_agentic_retrieval(
        process, [task], [], [rule], [ctx],
        cache=_cache(module_cos, rule_cos), **kwargs,
    ))
    return result, calls


# --------------------------------------------------------------------------
# 재발 방지 — 09-29 에 실제로 0이 나온 점수대
# --------------------------------------------------------------------------
def test_module_below_old_floor_still_yields_candidates(monkeypatch):
    """모듈 0.44 · 룰 0.42 — 옛 문턱(0.45/0.45)이면 둘 다 잘려 후보 0이었다."""
    result, calls = _run(monkeypatch, module_cos=0.44, rule_cos=0.42)
    assert calls == [1], "검증기가 후보를 받지 못했다 — Step 1/2 문턱이 다시 잘랐다"
    assert len(result.accepted) == 1


def test_process_is_not_skipped_below_old_cosine_gate(monkeypatch):
    """프로세스 최대 코사인 0.44 < 옛 게이트 0.55 — 통째로 건너뛰던 자리."""
    result, _ = _run(monkeypatch, module_cos=0.44, rule_cos=0.42)
    assert result.accepted, "프로세스 단위 코사인 게이트가 되살아났다"


def test_empty_module_corpus_short_circuits(monkeypatch):
    """모듈이 0개면 task 마다 경고를 흘리지 않고 한 번에 끊는다."""
    process, task, rule, ctx, _ = _fixture()
    monkeypatch.setattr(ar, "fetch_all_modules", list)
    monkeypatch.setattr(ar, "fetch_containment", dict)
    called: list[int] = []

    async def fake_validate(*_a, **_kw):
        called.append(1)
        return []

    monkeypatch.setattr(ar, "validate_candidates", fake_validate)
    result = asyncio.run(ar.run_agentic_retrieval(
        process, [task], [], [rule], [ctx], cache=_cache(0.9, 0.9),
    ))
    assert result.accepted == []
    assert called == [], "모듈이 없는데 검증기를 불렀다 — LLM 비용이 샌다"


# --------------------------------------------------------------------------
# 상수 — 왜 이 값인지는 각 상수 위 주석의 실측에 있다
# --------------------------------------------------------------------------
def test_bl_floor_recalibrated():
    assert ar.MIN_BL_INCLUSION == 0.40


def test_reject_floor_tracks_bl_floor():
    """따로 적어 두면 한쪽만 재보정됐을 때 화면이 없는 구간을 기다린다."""
    assert ar.REJECT_NEAR_MISS_FLOOR == ar.MIN_BL_INCLUSION


def test_module_absolute_floor_is_only_a_sanity_bound():
    """절대 하한으로 자르지 않는다 — 자르는 일은 top_k 가 한다."""
    assert mr.MIN_MODULE_INCLUSION <= 0.10


def test_process_gate_is_off_by_default(monkeypatch):
    monkeypatch.delenv("HYBRID_PROCESS_GATE", raising=False)
    assert mr.process_gate_enabled() is False


@pytest.mark.parametrize("value,expected", [
    ("on", True), ("1", True), ("true", True), ("YES", True),
    ("off", False), ("0", False), ("", False), ("nope", False),
])
def test_process_gate_env_toggle(monkeypatch, value, expected):
    monkeypatch.setenv("HYBRID_PROCESS_GATE", value)
    assert mr.process_gate_enabled() is expected


def test_process_gate_when_enabled_still_skips(monkeypatch):
    """되살릴 수 있어야 한다 — 대량 배치에서 비용이 문제가 되는 경우."""
    monkeypatch.setenv("HYBRID_PROCESS_GATE", "on")
    result, calls = _run(monkeypatch, module_cos=0.44, rule_cos=0.42)
    assert result.accepted == []
    assert calls == []


def test_explore_path_ignores_the_gate_even_when_enabled(monkeypatch):
    """단일 task 재탐색은 seen_fqns 가 한 점수뿐이라 게이트를 태우면 안 된다."""
    monkeypatch.setenv("HYBRID_PROCESS_GATE", "on")
    result, calls = _run(monkeypatch, module_cos=0.44, rule_cos=0.42,
                         skip_process_gate=True)
    assert calls == [1]
    assert len(result.accepted) == 1


# --------------------------------------------------------------------------
# 단계가 어긋나도 범위가 유지되는가 — 조용한 0의 다른 문
#
# Step 1 은 **요약이 붙은** 노드를 고른다. 그게 METHOD 일 수도, CLASS 일 수도
# 있다. 룰의 `source_module` 은 언제나 루틴 id 다. 컨테이너 단계로 고른 날
# 두 집합은 한 번도 겹치지 않는다 — robo-architect `main` 의 Step 1
# (`container_retriever`)이 정확히 그 모양이고, 이 DB 의 그래프에서는 0건이다.
# --------------------------------------------------------------------------
CONTAINER_ROWS = [{"fqn": "c_1", "name": "MonthlyClosingService",
                   "summary": f"{MODULE_MARK} 클래스 요약", "stereotype": None}]


def test_container_level_step1_still_reaches_routine_level_rules(monkeypatch):
    """CLASS 가 뽑혀도 그 안의 METHOD 가 낸 룰은 범위 안이다."""
    result, calls = _run(monkeypatch, module_cos=0.44, rule_cos=0.42,
                         rows=CONTAINER_ROWS, containment={"m_1": "c_1"})
    assert calls == [1], "컨테이너로 뽑힌 날 룰이 전부 범위 밖으로 떨어졌다"
    assert len(result.accepted) == 1


def test_without_containment_the_levels_do_not_meet(monkeypatch):
    """대조 — 이어 주지 않으면 같은 입력이 0이 된다(이 검사가 지키는 대상)."""
    _result, calls = _run(monkeypatch, module_cos=0.44, rule_cos=0.42,
                          rows=CONTAINER_ROWS, containment={})
    assert calls == []


def test_containment_walks_more_than_one_level(monkeypatch):
    """PACKAGE → CLASS → METHOD 처럼 두 단계 떨어져 있어도 닿는다."""
    rows = [{"fqn": "pkg_1", "name": "hr", "summary": f"{MODULE_MARK} 패키지 요약",
             "stereotype": None}]
    _result, calls = _run(monkeypatch, module_cos=0.44, rule_cos=0.42,
                          rows=rows, containment={"m_1": "c_1", "c_1": "pkg_1"})
    assert calls == [1]


def test_ancestors_stop_on_a_cycle():
    """그래프는 신뢰 대상이 아니다 — 순환이 있어도 멈춘다."""
    assert mr.ancestors_of("a", {"a": "b", "b": "a"}) == ["a", "b"]


def test_ancestors_respect_the_limit():
    chain = {str(i): str(i + 1) for i in range(100)}
    assert len(mr.ancestors_of("0", chain, limit=5)) == 5


def test_ancestors_of_unknown_node_is_itself():
    assert mr.ancestors_of("solo", {}) == ["solo"]


# --------------------------------------------------------------------------
# Step 1 을 현재 계약에 맞춤 (2026-09-30)
#
# 애널라이저는 컨테이너 요약을 **의도적으로** 주지 않는다(담당자 확인). 그러니
# 되살리는 것이 아니라 지금 계약에 맞추는 것이 맞고, 계약이 주는 것은 루틴 단위
# 요약뿐이다. 그 상태에서 실측으로 지지된 수정은 둘뿐이었다 —
#   ① 질의에서 domain_keywords 를 뺀다   (정답파일 hit@5  21/28 → 28/28)
#   ② 절대 문턱을 없앤다                 (0.10 은 한 번도 걸리지 않았다)
# --------------------------------------------------------------------------
def test_module_query_drops_domain_keywords():
    """키워드 8개가 task 이름을 눌러 task 단위 검색이 프로세스 단위가 됐다."""
    process = BpmProcess(id="p1", name="월 근태 마감", session_id="s1",
                         domain_keywords=["근태 관리", "월 마감", "급여 연계"])
    task = BpmTaskDTO(id="t1", name="마감 확정", process_id="p1")
    q = mr._build_query(process, task)
    assert "월 근태 마감" in q, "프로세스 이름은 빼면 안 된다 — task 만 쓰면 나빠진다"
    assert "마감 확정" in q
    for kw in process.domain_keywords:
        assert kw not in q, f"domain_keywords 가 다시 들어왔다: {kw}"


def test_module_query_keeps_task_description():
    process = BpmProcess(id="p1", name="월 근태 마감", session_id="s1", domain_keywords=[])
    task = BpmTaskDTO(id="t1", name="마감 확정", description="집계 결과를 확정한다",
                      process_id="p1")
    assert "집계 결과를 확정한다" in mr._build_query(process, task)


def test_module_floor_is_zero_not_lowered():
    """'낮춘 문턱' 은 고치는 척이다 — 값이 아니라 순위가 자른다."""
    assert mr.MIN_MODULE_INCLUSION == 0.0


def test_low_scoring_modules_survive_when_rank_allows(monkeypatch):
    """점수로는 아무것도 버리지 않는다. 옛 0.45 floor 면 1개만 남았다."""
    rows = [
        {"fqn": "m_hi",  "name": "hi",  "summary": f"{MODULE_MARK} 상위", "stereotype": None},
        {"fqn": "m_mid", "name": "mid", "summary": "중간 요약", "stereotype": None},
        {"fqn": "m_lo",  "name": "lo",  "summary": "낮은 요약", "stereotype": None},
    ]
    cache = AngleCache({
        QUERY_MARK: 0.0,
        MODULE_MARK: math.acos(0.90),
        "중간": math.acos(0.20),
        "낮은": math.acos(0.05),
    })
    process = BpmProcess(id="p1", name=QUERY_MARK, session_id="s1", domain_keywords=[])
    task = BpmTaskDTO(id="t1", name="확정", process_id="p1")
    got = asyncio.run(mr.retrieve_top_modules(process, task, top_k=20,
                                              cache=cache, module_rows=rows))
    assert [c.fqn for c in got] == ["m_hi", "m_mid", "m_lo"]


def test_top_k_is_the_real_cut(monkeypatch):
    """자르는 일은 top_k 가 한다 — 그 자리를 옮기면 잡힌다."""
    rows = [{"fqn": f"m{i}", "name": f"m{i}", "summary": f"{MODULE_MARK} {i}",
             "stereotype": None} for i in range(5)]
    cache = AngleCache({QUERY_MARK: 0.0, MODULE_MARK: math.acos(0.5)})
    process = BpmProcess(id="p1", name=QUERY_MARK, session_id="s1", domain_keywords=[])
    task = BpmTaskDTO(id="t1", name="확정", process_id="p1")
    got = asyncio.run(mr.retrieve_top_modules(process, task, top_k=2,
                                              cache=cache, module_rows=rows))
    assert len(got) == 2


# --------------------------------------------------------------------------
# 문턱은 얇게 만들 수 있지만 **비울 수는 없다** (2026-09-30)
#
# 2026-09-29 의 실패는 절대 문턱 자체보다 "0이 되어도 아무도 모른다" 가 본질이었다.
# 문턱이 정답을 통째로 잘라도 `no_candidates` 로만 보였고, 그것은 "코드에 그 업무가
# 없다" 와 구별되지 않았다. 그래서 문턱에서 아무것도 못 살아남으면 순위로 구조한다.
#
# `MIN_BL_INCLUSION` 을 없애는 안(순위만)은 **버렸다** — 실측에서 28개 task 중 25개가
# 정확히 top_k(20)로 평평해져 Step 2 가 판별을 그만둔다. 문턱이 후보 수를 3~18개로
# 흩어 놓는 유일한 장치다.
# --------------------------------------------------------------------------
BELOW = "문턱아래"
ABOVE = "문턱위"


def _rules(n: int, mark: str, start: int = 0):
    rules, ctxs = [], {}
    for k in range(start, start + n):
        rid = f"r{k}"
        rules.append(RuleDTO(id=rid, given="g", when="w", then="t",
                             source_function_id="m_1", source_function="fn", title=f"{mark} {k}"))
        ctxs[rid] = RuleContext(rule_id=rid, given=f"{mark} {k}", when="w", then="t",
                                source_function_id="m_1", source_function="fn")
    return rules, ctxs


def _step2(rules, ctxs, *, above_cos=0.50, below_cos=0.20):
    process = BpmProcess(id="p1", name=QUERY_MARK, session_id="s1", domain_keywords=[])
    task = BpmTaskDTO(id="t1", name="확정", process_id="p1")
    cache = AngleCache({
        QUERY_MARK: 0.0,
        ABOVE: math.acos(above_cos),
        BELOW: math.acos(below_cos),
    })
    stats = ar.Step2Stats()
    got = ar._candidates_for_task(
        task=task, process=process, rules=rules, contexts_by_rule=ctxs,
        module_fqns=["m_1"], top_k=20, cache=cache, actor_name_by_id={},
        stats=stats,
    )
    return got, stats


def test_bl_floor_never_empties_the_list():
    """전부 문턱 아래여도 빈손으로 나가지 않는다 — 그게 조용한 0의 원인이었다."""
    rules, ctxs = _rules(8, BELOW)
    got, stats = _step2(rules, ctxs)
    assert len(got) == ar.BL_FLOOR_RESCUE_N
    assert stats.rescued is True
    assert stats.above_floor == 0


def test_rescue_is_capped():
    """구조는 상한이 있다 — 검증기 부하가 문턱 없는 것과 같아지면 안 된다."""
    rules, ctxs = _rules(20, BELOW)
    got, _ = _step2(rules, ctxs)
    assert len(got) == ar.BL_FLOOR_RESCUE_N


def test_rescue_cannot_invent_candidates():
    """범위에 3개뿐이면 3개다."""
    rules, ctxs = _rules(3, BELOW)
    got, stats = _step2(rules, ctxs)
    assert len(got) == 3
    assert stats.rescued is True


def test_no_rescue_when_the_floor_passes():
    """정상 경로는 건드리지 않는다."""
    rules, ctxs = _rules(8, ABOVE)
    got, stats = _step2(rules, ctxs)
    assert len(got) == 8
    assert stats.rescued is False
    assert stats.above_floor == 8


def test_top_cut_score_is_recorded():
    """문턱이 자른 것 중 최고 점수 — 코퍼스가 옮겨갔는지 보는 신호다."""
    a_rules, a_ctxs = _rules(2, ABOVE, start=0)
    b_rules, b_ctxs = _rules(6, BELOW, start=100)
    got, stats = _step2(a_rules + b_rules, {**a_ctxs, **b_ctxs},
                        above_cos=0.50, below_cos=0.38)
    assert len(got) == 2
    assert stats.above_floor == 2
    assert stats.rescued is False
    assert abs(stats.top_cut_score - 0.38) < 0.005, "잘린 최고 점수가 안 남았다"
    assert abs(stats.top_score - 0.50) < 0.005


def test_empty_scope_is_still_empty():
    """룰이 범위에 하나도 없으면 구조할 것도 없다 — 이건 진짜 0이다."""
    rules, ctxs = _rules(4, BELOW)
    process = BpmProcess(id="p1", name=QUERY_MARK, session_id="s1", domain_keywords=[])
    task = BpmTaskDTO(id="t1", name="확정", process_id="p1")
    stats = ar.Step2Stats()
    got = ar._candidates_for_task(
        task=task, process=process, rules=rules, contexts_by_rule=ctxs,
        module_fqns=["m_other"], top_k=20, cache=AngleCache({QUERY_MARK: 0.0}),
        actor_name_by_id={}, stats=stats,
    )
    assert got == []
    assert stats.in_scope == 0
    assert stats.rescued is False


def test_bl_floor_still_binds():
    """문턱을 없애면 Step 2 가 판별을 그만둔다 — 값이 남아 있어야 한다."""
    assert ar.MIN_BL_INCLUSION == 0.40

