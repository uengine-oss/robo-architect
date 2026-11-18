"""명확화 단위 시험 공통 — 그래프 저장소를 끈다(D-4 ①).

flags · coverage 는 이제 그래프에 영속한다. 단위 시험은 DB 없이 돌아야 하므로
기본으로 메모리만 쓰게 한다. 영속 자체는 test_clarification_persistence.py 가
가짜 저장소로 잰다.
"""

from __future__ import annotations

import pytest

from api.features.requirements.clarification_agent import clarification_coverage as cov
from api.features.requirements.clarification_agent import clarification_flags as flags


@pytest.fixture(autouse=True)
def _no_graph_persistence(monkeypatch):
    monkeypatch.setattr(flags, "_GRAPH", None)
    monkeypatch.setattr(cov, "_GRAPH", None)
    yield
