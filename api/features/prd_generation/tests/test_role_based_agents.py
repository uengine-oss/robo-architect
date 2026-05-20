"""Tests for the role-based agent generators (T064, US7 / research D10)."""
from __future__ import annotations

import re

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
    generate_role_agent_ddd_specialist,
    generate_role_agent_frontend_engineer,
)


def _cfg(**overrides) -> TechStackConfig:
    base = dict(
        project_name="test",
        ai_assistant=AIAssistant.CLAUDE,
        spec_format=SpecFormat.DDD,
        language=Language.JAVA,
        framework=Framework.SPRING_BOOT,
        deployment=DeploymentStyle.MICROSERVICES,
        include_frontend=True,
        frontend_framework=FrontendFramework.VUE,
    )
    base.update(overrides)
    return TechStackConfig(**base)


# --- ddd-specialist ----------------------------------------------------


def test_ddd_specialist_references_required_skills_by_relative_path():
    body = generate_role_agent_ddd_specialist(_cfg())
    required_refs = [
        ".claude/skills/ddd-spec-implementation.md",
        ".claude/skills/ddd-principles.md",
        ".claude/skills/eventstorming-implementation.md",
        ".claude/skills/gwt-test-generation.md",
        ".claude/skills/spring-boot.md",
    ]
    for ref in required_refs:
        assert ref in body, f"ddd-specialist missing skill reference: {ref}"


def test_ddd_specialist_lists_invoking_slash_commands():
    body = generate_role_agent_ddd_specialist(_cfg())
    assert "/implement-ddd-bc" in body
    assert "/implement-ddd-wireframe" in body


def test_ddd_specialist_includes_api_gateway_for_microservices_only():
    micro = generate_role_agent_ddd_specialist(_cfg(deployment=DeploymentStyle.MICROSERVICES))
    mono = generate_role_agent_ddd_specialist(_cfg(deployment=DeploymentStyle.MODULAR_MONOLITH))
    assert ".claude/skills/api-gateway.md" in micro
    assert ".claude/skills/api-gateway.md" not in mono


def test_ddd_specialist_body_does_not_restate_skill_content():
    """The agent must reference skills, not duplicate them. Specifically
    it should not contain the H2 / H3 section titles a skill file uses."""
    body = generate_role_agent_ddd_specialist(_cfg())
    # If the agent included a full DDD-principles section it would
    # contain "## Naming Conventions" or similar. We assert it doesn't.
    forbidden_section_titles = [
        "## Naming Conventions",
        "## EARS Translation Rules",
        "## GWT Test Patterns",
    ]
    for title in forbidden_section_titles:
        assert title not in body, f"ddd-specialist restates skill section: {title}"


def test_ddd_specialist_has_frontmatter():
    body = generate_role_agent_ddd_specialist(_cfg())
    assert body.startswith("---\n")
    assert "name: ddd-specialist" in body
    assert "description:" in body


# --- frontend-engineer ------------------------------------------------


def test_frontend_engineer_references_frontend_skill():
    body = generate_role_agent_frontend_engineer(_cfg(frontend_framework=FrontendFramework.VUE))
    assert ".claude/skills/vue.md" in body
    body_r = generate_role_agent_frontend_engineer(_cfg(frontend_framework=FrontendFramework.REACT))
    assert ".claude/skills/react.md" in body_r
    body_s = generate_role_agent_frontend_engineer(_cfg(frontend_framework=FrontendFramework.SVELTE))
    assert ".claude/skills/svelte.md" in body_s


def test_frontend_engineer_lists_generate_frontend_command():
    body = generate_role_agent_frontend_engineer(_cfg())
    assert "/generate-frontend" in body


def test_frontend_engineer_has_frontmatter():
    body = generate_role_agent_frontend_engineer(_cfg())
    assert body.startswith("---\n")
    assert "name: frontend-engineer" in body


# --- naming-from-UL / structure-from-flow operating model ---------------


def test_frontend_engineer_states_two_rule_model():
    """Names come from `domain-terms.md`; everything else from ui-flow.md."""
    body = generate_role_agent_frontend_engineer(_cfg())
    assert "Ubiquitous Language" in body
    assert "domain-terms.md" in body
    assert "ui-flow.md" in body
    # "Aliases to AVOID" cited as forbidden names.
    assert "Aliases to AVOID" in body


def test_frontend_engineer_does_not_point_at_frontend_prd_md():
    """Frontend-PRD.md is removed (2026-05-12 amendment)."""
    body = generate_role_agent_frontend_engineer(_cfg())
    assert "Frontend-PRD.md" not in body


def test_frontend_engineer_forbids_browsing_full_bc_folder():
    """The agent must not read bc-<slug>.md or aggregate-<slug>.md for IA."""
    import re

    body = generate_role_agent_frontend_engineer(_cfg())
    # Tolerate the multi-line wrapping in the f-string — collapse all
    # whitespace runs to a single space before matching.
    flat = re.sub(r"\s+", " ", body).lower()
    assert (
        "do not browse" in flat
        or "do not read" in flat
        or "not for shaping" in flat
    )
