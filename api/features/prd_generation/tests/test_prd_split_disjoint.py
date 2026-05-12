"""End-to-end disjointness test for PRD vs CLAUDE/.cursorrules (T078, SC-011)."""
from __future__ import annotations

import pytest

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
    generate_claude_md,
    generate_cursor_rules,
    generate_main_prd,
)
from api.features.prd_generation.prd_split_lint import (
    PrdSplitLintError,
    lint_disjoint,
)


_BCS = [
    {"id": "bc1", "name": "Order", "aggregates": [{"name": "O", "commands": [{}], "events": [{}]}], "readmodels": [{}], "policies": [], "uis": [{}]},
    {"id": "bc2", "name": "Payment", "aggregates": [], "readmodels": [], "policies": [], "uis": []},
]


def _cfg(**overrides) -> TechStackConfig:
    base = dict(
        project_name="demo",
        language=Language.JAVA,
        framework=Framework.SPRING_BOOT,
        ai_assistant=AIAssistant.CLAUDE,
        spec_format=SpecFormat.DDD,
        include_frontend=True,
        frontend_framework=FrontendFramework.VUE,
        deployment=DeploymentStyle.MICROSERVICES,
    )
    base.update(overrides)
    return TechStackConfig(**base)


@pytest.mark.parametrize("ai", [AIAssistant.CLAUDE, AIAssistant.CURSOR])
@pytest.mark.parametrize("spec", [SpecFormat.PRD, SpecFormat.DDD])
@pytest.mark.parametrize("include_frontend", [False, True])
def test_render_passes_disjointness_lint_across_combinations(
    ai: AIAssistant, spec: SpecFormat, include_frontend: bool
):
    """Every combination of (ai_assistant, spec_format, include_frontend)
    produces PRD ↔ constitution files that pass the disjointness lint."""
    cfg = _cfg(
        ai_assistant=ai,
        spec_format=spec,
        include_frontend=include_frontend,
        frontend_framework=FrontendFramework.VUE if include_frontend else None,
    )
    prd = generate_main_prd(_BCS, cfg)
    if ai == AIAssistant.CLAUDE:
        claude = generate_claude_md(_BCS, cfg)
        lint_disjoint(prd, claude, constitution_filename="CLAUDE.md")
    else:
        cursor_rules = generate_cursor_rules(cfg)
        # generate_cursor_rules contains DDD-principle imperatives by
        # design — that's the *constitution* side. The lint only asserts
        # PRD.md is clean and the constitution doesn't restate the
        # inventory tables.
        lint_disjoint(prd, cursor_rules, constitution_filename=".cursorrules")


def test_prd_carries_inventory_tables():
    """PRD.md MUST own the compositional inventory."""
    cfg = _cfg()
    prd = generate_main_prd(_BCS, cfg)
    assert "## Technology Stack" in prd
    assert "## Bounded Contexts" in prd
    assert "| BC Name |" in prd
    assert "| Order |" in prd
    assert "| Payment |" in prd


def test_claude_md_does_not_restate_inventory_tables():
    """CLAUDE.md MUST NOT restate the stack table or BC inventory headers."""
    cfg = _cfg()
    claude = generate_claude_md(_BCS, cfg)
    # The lint's regex flags these specific H2 headers.
    assert "## Technology Stack" not in claude
    assert "## Bounded Contexts" not in claude


def test_prd_carries_no_prescriptive_imperatives():
    """PRD.md body MUST be free of prescriptive imperatives."""
    cfg = _cfg()
    prd = generate_main_prd(_BCS, cfg)
    # The lint asserts this via regex; here we check the spec's intent.
    # We allow keywords in fenced code blocks / tables, but the bare PRD
    # we emit has none of those zones containing imperatives, so a plain
    # search is fine.
    for forbidden in ("you MUST", "you SHALL", "Before starting", "🚨", "CRITICAL"):
        assert forbidden not in prd, f"PRD.md contains forbidden imperative: {forbidden!r}"
