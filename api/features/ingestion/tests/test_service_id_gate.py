# -*- coding: utf-8 -*-
"""적재 입구의 서비스 ID — **소유자만, 겹치면 거절, 안 주면 그냥 돈다**.

## 왜 이 검사가 있나

적재 입구가 셋(표준 업로드·Figma·하이브리드)이다. 판단을 세 군데에 베껴 두면 한
곳만 고치는 날이 오고, 그날 **한 입구만 소유자 검사를 안 한다** — 오류는 안 난다.
그래서 판단은 `service_id_gate.resolve()` 하나이고, 이 검사는 그 하나를 잰다.

```
모양     틀리면 400 — 뒤에 올 PDF 추출(수십 초) 전에 멈춘다
소유자   편집자가 ID 를 붙이면 403. **조용히 버리지 않는다**
유일     지난 적재까지 본다 → 409
선택     안 주면 `None` — 지금처럼 난수 id 로 돈다
```
"""

from __future__ import annotations

import pytest
from fastapi import HTTPException

from api.features.ingestion import service_id_gate as gate


@pytest.fixture
def 소유자(monkeypatch: pytest.MonkeyPatch):
    """프로젝트 `prj_a` 의 소유자 `u1` 이 요청한 상태를 만든다."""
    monkeypatch.setattr(gate, "request_graph", lambda request: "prj_a")
    monkeypatch.setattr(gate, "request_uid", lambda request: "u1")
    monkeypatch.setattr(gate.projects_store, "get_project", lambda g: {
        "graph": g, "displayName": "인사관리", "ownerUid": "u1",
    })
    monkeypatch.setattr(gate.runs, "session_id_taken", lambda sid: False)


def test_소유자가_준_값은_세션_id_가_된다(소유자):
    assert gate.resolve(object(), "ROBO-2026-001") == "ROBO-2026-001"


def test_안_주면_아무것도_확인하지_않는다(monkeypatch: pytest.MonkeyPatch):
    """ID 없이도 적재는 돌아야 한다 — 체계를 못 받은 사람과 편집자가 있다.

    프로젝트 조회조차 하지 않는다는 것이 "확인할 게 없다" 의 증거다.
    """
    def _터진다(*a, **k):
        raise AssertionError("안 준 값에 확인이 돌았다")

    monkeypatch.setattr(gate, "request_graph", _터진다)
    monkeypatch.setattr(gate.projects_store, "get_project", _터진다)
    assert gate.resolve(object(), None) is None
    assert gate.resolve(object(), "   ") is None


def test_모양이_틀리면_400_이고_도움말이_붙는다(소유자):
    with pytest.raises(HTTPException) as caught:
        gate.resolve(object(), "ROBO 2026")
    assert caught.value.status_code == 400
    assert "ROBO-2026-001" in caught.value.detail   # 예시를 보여 준다


def test_편집자는_서비스_ID_를_못_정한다(소유자, monkeypatch: pytest.MonkeyPatch):
    """사용자 지시: "프로젝트의 소유자만".

    편집자는 적재 자체는 할 수 있다(`require_write` 가 통과시킨다). 막는 것은
    **ID 를 붙이는 일**뿐이다.
    """
    monkeypatch.setattr(gate, "request_uid", lambda request: "u2")
    with pytest.raises(HTTPException) as caught:
        gate.resolve(object(), "ROBO-1")
    assert caught.value.status_code == 403


def test_소유자를_확인할_수_없으면_통과시키지_않는다(소유자, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(gate.projects_store, "get_project", lambda g: None)
    with pytest.raises(HTTPException) as caught:
        gate.resolve(object(), "ROBO-1")
    assert caught.value.status_code == 403


def test_지난_적재가_쓴_값은_409(소유자, monkeypatch: pytest.MonkeyPatch):
    """앱을 다시 띄워도 걸려야 한다 — 그래서 메모리가 아니라 run 기록을 본다."""
    monkeypatch.setattr(gate.runs, "session_id_taken", lambda sid: sid == "ROBO-1")
    with pytest.raises(HTTPException) as caught:
        gate.resolve(object(), "ROBO-1")
    assert caught.value.status_code == 409
    assert "ROBO-1" in caught.value.detail
