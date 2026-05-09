from __future__ import annotations

from api.features.ingestion.hybrid import pipeline_e2e_check


def test_run_pipeline_e2e_check_ready(monkeypatch):
    monkeypatch.setattr(
        pipeline_e2e_check,
        "verify_pipeline_status",
        lambda sid: {
            "summary": {
                "pipeline_ready": True,
                "bpm_ok": True,
                "mapping_ok": True,
                "es_ok": True,
                "prd_ready": True,
            }
        },
    )
    monkeypatch.setattr(
        pipeline_e2e_check,
        "get_bcs_from_nodes",
        lambda node_ids, session_id=None: [
            {"id": "bc-1", "name": "billing", "aggregates": [{"id": "agg-1"}]},
            {"id": "bc-2", "name": "auth", "readmodels": [{"id": "rm-1"}]},
        ],
    )

    out = pipeline_e2e_check.run_pipeline_e2e_check("sid-ok")
    assert out["summary"]["e2e_ready"] is True
    assert out["prd_input_check"]["bc_count"] == 2
    assert out["prd_input_check"]["non_empty_specs_candidate"] == 2


def test_run_pipeline_e2e_check_not_ready_when_prd_input_empty(monkeypatch):
    monkeypatch.setattr(
        pipeline_e2e_check,
        "verify_pipeline_status",
        lambda sid: {"summary": {"pipeline_ready": True}},
    )
    monkeypatch.setattr(
        pipeline_e2e_check,
        "get_bcs_from_nodes",
        lambda node_ids, session_id=None: [],
    )

    out = pipeline_e2e_check.run_pipeline_e2e_check("sid-empty")
    assert out["summary"]["pipeline_ready"] is True
    assert out["summary"]["prd_input_ready"] is False
    assert out["summary"]["e2e_ready"] is False
