"""Render ``specs/frontend/`` artifact set (research D7).

Three sub-renderers driven by :class:`FrontendCompositionProjection`:

- :func:`render_framework_md` → ``framework.md``
- :func:`render_menu_md`      → ``menu-structure.md``
- :func:`render_ui_flow_md`   → ``ui-flow.md``

The renderer emits warnings via the supplied :class:`GenerationContext`
for: unsupported framework, no-cross-BC fallback, cycle-broken edges,
unreferenced UIs.
"""
from __future__ import annotations

from typing import Optional

from jinja2 import Environment

from api.features.ddd_spec import paths as paths_mod
from api.features.ddd_spec.projection import (
    FrontendCompositionProjection,
)
from api.features.ddd_spec.schemas import ArtifactFileInfo, SkippedItem


def _bc_name_lookup(comp: FrontendCompositionProjection):
    """Closure used by the Jinja templates to look up BC names by id."""
    by_id = {bc.id: bc.name or bc.slug for bc in comp.bounded_contexts}

    def _bc_name_by_id(bc_id: Optional[str]) -> str:
        if not bc_id:
            return "(unknown)"
        return by_id.get(bc_id, bc_id)

    return _bc_name_by_id


def _emit_warnings(ctx, comp: FrontendCompositionProjection, *, cross_bc_edge_count: int) -> None:
    """Surface the four amendment warnings up to the caller's context.

    Caller invokes this once per generation; renderers stay pure-string.
    """
    if comp.framework_conventions is None:
        ctx.warn(
            "frontend_framework_unsupported",
            f"No curated conventions for framework '{comp.framework}'; rendered with (no curated conventions — confirm).",
            {"framework": comp.framework},
        )
    if cross_bc_edge_count == 0:
        ctx.warn(
            "ui_flow_no_cross_bc_edges",
            "No cross-BC Policy/Event edges to sequence by; ui-flow.md falls back to BC insertion order.",
            {},
        )
    for src, dst in comp.cycle_broken_edges:
        ctx.warn(
            "ui_flow_cycle_broken",
            f"Cycle detected in UI flow DAG; removed back-edge {src} → {dst} to linearise.",
            {"from_node": src, "to_node": dst},
        )
    for entry in comp.unreferenced_uis:
        ctx.warn(
            "ui_unreferenced_flow",
            f"Bound UI '{entry.wireframe_slug}' (story {entry.user_story_id}) is unreferenced by any flow; appended at the tail of ui-flow.md.",
            {
                "bounded_context_id": entry.bounded_context_id,
                "user_story_id": entry.user_story_id,
                "ui_id": entry.wireframe_ui_id,
            },
        )
    # Viewport-intent warnings (research D7+ amendment 2026-05-12). The
    # generated framework.md asks the agent to confirm direction with the
    # user before designing the IA; the warning is the operator-side
    # mirror of that prompt.
    summary = comp.viewport_summary or {}
    known_total = (
        summary.get("mobile", 0) + summary.get("tablet", 0) + summary.get("desktop", 0)
    )
    if known_total > 0:
        if comp.dominant_viewport is not None:
            ctx.warn(
                "frontend_viewport_dominant",
                f"{comp.dominant_viewport.title()}-class wireframes dominate "
                f"({summary.get(comp.dominant_viewport, 0)}/{known_total}); the agent "
                "will ask the user whether to design the whole IA "
                f"{comp.dominant_viewport}-first.",
                {"dominant": comp.dominant_viewport, **summary},
            )
        else:
            ctx.warn(
                "frontend_viewport_mixed",
                "No single viewport class covers ≥70% of bound wireframes; the agent "
                "must ask the user which viewport drives the IA.",
                {**summary},
            )


def render_framework_md(
    env: Environment,
    comp: FrontendCompositionProjection,
    *,
    generated_at: str,
) -> str:
    """Return the rendered ``specs/frontend/framework.md`` text."""
    template = env.get_template("frontend-framework.md.j2")
    return template.render(
        framework=comp.framework,
        conventions=comp.framework_conventions,
        generated_at=generated_at,
        viewport_summary=comp.viewport_summary,
        dominant_viewport=comp.dominant_viewport,
    )


def render_menu_md(
    env: Environment,
    comp: FrontendCompositionProjection,
    *,
    generated_at: str,
) -> str:
    """Return the rendered ``specs/frontend/menu-structure.md`` text.

    This file is *not* a menu structure — it is the agent-facing
    inventory + guidance described in research D7 (revised). The
    template renders ``comp.menu`` as a flat list of UI hints, ordered
    by UI-flow position with entry-point / unreferenced markers, plus
    prose telling the agent how to design the IA from the wider
    event-modeling flow.
    """
    template = env.get_template("frontend-menu.md.j2")
    return template.render(
        hints=comp.menu,
        generated_at=generated_at,
    )


def render_ui_flow_md(
    env: Environment,
    comp: FrontendCompositionProjection,
    *,
    generated_at: str,
) -> str:
    """Return the rendered ``specs/frontend/ui-flow.md`` text."""
    template = env.get_template("frontend-ui-flow.md.j2")
    return template.render(
        ui_flow=comp.ui_flow,
        unreferenced_uis=comp.unreferenced_uis,
        generated_at=generated_at,
        bc_name_by_id=_bc_name_lookup(comp),
    )


def _frontend_dir():
    """``specs/frontend/`` under the current ``paths.SPECS_DIR``.

    Sandboxed via :func:`paths.assert_under_specs`.
    """
    target = paths_mod.SPECS_DIR / "frontend"
    return paths_mod.assert_under_specs(target)


def render_to_disk(
    ctx,
    env: Environment,
    comp: FrontendCompositionProjection,
    *,
    generated_at: str,
    overwrite: bool,
    cross_bc_edge_count: int,
) -> list[ArtifactFileInfo]:
    """Render all three files to ``specs/frontend/`` via atomic-write.

    Honours ``overwrite``: existing files are reported as skipped when
    ``overwrite=False``. Emits the four amendment warnings via ``ctx``.
    """
    _emit_warnings(ctx, comp, cross_bc_edge_count=cross_bc_edge_count)
    target_dir = _frontend_dir()
    target_dir.mkdir(parents=True, exist_ok=True)

    out: list[ArtifactFileInfo] = []
    plan = [
        ("frontend_framework", "framework.md", render_framework_md(env, comp, generated_at=generated_at)),
        ("frontend_menu", "menu-structure.md", render_menu_md(env, comp, generated_at=generated_at)),
        ("frontend_ui_flow", "ui-flow.md", render_ui_flow_md(env, comp, generated_at=generated_at)),
    ]
    for kind, filename, text in plan:
        target = target_dir / filename
        wrote = paths_mod.atomic_write_text(
            target, text, overwrite=overwrite or not target.exists()
        )
        rel = str(target.relative_to(paths_mod.BASE_DIR))
        if not wrote:
            ctx.record_skipped(
                SkippedItem(
                    kind="artifact_file",
                    existing_path=rel,
                    reason="already_exists",
                )
            )
            continue
        info = ArtifactFileInfo(kind=kind, path=rel)
        ctx.record_created(info)
        out.append(info)
    return out
