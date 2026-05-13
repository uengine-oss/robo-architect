"""Tests for viewport classification and the framework.md viewport block.

Covers research D7+ amendment (2026-05-12):
  - ``wireframe_render.classify_viewport`` + ``extract_viewport_class``
  - ``WireframeProjection.viewport_class`` propagation through
    ``repository.load_frontend_composition`` → ``UIFlowEntry`` /
    ``MenuEntry``
  - ``viewport_summary`` + ``dominant_viewport`` aggregation
  - ``frontend_renderer.render_framework_md`` Viewport summary block
  - ``frontend_viewport_dominant`` / ``frontend_viewport_mixed`` warnings
  - ``generate_role_agent_frontend_engineer`` +
    ``generate_claude_command_generate_frontend`` Viewport intent steps
"""
from __future__ import annotations

import json

import pytest

from api.features.ddd_spec import repository, wireframe_render
from api.features.ddd_spec.frontend_renderer import (
    _emit_warnings,
    render_framework_md,
)
from api.features.ddd_spec.projection import (
    BoundedContextProjection,
    FrontendCompositionProjection,
    UserStoryProjection,
    WireframeProjection,
)
from api.features.ddd_spec.service import jinja_env


# --- classify_viewport ----------------------------------------------------


@pytest.mark.parametrize(
    ("width", "height", "expected"),
    [
        # Phones (portrait + landscape both classed by width since wireframes
        # are always drawn in the device's natural orientation).
        (375, 812, "mobile"),   # iPhone 13 mini portrait
        (390, 844, "mobile"),   # iPhone 14 portrait
        (414, 896, "mobile"),   # iPhone 11 Pro Max portrait
        (480, 800, "mobile"),   # Android edge of mobile bucket
        # Tablets.
        (481, 800, "tablet"),   # one pixel past mobile
        (768, 1024, "tablet"),  # iPad portrait
        (834, 1194, "tablet"),  # iPad Pro 11" portrait
        (1024, 1366, "tablet"), # iPad Pro 12.9" portrait
        # Desktops.
        (1025, 768, "desktop"), # one pixel past tablet
        (1280, 800, "desktop"),
        (1440, 900, "desktop"),
        (1920, 1080, "desktop"),
    ],
)
def test_classify_viewport_buckets_by_width(width, height, expected):
    assert wireframe_render.classify_viewport(width, height) == expected


@pytest.mark.parametrize("w,h", [(0, 0), (-1, 100), (100, 0), (0, 640)])
def test_classify_viewport_rejects_nonpositive(w, h):
    assert wireframe_render.classify_viewport(w, h) is None


def test_classify_viewport_rejects_non_numeric():
    assert wireframe_render.classify_viewport("nope", 640) is None
    assert wireframe_render.classify_viewport(None, 640) is None


# --- extract_viewport_class ----------------------------------------------


def test_extract_viewport_class_open_pencil_shape():
    sg = json.dumps(
        {
            "nodes": {
                "root": {"id": "root", "type": "FRAME", "width": 0, "height": 0,
                         "childIds": ["page"]},
                "page": {"id": "page", "type": "FRAME", "name": "Login",
                         "width": 375, "height": 812, "childIds": []},
            },
            "rootId": "root",
        }
    )
    assert wireframe_render.extract_viewport_class(sg) == "mobile"


def test_extract_viewport_class_legacy_inline_shape():
    sg = json.dumps({"root": {"type": "frame", "width": 1440, "height": 900}})
    assert wireframe_render.extract_viewport_class(sg) == "desktop"


@pytest.mark.parametrize("bad", [None, "", "not-json", "{}", "[]"])
def test_extract_viewport_class_handles_missing_or_invalid(bad):
    assert wireframe_render.extract_viewport_class(bad) is None


def test_extract_viewport_class_returns_none_for_dimensionless():
    sg = json.dumps({"root": {"type": "frame"}})
    assert wireframe_render.extract_viewport_class(sg) is None


