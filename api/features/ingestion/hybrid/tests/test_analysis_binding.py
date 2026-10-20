# -*- coding: utf-8 -*-
"""BPM 탐색/ES 승격은 자신을 만든 프로젝트 분석과 일치해야 한다."""

from contextlib import contextmanager
from pathlib import Path

import pytest

from api.features.ingestion.hybrid import analysis_binding


class _Analyzer:
    def __init__(self, rows):
        self.rows = rows

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return None

    def run(self, query, **params):
        return self.rows


class _Design:
    def __init__(self, record=None):
        self.record = record
        self.calls = []

    def run(self, query, **params):
        self.calls.append((query, params))
        return _Result(self.record)


class _Result:
    def __init__(self, record):
        self.record = record

    def single(self):
        return self.record


def _analyzer_rows(summary="요약"):
    return [{
        "kind": "node", "item_key": "fn-1", "item_labels": ["FUNCTION"],
        "item_values": ["applyLeave", summary],
    }]


def _wire(monkeypatch, design_record):
    design = _Design(design_record)

    @contextmanager
    def design_session():
        yield design

    monkeypatch.setattr(analysis_binding, "get_session", design_session)
    monkeypatch.setattr(analysis_binding, "design_database", lambda: "prj_a")
    monkeypatch.setattr(analysis_binding, "analyzer_database", lambda: "prj_a_a")
    monkeypatch.setattr(
        analysis_binding, "analyzer_session", lambda: _Analyzer(_analyzer_rows()),
    )
    return design


def test_binding_records_design_analyzer_and_content_fingerprint(monkeypatch):
    design = _wire(monkeypatch, {"id": "s1"})

    out = analysis_binding.bind_session_to_current_analysis("s1")

    assert out["design_graph"] == "prj_a"
    assert out["analyzer_graph"] == "prj_a_a"
    assert len(out["fingerprint"]) == 64
    params = design.calls[0][1]
    assert params["design"] == "prj_a" and params["analyzer"] == "prj_a_a"


def test_guard_rejects_another_projects_analysis(monkeypatch):
    _wire(monkeypatch, {
        "design_graph": "prj_a", "analyzer_graph": "prj_b_a",
        "analysis_fingerprint": "old",
    })

    with pytest.raises(analysis_binding.AnalysisBindingError) as caught:
        analysis_binding.assert_session_analysis_binding("s1")

    assert caught.value.code == "ANALYSIS_PROJECT_MISMATCH"


def test_guard_rejects_reanalysis_before_process_and_es_regeneration(monkeypatch):
    _wire(monkeypatch, {
        "design_graph": "prj_a", "analyzer_graph": "prj_a_a",
        "analysis_fingerprint": "fingerprint-before-reanalysis",
    })

    with pytest.raises(analysis_binding.AnalysisBindingError) as caught:
        analysis_binding.assert_session_analysis_binding("s1")

    assert caught.value.code == "ANALYSIS_CONTENT_CHANGED"


def test_guard_accepts_same_project_same_analysis(monkeypatch):
    _wire(monkeypatch, {"unused": True})
    fingerprint = analysis_binding.current_analysis_fingerprint()
    _wire(monkeypatch, {
        "design_graph": "prj_a", "analyzer_graph": "prj_a_a",
        "analysis_fingerprint": fingerprint,
    })

    out = analysis_binding.assert_session_analysis_binding("s1")

    assert out["fingerprint"] == fingerprint


def test_promotion_checks_binding_before_deleting_previous_es():
    source = Path("api/features/ingestion/hybrid/router.py").read_text(encoding="utf-8")
    function = source[source.index("async def promote_start"):source.index("async def reset_promotion")]
    assert function.index("assert_session_analysis_binding") < function.index("clear_promoted_nodes")
