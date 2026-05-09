from __future__ import annotations

from api.features.ingestion.hybrid import pipeline_verification


def test_verify_pipeline_status_ready(monkeypatch):
    class _Rec(dict):
        pass

    class _Result:
        def __init__(self, rec):
            self._rec = rec

        def single(self):
            return self._rec

    class _Session:
        def __init__(self):
            self.idx = 0
            self.rows = [
                _Rec({"processes": 1, "tasks": 3, "actors": 2}),
                _Rec({"total_tasks": 3, "mapped_tasks": 2, "zero_rule_tasks": 1}),
                _Rec(
                    {
                        "user_stories": 3,
                        "bounded_contexts": 1,
                        "aggregates": 1,
                        "commands": 2,
                        "events": 2,
                        "policies": 1,
                        "readmodels": 1,
                    }
                ),
                _Rec({"promoted_to": 3, "sourced_from": 2, "implements_bc": 3}),
                _Rec({"total_questions": 4, "attached_questions": 4}),
            ]

        def run(self, query, **params):
            rec = self.rows[self.idx]
            self.idx += 1
            return _Result(rec)

    class _Ctx:
        def __init__(self, s):
            self.s = s

        def __enter__(self):
            return self.s

        def __exit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr(pipeline_verification, "get_session", lambda: _Ctx(_Session()))
    out = pipeline_verification.verify_pipeline_status("sid-1")
    assert out["summary"]["pipeline_ready"] is True
    assert out["counts"]["mapping"]["mapped_tasks"] == 2
    assert out["counts"]["traceability_edges"]["promoted_to"] == 3


def test_verify_pipeline_status_not_ready(monkeypatch):
    class _Rec(dict):
        pass

    class _Result:
        def __init__(self, rec):
            self._rec = rec

        def single(self):
            return self._rec

    class _Session:
        def __init__(self):
            self.idx = 0
            self.rows = [
                _Rec({"processes": 0, "tasks": 0, "actors": 0}),
                _Rec({"total_tasks": 0, "mapped_tasks": 0, "zero_rule_tasks": 0}),
                _Rec(
                    {
                        "user_stories": 0,
                        "bounded_contexts": 0,
                        "aggregates": 0,
                        "commands": 0,
                        "events": 0,
                        "policies": 0,
                        "readmodels": 0,
                    }
                ),
                _Rec({"promoted_to": 0, "sourced_from": 0, "implements_bc": 0}),
                _Rec({"total_questions": 4, "attached_questions": 0}),
            ]

        def run(self, query, **params):
            rec = self.rows[self.idx]
            self.idx += 1
            return _Result(rec)

    class _Ctx:
        def __init__(self, s):
            self.s = s

        def __enter__(self):
            return self.s

        def __exit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr(pipeline_verification, "get_session", lambda: _Ctx(_Session()))
    out = pipeline_verification.verify_pipeline_status("sid-2")
    assert out["summary"]["pipeline_ready"] is False
    assert out["summary"]["bpm_ok"] is False
