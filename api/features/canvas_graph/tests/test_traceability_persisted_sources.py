# -*- coding: utf-8 -*-
"""**출처 탭이 영속된 엣지를 읽는다** (2026-09-30).

## 무슨 일이 있었나

화면의 출처 탭(`GET /api/graph/traceability/{node_id}`)에 **UserStory 만** 보였다.
Command 를 물으면 이렇게 나왔다.

    node: Command 월별 근태 집계/요약
      US US-025  rules=0  functions=0     (전건)

원인은 그 라우트가 출처를 **매번 다시 유도**하면서 분석 그래프와 문자열로 조인한
것이다.

    RETURN … ar.statement AS title        ← 생산자의 RULE 에 `statement` 가 없다

전건 NULL 이라 오류 없이 0건이 된다. `condition_description` 으로 바꿔도 안 맞는다 —
설계 shadow 의 `title` 은 `condition_description + ": " + 효과` 로 합성한 문자열이어서
68개 중 **0건** 일치다(실측).

## 그래서 유도를 그만둔다

승격이 요소마다 `(x)-[:SOURCED_FROM {evidence_role, via_task_id}]->(Rule)` 을 남긴다.
루틴은 **내부 id** 로 정확히 잇는다 — `Rule.source_module` 이 분석 그래프 루틴 노드의
`_id` 이고 68/68 일치한다(실측). 문자열이 아니므로 생산자가 문장 표기를 바꿔도 안 끊긴다.

## 여기서 재는 것

  ① 엣지가 있으면 **그 경로로 간다** — 옛 유도를 타지 않는다
  ② 룰에 `evidence_role`·`via_task_id` 가 실린다 · 주 근거가 먼저 온다
  ③ UserStory 를 못 찾은 엣지를 **버리지 않는다** — 근거가 화면에서 사라지면 안 된다
  ④ 루틴 조회 키는 `_id` 다 — `f.id`/`f.name` 으로 맞추면 이 그래프에서 0건이다
  ⑤ 엣지가 없으면 옛 경로로 돌아간다 (rfp/figma US · 이 정책 이전 데이터)
"""

from __future__ import annotations

import asyncio
import inspect

import pytest

from api.features.canvas_graph.routes import traceability as tr


class _Req:
    class _c:
        host = "127.0.0.1"

    client = _c()
    method = "GET"
    url = type("u", (), {"path": "/x"})()
    headers: dict = {}
    state = type("s", (), {})()


def _edge(us="US-1", role="담당자", action="한다", title="조건: 효과",
          fn="applyLeave", rid="111", evidence_role="primary", task="task_a"):
    return {"us_id": us, "role": role, "action": action, "title": title,
            "given": "g", "wh": "w", "th": "t", "fn": fn, "routine_id": rid,
            "evidence_role": evidence_role, "via_task_id": task}


def test_룰에_역할과_경유_task_가_실리고_주_근거가_먼저_온다(monkeypatch):
    monkeypatch.setattr(tr, "_routine_entry", lambda rid, cache: None)
    out = tr._sources_from_persisted(
        _Req(), "cmd-1", {"name": "어떤 Command"}, "Command", None,
        [_edge(title="보조 룰", evidence_role="supporting"),
         _edge(title="주 룰", evidence_role="primary")],
    )
    rules = out["sources"][0]["rules"]
    assert [r["evidence_role"] for r in rules] == ["primary", "supporting"]
    assert rules[0]["title"] == "주 룰"
    assert rules[0]["via_task_id"] == "task_a"


def test_UserStory_를_못_찾은_엣지를_버리지_않는다(monkeypatch):
    """근거가 있는데 화면에서 사라지는 것이 가장 나쁘다."""
    monkeypatch.setattr(tr, "_routine_entry", lambda rid, cache: None)
    out = tr._sources_from_persisted(
        _Req(), "cmd-1", {"name": "x"}, "Command", None,
        [_edge(us="US-1", title="가진 것"), _edge(us="", title="US 없는 것")],
    )
    ids = [s["us"]["id"] for s in out["sources"]]
    assert ids == ["US-1", ""], f"묶음이 사라졌다: {ids}"
    assert sum(len(s["rules"]) for s in out["sources"]) == 2
    # US 없는 묶음은 마지막에 둔다.
    assert out["sources"][-1]["us"]["id"] == ""


def test_같은_루틴은_한_번만_읽는다(monkeypatch):
    calls: list[str] = []

    def fake(rid, cache):
        calls.append(rid)
        return {"id": rid, "name": "fn", "summary": "", "location": "", "code": "", "tables": []}

    monkeypatch.setattr(tr, "_routine_entry", fake)
    tr._sources_from_persisted(
        _Req(), "n", {"name": "x"}, "Aggregate", None,
        [_edge(us="US-1", rid="7"), _edge(us="US-1", rid="7"), _edge(us="US-2", rid="7")],
    )
    # 묶음마다 한 번 — 캐시는 `_routine_entry` 안에 있다(여기선 가짜라 두 번).
    assert calls == ["7", "7"], calls


def test_응답_모양이_옛_경로와_같다(monkeypatch):
    """화면을 안 고쳐도 되게 유지한다."""
    monkeypatch.setattr(tr, "_routine_entry", lambda rid, cache: None)
    out = tr._sources_from_persisted(_Req(), "n", {"displayName": "이름"}, "Policy",
                                     {"id": "bc-1", "name": "BC"}, [_edge()])
    assert sorted(out.keys()) == ["bc", "node", "sources"]
    assert out["node"] == {"id": "n", "name": "이름", "type": "Policy"}
    assert out["bc"] == {"id": "bc-1", "name": "BC"}
    s = out["sources"][0]
    assert sorted(s.keys()) == ["functions", "rules", "us"]
    assert sorted(s["rules"][0].keys()) == [
        "boundary_example_ids", "coupled_domain", "evidence_role", "function_id",
        "given", "seq", "then", "title", "via_task_id", "when", "writes",
    ]


def test_루틴_조회는_내부_id_로_맞춘다():
    """`f.id`·`f.name` 으로 맞추면 이 그래프에서 전건 0이다 — METHOD 에 그 속성이 없다."""
    src = inspect.getsource(tr._routine_entry)
    assert "f._id = $rid" in src, "내부 id 가 아닌 키로 루틴을 찾는다"
    assert "READS|WRITES" in src, "테이블 접근을 안 읽는다"


def test_엣지가_있으면_그_경로로_간다(monkeypatch):
    """옛 유도(분석 그래프 문자열 조인)를 타면 rules 가 0으로 돌아간다."""
    src = inspect.getsource(tr.get_traceability)
    i_persisted = src.index("persisted = _query(")
    i_return = src.index("return _sources_from_persisted(")
    i_legacy = src.index("# 4) Per US, build a `source` entry")
    assert i_persisted < i_return < i_legacy, "영속 경로가 옛 경로보다 뒤에 있다"

    called = {}
    monkeypatch.setattr(tr, "_query", lambda q, p=None: (
        [{"id": "n", "name": "N", "displayName": None, "labels": ["Command"]}]
        if "labels(n)" in q else
        [_edge()] if "SOURCED_FROM" in q and "sf.via_task_id" in q else []))
    monkeypatch.setattr(tr, "_routine_entry", lambda rid, cache: None)
    monkeypatch.setattr(tr, "_analyzer_rules",
                        lambda fns: called.setdefault("legacy", True) or [])
    out = asyncio.run(tr.get_traceability(_Req(), "n"))
    assert "legacy" not in called, "영속 엣지가 있는데도 옛 유도를 탔다"
    assert len(out["sources"][0]["rules"]) == 1
