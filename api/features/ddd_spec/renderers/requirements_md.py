"""Render ``requirements.md`` + best-effort ``requirements.assets/*.svg``.

Scene-graph JSON sidecars are no longer emitted (2026-05-12 amendment).
The element tree inside ``requirements.md`` is the structural reference
for downstream code; the SVG is the visual reference. Anything that
needs exact numeric values reads them from the SVG, not from a separate
``.scene.json`` file.
"""
from __future__ import annotations

from typing import Callable, Optional

from jinja2 import Environment

from api.features.ddd_spec import ears as ears_mod
from api.features.ddd_spec import paths as paths_mod
from api.features.ddd_spec import wireframe_render
from api.features.ddd_spec.projection import (
    BoundedContextProjection,
    UserStoryProjection,
)
from api.features.ddd_spec.schemas import (
    ArtifactFileInfo,
    GenerateBoundedContextRequest,
    SkippedItem,
)


_PRIORITY_RANK = {"P1": 1, "P2": 2, "P3": 3, "P4": 4, "P5": 5}


def _grouped_stories(bc: BoundedContextProjection) -> list[dict]:
    """Group user stories by aggregate in priority/insertion order."""
    by_agg: dict[str, list[UserStoryProjection]] = {}
    insertion: list[str] = []
    for s in bc.user_stories:
        key = s.aggregate_id or "(unassigned)"
        if key not in by_agg:
            by_agg[key] = []
            insertion.append(key)
        by_agg[key].append(s)

    groups: list[dict] = []
    # Emit aggregates in their canonical (alphabetical) order, then any
    # leftover IDs (e.g. unassigned).
    agg_names = {a.id: a.name for a in bc.aggregates}
    ordered_keys = [a.id for a in bc.aggregates if a.id in by_agg]
    for key in insertion:
        if key not in ordered_keys:
            ordered_keys.append(key)

    for key in ordered_keys:
        stories = by_agg.get(key, [])
        stories.sort(
            key=lambda s: (
                _PRIORITY_RANK.get(s.priority or "", 99),
                bc.user_stories.index(s),
            )
        )
        groups.append(
            {
                "aggregate_id": key,
                "aggregate_name": agg_names.get(key, key),
                "stories": stories,
            }
        )
    return groups


def _render_wireframes(
    ctx,
    bc: BoundedContextProjection,
    story: UserStoryProjection,
    req: GenerateBoundedContextRequest,
    referenced_assets: set,
) -> list[dict]:
    out: list[dict] = []
    if not story.wireframes:
        return out
    assets = paths_mod.assets_dir(bc.slug)
    for wf in story.wireframes:
        elem_tree = wireframe_render.extract_element_tree(wf.scene_graph_json)
        svg_path = assets / f"{story.id}-{wf.slug}.svg"
        svg_rel = svg_path.relative_to(paths_mod.bc_dir(bc.slug))

        svg_written = False
        if req.render_svg and wf.scene_graph_json:
            svg_written, err = wireframe_render.render_svg_to_file(
                target=svg_path,
                scene_graph_json=wf.scene_graph_json,
                overwrite=req.overwrite or not svg_path.exists(),
            )
            if svg_written:
                referenced_assets.add(svg_path)
                ctx.record_created(
                    ArtifactFileInfo(
                        kind="svg",
                        path=str(svg_path.relative_to(paths_mod.BASE_DIR)),
                        bounded_context_id=bc.id,
                    )
                )
            elif err is not None:
                ctx.warn(
                    err,
                    f"SVG render for UI '{wf.name}' failed; textual artifacts still produced.",
                    {"bounded_context_id": bc.id, "ui_id": wf.ui_id},
                )

        ctx.log(
            "wireframe_rendered",
            params={
                "bounded_context_id": bc.id,
                "user_story_id": story.id,
                "ui_id": wf.ui_id,
                "svg_path": str(svg_path.relative_to(paths_mod.BASE_DIR)) if svg_written else None,
            },
        )

        out.append(
            {
                "name": wf.name,
                "element_tree": elem_tree,
                # SVG is surfaced only when the renderer produced one;
                # otherwise the element tree above is the only signal.
                "svg_path": str(svg_rel) if svg_written else None,
            }
        )
    return out


def render(
    ctx,
    env: Environment,
    bc: BoundedContextProjection,
    req: GenerateBoundedContextRequest,
    *,
    generated_at: str,
    smoother: Optional[Callable[[list[str]], list[str]]] = None,
) -> Optional[ArtifactFileInfo]:
    groups_raw = _grouped_stories(bc)

    referenced_assets: set = set()
    groups_view: list[dict] = []
    for g in groups_raw:
        stories_view: list[dict] = []
        for s in g["stories"]:
            ears_lines = ears_mod.story_acceptance_lines(
                acceptance_criteria=s.acceptance_criteria, smoother=smoother
            )
            wireframes = _render_wireframes(ctx, bc, s, req, referenced_assets)
            stories_view.append(
                {
                    "title": s.title,
                    "priority": s.priority,
                    "narrative": s.narrative,
                    "ears_lines": ears_lines,
                    "wireframes": wireframes,
                }
            )
        groups_view.append(
            {"aggregate_name": g["aggregate_name"], "stories": stories_view}
        )

    template = env.get_template("requirements.md.j2")
    text = template.render(bc=bc, story_groups=groups_view, generated_at=generated_at)
    target = paths_mod.bc_dir(bc.slug) / "requirements.md"
    wrote = paths_mod.atomic_write_text(target, text, overwrite=req.overwrite or not target.exists())
    if not wrote:
        ctx.record_skipped(
            SkippedItem(
                kind="artifact_file",
                existing_path=str(target.relative_to(paths_mod.BASE_DIR)),
                reason="already_exists",
            )
        )
        return None
    info = ArtifactFileInfo(
        kind="requirements",
        path=str(target.relative_to(paths_mod.BASE_DIR)),
        bounded_context_id=bc.id,
    )
    ctx.record_created(info)

    # Stale-asset detection — only meaningful when we just rewrote requirements.
    if req.overwrite:
        for stale in paths_mod.detect_stale_assets(bc.slug, referenced_assets):
            ctx.warn(
                "stale_asset",
                f"Asset {stale.name} is no longer referenced by requirements.md (kept on disk).",
                {"bounded_context_id": bc.id, "path": str(stale.relative_to(paths_mod.BASE_DIR))},
            )

    return info