# --- composition aggregation ---------------------------------------------


def _bc_with_wireframes(*viewport_widths: float) -> BoundedContextProjection:
    """Build a BC with one User Story whose wireframes carry the given
    viewport widths via ``viewport_class`` derived from each width."""
    wireframes = []
    for idx, w in enumerate(viewport_widths):
        vp = wireframe_render.classify_viewport(w, 800) if w else None
        wireframes.append(
            WireframeProjection(
                ui_id=f"ui-{idx}", name=f"Screen {idx}", slug=f"screen-{idx}",
                viewport_class=vp,
            )
        )
    return BoundedContextProjection(
        id="bc-1", name="One", slug="one",
        user_stories=[
            UserStoryProjection(
                id="US-1", title="Story 1", priority="P1",
                wireframes=wireframes,
            )
        ],
    )


def test_load_frontend_composition_aggregates_dominant_mobile():
    bc = _bc_with_wireframes(375, 390, 414, 1440)  # 3 mobile + 1 desktop
    comp = repository.load_frontend_composition(
        framework="vue", framework_conventions=None, bcs=[bc], flows=[]
    )
    assert comp.viewport_summary["mobile"] == 3
    assert comp.viewport_summary["desktop"] == 1
    assert comp.viewport_summary["tablet"] == 0
    assert comp.dominant_viewport == "mobile"  # 3/4 = 75% ≥ 70%


def test_load_frontend_composition_mixed_when_no_class_meets_threshold():
    bc = _bc_with_wireframes(375, 768, 1440)  # 1 of each — none ≥ 70%
    comp = repository.load_frontend_composition(
        framework="vue", framework_conventions=None, bcs=[bc], flows=[]
    )
    assert comp.viewport_summary == {"mobile": 1, "tablet": 1, "desktop": 1, "unknown": 0}
    assert comp.dominant_viewport is None


def test_load_frontend_composition_counts_unknown_separately():
    bc = _bc_with_wireframes(375, 0)  # one mobile, one with no viewport
    comp = repository.load_frontend_composition(
        framework="vue", framework_conventions=None, bcs=[bc], flows=[]
    )
    assert comp.viewport_summary["mobile"] == 1
    assert comp.viewport_summary["unknown"] == 1
    # The unknown is excluded from the dominant calculation, so 1/1 known = 100%.
    assert comp.dominant_viewport == "mobile"


def test_ui_flow_entries_inherit_viewport_class():
    bc = _bc_with_wireframes(375, 1440)
    comp = repository.load_frontend_composition(
        framework="vue", framework_conventions=None, bcs=[bc], flows=[]
    )
    # All four ended up unreferenced (no edges between them since only
    # consecutive-wireframes-in-a-story edges exist), but viewport_class
    # must still propagate.
    classes = {e.viewport_class for e in comp.ui_flow + comp.unreferenced_uis}
    assert classes == {"mobile", "desktop"}
    # Menu hints also carry the class.
    menu_classes = {h.viewport_class for h in comp.menu}
    assert menu_classes == {"mobile", "desktop"}


# --- framework.md rendering ----------------------------------------------


def _comp(summary: dict[str, int], dominant: str | None = None) -> FrontendCompositionProjection:
    return FrontendCompositionProjection(
        framework="vue",
        framework_conventions=None,
        viewport_summary=summary,
        dominant_viewport=dominant,
    )


def test_framework_md_renders_viewport_summary_with_dominant():
    md = render_framework_md(
        jinja_env(),
        _comp({"mobile": 8, "tablet": 0, "desktop": 2, "unknown": 0}, dominant="mobile"),
        generated_at="2026-05-12T00:00:00Z",
    )
    assert "## Viewport summary" in md
    assert "Mobile (frame width ≤ 480px): 8" in md
    assert "Desktop (frame width > 1024px): 2" in md
    assert "Dominant: **mobile**" in md
    # Must include the agent-prompt instruction so the rendered file
    # tells the agent to ask the user before designing the IA.
    assert "MUST ask the user" in md


