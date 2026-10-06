# -*- coding: utf-8 -*-
"""DB 가 돌려준 id 를 못 심으면 **말한다** (2026-10-06).

## 무엇이 조용했나

승격은 LLM 이 지어낸 임시 id 를 DB 가 돌려준 UUID 로 덮어쓴다. 그 자리가 다섯 군데
모두 이렇게 적혀 있었다 —

```python
try:
    cmd.id = created_cmd.get("id")
except Exception:
    pass
```

실패해도 코드는 계속 가고, 다음 단계는 **DB 에 없는 id 로 관계를 건다.** 링크는
조용히 안 붙고, 나중에 "이 요소는 왜 출처가 없나" 만 남는다 — 이 저장소가 여러 번
만난 모양이다.

## 여기서 재는 것

```
① 심는다          객체든 dict 든
② 없는 값은 안 덮는다  `None` 으로 덮으면 **있던 id 가 사라진다**
③ 못 심으면 말한다   그리고 **막지는 않는다**(한 요소가 승격 전체를 세우지 않는다)
```
"""

from __future__ import annotations

import pytest

from api.features.ingestion import db_identity
from api.features.ingestion.db_identity import adopt_db_identity


class _Model:
    def __init__(self):
        self.id = "llm-temp-1"
        self.key = "llm-key-1"


class _Frozen:
    """속성을 못 바꾸는 모델. pydantic frozen 이 이렇게 군다."""

    __slots__ = ()

    def __setattr__(self, *_a):
        raise AttributeError("frozen")


@pytest.fixture
def logged(monkeypatch: pytest.MonkeyPatch) -> list[tuple]:
    rows: list[tuple] = []
    monkeypatch.setattr(
        db_identity.SmartLogger, "log",
        lambda level, msg, category=None, params=None: rows.append((level, category, params)),
    )
    return rows


# ── ① 심는다 ──────────────────────────────────────────────────────────────

def test_객체에_심는다(logged):
    m = _Model()
    assert adopt_db_identity(m, {"id": "uuid-1", "key": "k-1"}, kind="Command", name="X")
    assert (m.id, m.key) == ("uuid-1", "k-1")
    assert logged == []


def test_dict_에도_심는다(logged):
    d = {"id": "llm-temp", "name": "X"}
    assert adopt_db_identity(d, {"id": "uuid-1", "key": "k-1"}, kind="Event", name="X")
    assert d["id"] == "uuid-1" and d["key"] == "k-1"


def test_필드를_고를_수_있다(logged):
    m = _Model()
    adopt_db_identity(m, {"id": "uuid-1", "key": "k-1"}, kind="BoundedContext",
                      name="X", fields=("id",))
    assert m.id == "uuid-1" and m.key == "llm-key-1"


# ── ② 없는 값은 안 덮는다 ─────────────────────────────────────────────────

def test_None_으로_덮지_않는다(logged):
    """`None` 으로 덮으면 **있던 id 가 사라진다** — 없는 것보다 나쁘다."""
    m = _Model()
    adopt_db_identity(m, {"id": None, "key": "k-1"}, kind="Command", name="X")
    assert m.id == "llm-temp-1" and m.key == "k-1"


def test_응답에_심을_것이_없으면_말한다(logged):
    m = _Model()
    assert adopt_db_identity(m, {"name": "X"}, kind="Command", name="X") is False
    assert logged and logged[-1][1] == "ingestion.identity.empty"


def test_응답이_없으면_말한다(logged):
    assert adopt_db_identity(_Model(), None, kind="Aggregate", name="X") is False
    assert logged[-1][1] == "ingestion.identity.missing"


# ── ③ 못 심으면 말한다. 그리고 막지 않는다 ────────────────────────────────

def test_못_심으면_WARN_을_남기고_계속_간다(logged):
    ok = adopt_db_identity(_Frozen(), {"id": "uuid-1"}, kind="Policy", name="연차 부여")
    assert ok is False                      # 예외가 밖으로 안 나간다
    level, category, params = logged[-1]
    assert level == "WARN" and category == "ingestion.identity.failed"
    assert params["kind"] == "Policy" and params["name"] == "연차 부여"
    # 어느 요소인지 · 무엇까지 심었는지가 남아야 나중에 답이 된다.
    assert "wrote" in params and "error" in params
