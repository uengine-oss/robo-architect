from __future__ import annotations

from api.features.ingestion.hybrid.pipeline_verification import verify_pipeline_status
from api.features.prd_generation.prd_model_data import get_bcs_from_nodes


def run_pipeline_e2e_check(session_id: str) -> dict:
    """Operational check for the target chain:
    BPM 생성 -> Rule 탐색/매핑 -> ES 승격 -> PRD 생성 입력.
    """

    pipeline = verify_pipeline_status(session_id)
    bcs = get_bcs_from_nodes(None, session_id=session_id)

    prd = {
        "bc_count": len(bcs),
        "has_any_bc": len(bcs) > 0,
        "non_empty_specs_candidate": 0,
    }
    for bc in bcs:
        # Minimal health: BC has id/name and at least one major ES section.
        has_major = bool(
            (bc.get("aggregates") or [])
            or (bc.get("readmodels") or [])
            or (bc.get("policies") or [])
            or (bc.get("userStories") or [])
        )
        if bc.get("id") and bc.get("name") and has_major:
            prd["non_empty_specs_candidate"] += 1

    prd["ready"] = bool(prd["has_any_bc"] and prd["non_empty_specs_candidate"] > 0)

    return {
        "session_id": session_id,
        "pipeline": pipeline,
        "prd_input_check": prd,
        "summary": {
            "e2e_ready": bool(pipeline["summary"]["pipeline_ready"] and prd["ready"]),
            "pipeline_ready": bool(pipeline["summary"]["pipeline_ready"]),
            "prd_input_ready": bool(prd["ready"]),
        },
    }
