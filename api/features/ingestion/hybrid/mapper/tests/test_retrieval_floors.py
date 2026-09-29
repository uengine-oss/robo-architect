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
                   source_module="m_1", source_function="confirmClosing",
                   title=RULE_MARK)
    ctx = RuleContext(rule_id="rule_1", given=RULE_MARK, when="w", then="t",
                      source_module="m_1", source_function="confirmClosing")
    rows = [{"fqn": "m_1", "name": "confirmClosing",
             "summary": f"{MODULE_MARK} 의 마감 확정 메서드", "stereotype": None}]
    return process, task, rule, ctx, rows


def _run(monkeypatch, module_cos: float, rule_cos: float, **kwargs):
    process, task, rule, ctx, rows = _fixture()
    monkeypatch.setattr(ar, "fetch_all_modules", lambda: rows)
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
