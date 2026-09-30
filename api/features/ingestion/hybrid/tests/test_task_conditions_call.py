# -*- coding: utf-8 -*-
"""**조건 생성 호출이 서명과 맞는가** — 5개월 묻혀 있던 결함 (2026-09-30).

## 무슨 일이 있었나

`extract_conditions_for_task` 의 서명은 `(task_name, task_description, passages,
rules)` 인데, `explore_service._refresh_task_conditions` 는 2026-05-06(`8226f55`)
부터 `task` DTO 를 한 덩어리로 넘겨 **인자가 셋**이었다.

    TypeError: extract_conditions_for_task() missing 1 required positional
               argument: 'rules'

바깥 `except Exception` 이 그걸 WARN 한 줄로 삼켰다 —

    [WARN] Per-task conditions refresh failed (continuing): …

그래서 탐색은 늘 "성공" 했고, `BpmTask.conditions` 는 **0/28** 이었다. 5개월 동안
조건이 하나도 생기지 않았고 아무도 몰랐다.

## 여기서 재는 것

  ① 호출 인자가 **진짜 서명에 바인딩되는가** — `inspect.signature().bind()` 로 잰다.
     개수를 세는 검사는 순서가 바뀌면 통과한다.
  ② 첫 인자가 **이름(str)** 인가 — DTO 를 넘기면 개수가 맞아도 프롬프트가 어긋난다.
  ③ 서명 불일치는 **WARN 으로 묻지 않는다** — ERROR 로 올리고 "코드 결함" 이라 적는다.

③이 없으면 같은 결함이 다시 5개월 숨는다. ①만으로는 다음 사람이 서명을 바꿀 때
경보가 울리지 않는다 — 울리는 자리는 로그다.
"""

from __future__ import annotations

import asyncio
import inspect

import pytest

from api.features.ingestion.hybrid import contracts, explore_service
from api.features.ingestion.hybrid.mapper import condition_extractor

SID = "sess_cond"
TASK = "t_1"


def _task() -> contracts.BpmTaskDTO:
    return contracts.BpmTaskDTO(id=TASK, name="마감 대상 확인", description="마감할 사원을 고른다")


def _rule() -> contracts.RuleDTO:
    return contracts.RuleDTO(id="rule_1", given="g", when="w", then="t")


@pytest.fixture
def recorded(monkeypatch: pytest.MonkeyPatch) -> dict:
    """조건 추출기를 기록기로 갈아 끼우고, 스냅샷·저장은 가짜로 둔다."""
    box: dict = {}

    async def recorder(*args, **kwargs):
        box["args"] = args
        box["kwargs"] = kwargs
        return ["잔여가 0이면 반려한다"]

    monkeypatch.setattr(explore_service, "extract_conditions_for_task", recorder)
    monkeypatch.setattr(explore_service, "fetch_session_snapshot", lambda sid: {
        "tasks": [{
            "id": TASK,
            "document_passages": [
                {"id": "p1", "session_id": SID, "text": "마감 대상은 재직자다", "page": 1},
            ],
        }],
    })
    monkeypatch.setattr(explore_service, "save_task_conditions",
                        lambda sid, m: box.setdefault("saved", m))
    return box


def _run(box: dict) -> None:
    asyncio.run(explore_service._refresh_task_conditions(
        SID, _task(),
        [contracts.ActivityRuleMapping(task_id=TASK, rule_id="rule_1", score=0.6,
                                       method="agentic", reviewed=True)],
        [_rule()],
    ))


def test_호출이_진짜_서명에_바인딩된다(recorded):
    _run(recorded)
    assert "args" in recorded, "조건 추출기를 아예 부르지 않았다"
    sig = inspect.signature(condition_extractor.extract_conditions_for_task)
    # 여기서 TypeError 가 나면 실제 실행에서도 난다 — 그게 5개월 묻혔던 바로 그 예외다.
    sig.bind(*recorded["args"], **recorded["kwargs"])


def test_첫_인자는_task_이름이다(recorded):
    """개수가 맞아도 DTO 를 넘기면 프롬프트가 어긋난다 — 조용히 나쁜 조건이 나온다."""
    _run(recorded)
    first = recorded["args"][0]
    assert isinstance(first, str), f"첫 인자가 이름이 아니다: {type(first).__name__}"
    assert first == "마감 대상 확인"
    assert recorded["args"][1] == "마감할 사원을 고른다"


def test_결과를_저장한다(recorded):
    _run(recorded)
    assert recorded.get("saved") == {TASK: ["잔여가 0이면 반려한다"]}


def test_서명_불일치는_ERROR_로_남는다(monkeypatch: pytest.MonkeyPatch):
    """WARN 으로 묻으면 LLM 실패·문서 없음과 섞여 또 5개월 숨는다."""
    src = inspect.getsource(explore_service.explore_task)
    assert "except TypeError as e:" in src, (
        "서명 불일치를 일반 예외와 같이 삼킨다 — 같은 결함이 다시 묻힌다"
    )
    head = src[src.index("except TypeError as e:"):]
    head = head[: head.index("except Exception")]
    assert '"ERROR"' in head, "서명 불일치를 WARN 으로 적는다"
    assert "코드 결함" in head, "사람이 읽고 코드 결함임을 알 수 있어야 한다"
