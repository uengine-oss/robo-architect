# -*- coding: utf-8 -*-
"""재적재는 **묻고 나서** 지운다 — 쓰는 자리에서 본다.

## 왜 서버에도 두나

화면은 이미 묻는다 — `RequirementsIngestionModal.handleStartClick` 이
`/api/ingest/replacement-preview` 를 읽고, 지울 것이 있으면 확인 대화상자를 띄운다.
그런데 **그 문을 지나지 않는 길이 있었다**: 업로드 엔드포인트를 직접 부르면
아무것도 묻지 않고 **지우기부터 시작한다.**

그 지우기는 `MATCH (n:Label) DETACH DELETE n` 이다 — WHERE 절이 없고, "그 프로젝트
만" 이 되는 이유는 **연결이 그 graph 에 묶여 있기 때문**이다. 공유받은 사람이
재적재하면 **소유자의 BPM·ES 가 그대로 사라진다.** 되돌릴 길은 지우기 직전의
스냅샷뿐이다.

## 여기서 재는 것

```
① 지울 것이 있는데 확인이 없으면   409 + **무엇이 지워지는지**
② 확인이 있으면                  통과하고, 그 미리보기를 돌려준다(로그에 남길 근거)
③ 첫 적재(지울 것 0)            **묻지 않는다** — 확인만 늘리면 사람은 읽지 않는다
④ 세다가 실패하면                막지 않는다 — 못 센 것은 "있다" 의 근거가 아니다
```

④가 중요하다. 여기서 막으면 **멀쩡한 첫 적재까지** 못 하게 된다.
"""

from __future__ import annotations

import pytest
from fastapi import HTTPException

from api.features.ingestion import replacement


def _preview(monkeypatch: pytest.MonkeyPatch, value):
    def fake():
        if isinstance(value, Exception):
            raise value
        return value

    monkeypatch.setattr(replacement, "preview", fake)


def test_지울_것이_있는데_확인이_없으면_409(monkeypatch: pytest.MonkeyPatch):
    _preview(monkeypatch, {
        "graph": "prj_x", "total": 732, "sessions": ["0eb8e37f"],
        "counts": {"BpmTask": 29, "Command": 17}, "preserved": ["FigmaBinding"],
    })
    with pytest.raises(HTTPException) as e:
        replacement.require_replace_ack(False)
    assert e.value.status_code == 409
    detail = e.value.detail
    assert detail["code"] == "INGEST_REPLACE_CONFIRM"
    # **무엇이 지워지는지** 가 응답에 있어야 화면이 그것을 보여줄 수 있다.
    assert detail["total"] == 732
    assert detail["counts"]["BpmTask"] == 29
    assert detail["sessions"] == ["0eb8e37f"]
    assert "732" in detail["message"]


def test_확인이_있으면_통과하고_미리보기를_돌려준다(monkeypatch: pytest.MonkeyPatch):
    data = {"graph": "prj_x", "total": 10, "counts": {"UI": 10}, "sessions": [],
            "preserved": []}
    _preview(monkeypatch, data)
    got = replacement.require_replace_ack(True)
    assert got is not None and got["total"] == 10


def test_첫_적재는_묻지_않는다(monkeypatch: pytest.MonkeyPatch):
    _preview(monkeypatch, {"graph": "prj_x", "total": 0, "counts": {}, "sessions": [],
                           "preserved": []})
    assert replacement.require_replace_ack(False) is None


def test_세다가_실패해도_막지_않는다(monkeypatch: pytest.MonkeyPatch):
    """못 센 것은 "지울 것이 있다" 의 근거가 아니다 — 여기서 막으면 첫 적재도 못 한다."""
    _preview(monkeypatch, RuntimeError("bolt closed"))
    assert replacement.require_replace_ack(False) is None


def test_지우는_입구_셋이_모두_확인을_본다():
    """엔드포인트가 늘어나면 **그 길만 조용히 안 묻는다.** 입구를 세어 못박는다."""
    import inspect

    from api.features.ingestion import router as std
    from api.features.ingestion.hybrid import router as hyb

    wipes = [std.upload_document, std.upload_figma_document, hyb.upload_hybrid]
    for fn in wipes:
        src = inspect.getsource(fn)
        assert "require_replace_ack" in src, f"{fn.__name__} 가 교체 확인을 안 본다"
        assert "replaceAck" in src, f"{fn.__name__} 에 확인 플래그가 없다"


def test_지우지_않는_길에는_묻지_않는다():
    """`/user-stories/design` 은 증분이다 — `incremental_design_runner` 가 그래프를
    **지우지 않고** 기존 BC·Aggregate 를 MERGE 로 재사용한다.

    처음에 이 길에도 확인을 달았다가 **뺐다.** 지우지 않는 일에 확인을 물으면
    확인이 싸구려가 된다 — 사람이 읽지 않고 누르게 되고, 그러면 **정말 지우는
    자리의 확인도 같이 무력해진다.**
    """
    import inspect

    from api.features.ingestion import router as std
    from api.features.ingestion.workflow import incremental_design_runner as inc

    assert "require_replace_ack" not in inspect.getsource(std.design_for_user_stories)
    # 그 주장의 근거: 증분 러너에 지우기가 없다.
    runner_src = inspect.getsource(inc)
    assert "clear_event_storming_nodes" not in runner_src
    assert "clear_all_hybrid_workspace" not in runner_src
    assert "DETACH DELETE" not in runner_src
