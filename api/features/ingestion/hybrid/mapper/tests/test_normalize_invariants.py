"""§036 불변식 가드 — 정규화가 floor/후보예산을 바꾸지 않고, env로 완전 비활성 가능.

사용자 인지부하 최소화 제약의 코드 레벨 보증:
- retrieval floor(MIN_BL_INCLUSION)·후보예산(bl_top_k/per_task_cap) 기본값 불변.
- HYBRID_GLOSSARY_NORMALIZE=0 이면 정규화 비활성(기존 경로와 동일).
순수 검사 — neo4j/LLM 불필요.
"""

from __future__ import annotations

import inspect

from api.features.ingestion.hybrid.mapper import agentic_retriever as ar


def test_floor_constants_unchanged():
    # 036은 floor를 낮추지 않는다(= 통과 기준 유지). 값이 바뀌면 인지부하/비용 제약 위반.
    assert ar.MIN_BL_INCLUSION == 0.45
    assert ar.REJECT_NEAR_MISS_FLOOR == 0.45
    assert ar.REJECT_VISIBLE_CAP == 3


def test_candidate_budget_defaults_unchanged():
    sig = inspect.signature(ar.run_agentic_retrieval)
    assert sig.parameters["bl_top_k"].default == 20
    assert sig.parameters["per_task_cap"].default == 20


def test_glossary_param_is_backward_compatible():
    # 신규 glossary 파라미터는 기본 None → 기존 호출자/테스트 무변경 동작.
    sig = inspect.signature(ar.run_agentic_retrieval)
    assert "glossary" in sig.parameters
    assert sig.parameters["glossary"].default is None


def test_env_toggle_disables_normalization(monkeypatch):
    monkeypatch.setenv("HYBRID_GLOSSARY_NORMALIZE", "0")
    assert ar._glossary_normalize_enabled() is False
    monkeypatch.setenv("HYBRID_GLOSSARY_NORMALIZE", "1")
    assert ar._glossary_normalize_enabled() is True
    monkeypatch.delenv("HYBRID_GLOSSARY_NORMALIZE", raising=False)
    assert ar._glossary_normalize_enabled() is True  # 기본 on