def test_framework_md_renders_mixed_when_no_dominant():
    md = render_framework_md(
        jinja_env(),
        _comp({"mobile": 1, "tablet": 1, "desktop": 1, "unknown": 0}, dominant=None),
        generated_at="2026-05-12T00:00:00Z",
    )
    assert "Dominant: **mixed — ask the user**" in md


# --- warnings ------------------------------------------------------------


class _CapCtx:
    def __init__(self):
        self.warnings: list[tuple[str, str, dict | None]] = []

    def warn(self, code, message, target=None):
        self.warnings.append((code, message, target))


def test_emit_warnings_includes_dominant_viewport_when_one_class_wins():
    ctx = _CapCtx()
    comp = _comp({"mobile": 8, "tablet": 0, "desktop": 2, "unknown": 0}, dominant="mobile")
    _emit_warnings(ctx, comp, cross_bc_edge_count=1)
    codes = [c for c, _, _ in ctx.warnings]
    assert "frontend_viewport_dominant" in codes
    assert "frontend_viewport_mixed" not in codes


def test_emit_warnings_includes_mixed_when_no_dominant():
    ctx = _CapCtx()
    comp = _comp({"mobile": 1, "tablet": 1, "desktop": 1, "unknown": 0}, dominant=None)
    _emit_warnings(ctx, comp, cross_bc_edge_count=1)
    codes = [c for c, _, _ in ctx.warnings]
    assert "frontend_viewport_mixed" in codes
    assert "frontend_viewport_dominant" not in codes


def test_emit_warnings_skips_viewport_codes_when_no_known_wireframes():
    """All-unknown projects shouldn't trigger either viewport warning
    (there's nothing to be dominant or mixed about)."""
    ctx = _CapCtx()
    comp = _comp({"mobile": 0, "tablet": 0, "desktop": 0, "unknown": 3}, dominant=None)
    _emit_warnings(ctx, comp, cross_bc_edge_count=1)
    codes = [c for c, _, _ in ctx.warnings]
    assert "frontend_viewport_dominant" not in codes
    assert "frontend_viewport_mixed" not in codes


# --- agent + slash command bodies ----------------------------------------


def test_role_agent_frontend_engineer_contains_viewport_intent_step():
    from api.features.prd_generation.prd_artifact_generation import (
        generate_role_agent_frontend_engineer,
    )
    from api.features.prd_generation.prd_api_contracts import TechStackConfig

    config = TechStackConfig(
        ai_assistant="claude",
        spec_format="ddd",
        framework="fastapi",
        include_frontend=True,
        frontend_framework="vue",
    )
    body = generate_role_agent_frontend_engineer(config)
    assert "Viewport intent check" in body
    assert "Viewport summary" in body
    # The stop-condition list must mention the mixed → ask-user gate.
    assert "mixed — ask the user" in body


def test_generate_frontend_command_contains_viewport_step():
    from api.features.prd_generation.prd_artifact_generation import (
        generate_claude_command_generate_frontend,
    )
    from api.features.prd_generation.prd_api_contracts import TechStackConfig

    config = TechStackConfig(
        ai_assistant="claude",
        spec_format="ddd",
        framework="fastapi",
        include_frontend=True,
        frontend_framework="vue",
    )
    body = generate_claude_command_generate_frontend(config)
    # Step 0 must come BEFORE step 1 in the Plan section.
    plan_idx = body.find("## Plan")
    step0_idx = body.find("Confirm viewport intent", plan_idx)
    step1_idx = body.find("\n1. Build the project skeleton", plan_idx)
    assert plan_idx >= 0
    assert step0_idx >= 0
    assert step1_idx >= 0
    assert step0_idx < step1_idx
    # Stop conditions must mention viewport-tag conflicts.
    assert "[viewport: ...]" in body
    # The user-facing question template must survive f-string brace escaping.
    assert "{counts}" in body
