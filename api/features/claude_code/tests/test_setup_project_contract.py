"""Tests for /api/claude-code/setup-project — must follow the same
contract as /api/prd/download (no per-BC agents, no Frontend-PRD.md,
no .scene.json, role-based agents emitted when applicable).
"""
from __future__ import annotations

import os
import tempfile

import pytest
from unittest.mock import patch


@pytest.fixture
def _bcs():
    return [
        {"id": "bc1", "name": "Membership", "aggregates": [], "readmodels": [], "policies": [], "uis": []},
        {"id": "bc2", "name": "Payment", "aggregates": [], "readmodels": [], "policies": [], "uis": []},
    ]


def _setup_payload(target_dir: str, **tech_stack_overrides) -> dict:
    base = dict(
        ai_assistant="claude",
        spec_format="ddd",
        include_frontend=True,
        frontend_framework="vue",
        deployment="microservices",
    )
    base.update(tech_stack_overrides)
    return {"project_path": target_dir, "prd_request": {"tech_stack": base}}


def _do_setup(target: str, _bcs, **tech_stack_overrides):
    """Invoke /api/claude-code/setup-project; return (status, body)."""
    from fastapi.testclient import TestClient
    from api.main import app

    with patch(
        "api.features.prd_generation.routes.prd_export.get_bcs_from_nodes",
        return_value=_bcs,
    ), patch(
        "api.features.prd_generation.prd_model_data.get_bcs_from_nodes",
        return_value=_bcs,
    ), patch(
        "api.features.ddd_spec.inproc.pack_ddd_artifacts_to_zip",
        return_value=[],
    ), patch(
        "api.features.ddd_spec.inproc.render_frontend_spec_to_zip",
        return_value=[],
    ):
        client = TestClient(app)
        r = client.post("/api/claude-code/setup-project", json=_setup_payload(target, **tech_stack_overrides))
    return r


def test_setup_project_extracts_role_based_agents_no_per_bc(_bcs):
    """The on-disk layout MUST mirror the new zip contract."""
    with tempfile.TemporaryDirectory(prefix="setup-test-") as tmp:
        r = _do_setup(tmp, _bcs)
        assert r.status_code == 200, r.text
        # Role-based agents present.
        assert os.path.isfile(os.path.join(tmp, ".claude/agents/ddd-specialist.md"))
        assert os.path.isfile(os.path.join(tmp, ".claude/agents/frontend-engineer.md"))
        # /generate-frontend slash command present.
        assert os.path.isfile(os.path.join(tmp, ".claude/commands/generate-frontend.md"))
        # No per-BC agent files.
        agents_dir = os.path.join(tmp, ".claude/agents")
        per_bc_hits = [
            f for f in os.listdir(agents_dir)
            if f.endswith("_agent.md")
        ]
        assert per_bc_hits == [], f"unexpected per-BC agents in setup output: {per_bc_hits}"


def test_setup_project_does_not_emit_frontend_prd_or_scene_json(_bcs):
    with tempfile.TemporaryDirectory(prefix="setup-test-") as tmp:
        r = _do_setup(tmp, _bcs)
        assert r.status_code == 200, r.text
        assert not os.path.exists(os.path.join(tmp, "Frontend-PRD.md"))
        # Walk the tree — no .scene.json anywhere.
        scene_json_hits = []
        for root, _dirs, files in os.walk(tmp):
            for f in files:
                if f.endswith(".scene.json"):
                    scene_json_hits.append(os.path.join(root, f))
        assert scene_json_hits == [], f"unexpected .scene.json files: {scene_json_hits}"


def test_setup_project_cleans_up_legacy_files(_bcs):
    """A re-run against a directory that holds legacy artifacts must
    remove the deprecated files (per-BC agents, Frontend-PRD.md,
    scene-graph JSON sidecars) so old and new contracts don't coexist.
    """
    with tempfile.TemporaryDirectory(prefix="setup-cleanup-") as tmp:
        # Seed legacy artifacts a previous setup-project might have written.
        os.makedirs(os.path.join(tmp, ".claude/agents"), exist_ok=True)
        os.makedirs(os.path.join(tmp, "specs/bounded-contexts/membership/requirements.assets"), exist_ok=True)
        legacy_per_bc_a = os.path.join(tmp, ".claude/agents/membership_agent.md")
        legacy_per_bc_b = os.path.join(tmp, ".claude/agents/payment_agent.md")
        legacy_frontend_prd = os.path.join(tmp, "Frontend-PRD.md")
        legacy_scene_json = os.path.join(tmp, "specs/bounded-contexts/membership/requirements.assets/US-1-screen.scene.json")
        for p in (legacy_per_bc_a, legacy_per_bc_b, legacy_frontend_prd, legacy_scene_json):
            with open(p, "w") as f:
                f.write("legacy")

        # Also seed an unrelated hand-written agent that does NOT match
        # any BC name — must NOT be deleted.
        custom_agent = os.path.join(tmp, ".claude/agents/custom_helper.md")
        with open(custom_agent, "w") as f:
            f.write("hand-written")

        r = _do_setup(tmp, _bcs)
        assert r.status_code == 200, r.text
        body = r.json()

        # All four legacy files are gone.
        assert not os.path.exists(legacy_per_bc_a)
        assert not os.path.exists(legacy_per_bc_b)
        assert not os.path.exists(legacy_frontend_prd)
        assert not os.path.exists(legacy_scene_json)
        # The unrelated user file survives.
        assert os.path.exists(custom_agent)

        # Response surfaces what was removed (paths relative to project_path).
        removed = set(body.get("deprecated_removed", []))
        assert ".claude/agents/membership_agent.md" in removed
        assert ".claude/agents/payment_agent.md" in removed
        assert "Frontend-PRD.md" in removed
        assert any(p.endswith("US-1-screen.scene.json") for p in removed), removed


def test_setup_project_enforces_frontend_framework_required(_bcs):
    """FR-020 also fires on the setup-project path."""
    with tempfile.TemporaryDirectory(prefix="setup-test-") as tmp:
        from fastapi.testclient import TestClient
        from api.main import app

        with patch(
            "api.features.prd_generation.prd_model_data.get_bcs_from_nodes",
            return_value=_bcs,
        ):
            client = TestClient(app)
            r = client.post(
                "/api/claude-code/setup-project",
                json={
                    "project_path": tmp,
                    "prd_request": {
                        "tech_stack": {
                            "ai_assistant": "claude",
                            "spec_format": "ddd",
                            "include_frontend": True,
                            # frontend_framework deliberately omitted
                        }
                    },
                },
            )
        assert r.status_code == 400, r.text
        assert r.json()["detail"]["code"] == "frontend_framework_required"
