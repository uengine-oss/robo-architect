"""Tests for the `/generate-frontend` slash command generator (T065, FR-024)."""
from __future__ import annotations

from api.features.prd_generation.prd_api_contracts import (
    AIAssistant,
    DeploymentStyle,
    Framework,
    FrontendFramework,
    Language,
    SpecFormat,
    TechStackConfig,
)
from api.features.prd_generation.prd_artifact_generation import (
    generate_claude_command_generate_frontend,
)


def _cfg(framework: FrontendFramework = FrontendFramework.VUE) -> TechStackConfig:
    return TechStackConfig(
        project_name="test",
        ai_assistant=AIAssistant.CLAUDE,
        spec_format=SpecFormat.DDD,
        language=Language.JAVA,
        framework=Framework.SPRING_BOOT,
        deployment=DeploymentStyle.MICROSERVICES,
        include_frontend=True,
        frontend_framework=framework,
    )


def test_command_body_reads_all_three_frontend_spec_files():
    body = generate_claude_command_generate_frontend(_cfg())
    for ref in (
        "specs/frontend/framework.md",
        "specs/frontend/menu-structure.md",
        "specs/frontend/ui-flow.md",
    ):
        assert ref in body, f"/generate-frontend missing reference: {ref}"


def test_command_body_walks_requirements_assets():
    body = generate_claude_command_generate_frontend(_cfg())
    assert "requirements.assets" in body
    assert ".svg" in body
    # Scene-graph JSON sidecars are no longer emitted (2026-05-12
    # amendment); the command must not point at one.
    assert ".scene.json" not in body


def test_command_body_invokes_frontend_engineer_agent():
    body = generate_claude_command_generate_frontend(_cfg())
    assert "frontend-engineer.md" in body


def test_command_body_carries_declared_framework_verbatim():
    for fw in (FrontendFramework.VUE, FrontendFramework.REACT, FrontendFramework.SVELTE):
        body = generate_claude_command_generate_frontend(_cfg(framework=fw))
        assert f"in **{fw.value}**" in body, f"framework not echoed for {fw.value}"


def test_command_body_has_frontmatter():
    body = generate_claude_command_generate_frontend(_cfg())
    assert body.startswith("---\n")
    assert "description:" in body
    assert "argument-hint:" in body


# --- two-rule operating model: naming vs structure --------------------


def test_command_body_separates_naming_from_structure():
    """Names come from BC domain-terms.md (Ubiquitous Language);
    everything else from the UI flow. The body MUST state this."""
    body = generate_claude_command_generate_frontend(_cfg())
    assert "Ubiquitous Language" in body
    assert "domain-terms.md" in body
    # The body explicitly forbids using BC layout for IA.
    assert "ui-flow.md" in body
    # The body cites "Aliases to AVOID" as forbidden names.
    assert "Aliases to AVOID" in body


def test_command_body_forbids_other_bc_files_for_ia():
    """Beyond domain-terms.md, the agent must not browse the BC folder
    looking for structure cues."""
    import re

    body = generate_claude_command_generate_frontend(_cfg())
    flat = re.sub(r"\s+", " ", body).lower()
    # The body explicitly names bc-<slug>.md / aggregate-<slug>.md as
    # files NOT to read for IA, and explicitly forbids it.
    assert "bc-<slug>.md" in flat or "bc-" in flat
    assert "aggregate-" in flat
    assert "do not browse" in flat or "do not read" in flat


def test_command_body_does_not_reference_frontend_prd_md():
    """Frontend-PRD.md is removed — the command must not point at it."""
    body = generate_claude_command_generate_frontend(_cfg())
    assert "Frontend-PRD.md" not in body


def test_command_body_emphasises_business_task_framing():
    """Each screen is framed as a user task, not as a CRUD operation
    on a BC entity."""
    body = generate_claude_command_generate_frontend(_cfg())
    # "business" + "task" both appear in the principles block.
    assert "business" in body.lower()
    assert "task" in body.lower()
