"""End-to-end test: zip carries role-based agents, zero per-BC agents (T079, SC-012)."""
from __future__ import annotations

import io
import zipfile

import pytest
from unittest.mock import patch

from api.features.prd_generation.prd_api_contracts import FrontendFramework


@pytest.fixture
def _bcs():
    return [
        {"id": "bc1", "name": "Membership", "aggregates": [], "readmodels": [], "policies": [], "uis": []},
        {"id": "bc2", "name": "Payment", "aggregates": [], "readmodels": [], "policies": [], "uis": []},
    ]


def _payload(**tech_stack_overrides):
    """Build a /api/prd/download request body."""
    base = dict(
        ai_assistant="claude",
        spec_format="ddd",
        include_frontend=True,
        frontend_framework="vue",
        deployment="microservices",
    )
    base.update(tech_stack_overrides)
    return {"tech_stack": base}


def _do_download(_bcs, **tech_stack_overrides) -> zipfile.ZipFile:
    """Call POST /api/prd/download via FastAPI TestClient and return the
    extracted zip ready for inspection."""
    from fastapi.testclient import TestClient

    from api.main import app

    # Mock the BC loader + the in-process DDD artifact pack so we don't
    # need Neo4j running for this packaging-shape test.
    with patch(
        "api.features.prd_generation.routes.prd_export.get_bcs_from_nodes",
        return_value=_bcs,
    ), patch(
        "api.features.ddd_spec.inproc.pack_ddd_artifacts_to_zip",
        return_value=[],
    ), patch(
        "api.features.ddd_spec.inproc.render_frontend_spec_to_zip",
        return_value=[],
    ):
        client = TestClient(app)
        r = client.post("/api/prd/download", json=_payload(**tech_stack_overrides))
    assert r.status_code == 200, r.text
    return zipfile.ZipFile(io.BytesIO(r.content))


def test_zip_contains_role_based_agents_when_ddd_and_frontend(_bcs):
    zf = _do_download(_bcs)
    names = set(zf.namelist())
    assert ".claude/agents/ddd-specialist.md" in names
    assert ".claude/agents/frontend-engineer.md" in names
    assert ".claude/commands/generate-frontend.md" in names


def test_zip_omits_frontend_engineer_when_frontend_not_included(_bcs):
    zf = _do_download(_bcs, include_frontend=False, frontend_framework=None)
    names = set(zf.namelist())
    # ddd-specialist stays (spec_format=ddd) but no frontend-engineer
    assert ".claude/agents/ddd-specialist.md" in names
    assert ".claude/agents/frontend-engineer.md" not in names
    assert ".claude/commands/generate-frontend.md" not in names


def test_zip_has_zero_per_bc_agent_files(_bcs):
    zf = _do_download(_bcs)
    names = set(zf.namelist())
    # No file matching the deprecated per-BC pattern.
    per_bc_pattern_hits = [
        n for n in names
        if n.startswith(".claude/agents/") and n.endswith("_agent.md")
    ]
    assert per_bc_pattern_hits == [], f"deprecated per-BC agents found: {per_bc_pattern_hits}"


def test_zip_contains_prd_and_claude_md_disjoint(_bcs):
    """The build aborts on lint failure — if it succeeded here, the
    rendered PRD↔CLAUDE pair passed the disjointness contract."""
    zf = _do_download(_bcs)
    names = set(zf.namelist())
    assert "PRD.md" in names
    assert "CLAUDE.md" in names
    prd = zf.read("PRD.md").decode("utf-8")
    claude = zf.read("CLAUDE.md").decode("utf-8")
    # Cheap sanity checks; the full lint is exercised in
    # test_prd_split_disjoint.py.
    assert "## Technology Stack" in prd
    assert "## Technology Stack" not in claude


def test_zip_does_not_emit_scene_json_sidecars(_bcs):
    """Scene-graph JSON sidecars are no longer emitted (2026-05-12
    amendment). The SVG is the only visual asset.
    """
    zf = _do_download(_bcs)
    names = set(zf.namelist())
    scene_json_hits = [n for n in names if n.endswith(".scene.json")]
    assert scene_json_hits == [], f"unexpected .scene.json files: {scene_json_hits}"


def test_zip_does_not_emit_frontend_prd_md(_bcs):
    """Frontend-PRD.md is dropped (2026-05-12 amendment) — its
    BC-centric content tends to leak BC-shaped thinking into the
    frontend workflow. The frontend perspective lives in
    `specs/frontend/*` instead, with naming pulled from each BC's
    `domain-terms.md` as needed.
    """
    zf = _do_download(_bcs)
    names = set(zf.namelist())
    assert "Frontend-PRD.md" not in names
    # Also confirm the planning path doesn't list it.
    from fastapi.testclient import TestClient
    from api.main import app

    with patch(
        "api.features.prd_generation.routes.prd_export.get_bcs_from_nodes",
        return_value=_bcs,
    ), patch(
        "api.features.ddd_spec.inproc.planned_paths_for_preview",
        return_value=[],
    ):
        client = TestClient(app)
        r = client.post("/api/prd/generate", json=_payload())
    assert r.status_code == 200
    assert "Frontend-PRD.md" not in r.json()["files_to_generate"]


def test_deprecated_per_bc_agents_reported_via_plan(_bcs):
    """The /generate planning endpoint surfaces deprecated per-BC paths
    so users can clean up their working copies."""
    from fastapi.testclient import TestClient

    from api.main import app

    with patch(
        "api.features.prd_generation.routes.prd_export.get_bcs_from_nodes",
        return_value=_bcs,
    ), patch(
        "api.features.ddd_spec.inproc.planned_paths_for_preview",
        return_value=[],
    ):
        client = TestClient(app)
        r = client.post("/api/prd/generate", json=_payload())
    assert r.status_code == 200, r.text
    body = r.json()
    deprecated = body.get("deprecated_per_bc_agents", [])
    assert len(deprecated) == 2
    paths = {item["existing_path"] for item in deprecated}
    assert paths == {
        ".claude/agents/membership_agent.md",
        ".claude/agents/payment_agent.md",
    }
    for item in deprecated:
        assert item["reason"] == "deprecated_per_bc_agent"
