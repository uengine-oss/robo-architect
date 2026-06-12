"""Contract tests for ReadModel UI classification helpers (spec 042 — US3).

Pure-logic + LLM-fallback tests; no live Neo4j/LLM (llm_invoke stubbed).
Command UI는 기존 "사람-조작 command마다" 동작을 유지하므로 여기서 다루지 않는다.
"""

from __future__ import annotations

import asyncio

from api.features.ingestion.workflow.phases import task_ui_helpers as H


# ----- 3-way classification --------------------------------------------------
def _stub(kind):
    async def _inner(system, user):
        return f'{{"kind": "{kind}", "rationale": "x"}}'
    return _inner


def test_classify_screen_result_view():
    # 결과 화면 → screen (자체 UI)
    v = asyncio.run(H.classify_readmodel({"name": "본인확인결과"}, llm_invoke=_stub("screen")))
    assert v.kind == "screen"


def test_classify_inline():
    v = asyncio.run(H.classify_readmodel({"name": "잔액배지"}, llm_invoke=_stub("inline")))
    assert v.kind == "inline"


def test_classify_system():
    v = asyncio.run(H.classify_readmodel({"name": "내부집계"}, llm_invoke=_stub("system")))
    assert v.kind == "system"


def test_classify_invalid_kind_defaults_screen():
    v = asyncio.run(H.classify_readmodel({"name": "x"}, llm_invoke=_stub("garbage")))
    assert v.kind == "screen"  # 보수적: 사용자가 보는 결과 화면 누락 방지


def test_classify_error_defaults_screen():
    async def boom(system, user):
        raise RuntimeError("llm down")
    v = asyncio.run(H.classify_readmodel({"name": "x"}, llm_invoke=boom))
    assert v.kind == "screen"


# ----- display attach --------------------------------------------------------
def test_attach_readmodel_display_cypher():
    captured = {}

    class _Sess:
        def run(self, query, **params):
            captured["query"] = query
            captured["params"] = params

    H.attach_readmodel_display(_Sess(), "ui1", "rm1")
    q = captured["query"]
    assert "MERGE (u)-[r:ATTACHED_TO]->(rm)" in q
    assert "r.role = 'display'" in q
    assert captured["params"] == {"uid": "ui1", "rid": "rm1"}


def test_attach_display_readmodels_uses_producing_task_ui():
    runs = []

    class _Res:
        def __init__(self, rows): self._rows = rows
        def single(self): return self._rows[0] if self._rows else None

    class _Sess:
        def run(self, query, **params):
            runs.append((query, params))
            if "RETURN u.id AS uid" in query:
                return _Res([{"uid": "ui_host"}] if params.get("rid") == "rm1" else [])
            return _Res([])

    n = H.attach_display_readmodels(_Sess(), "sid", ["rm1", "rm2"])
    assert n == 1  # rm1만 소비 화면 발견
    assert any("r.role = 'display'" in q and p.get("rid") == "rm1" for q, p in runs)
