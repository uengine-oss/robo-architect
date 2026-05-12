"""Render system-level ``specs/context-map.md``."""
from __future__ import annotations

import re
from typing import Optional

from jinja2 import Environment

from api.features.ddd_spec import llm_assist, paths as paths_mod
from api.features.ddd_spec.projection import BoundedContextProjection, CrossBcFlow
from api.features.ddd_spec.schemas import ArtifactFileInfo, SkippedItem


def _safe_node_id(slug: str) -> str:
    """Mermaid node ids must be identifier-safe; replace hyphens."""
    return "bc_" + re.sub(r"[^0-9a-zA-Z_]", "_", slug)


def _fanout_count(flows: list[CrossBcFlow]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for f in flows:
        counts[f.from_bc_id] = counts.get(f.from_bc_id, 0) + 1
    return counts


def _infer_pattern_heuristic(
    flow: CrossBcFlow,
    *,
    fanout: dict[str, int],
    downstream_has_acl: bool,
    flagged_external: bool,
) -> str:
    """Per research D6 — best-guess relationship pattern."""
    if flagged_external:
        return "Anti-Corruption Layer"
    if fanout.get(flow.from_bc_id, 0) >= 3:
        return "Open Host Service + Published Language"
    if downstream_has_acl:
        return "Conformist + Anti-Corruption Layer"
    return "Customer-Supplier"


def _spec_file_link(
    flow: CrossBcFlow,
    bcs_by_id: dict[str, BoundedContextProjection],
    pattern: str,
) -> str:
    downstream = bcs_by_id.get(flow.to_bc_id)
    if downstream is None:
        return "bounded-contexts/(unknown)"
    if "Anti-Corruption Layer" in pattern and downstream.external_integrations:
        ext = downstream.external_integrations[0]
        return f"bounded-contexts/{downstream.slug}/acl-{ext.slug}.md"
    return f"bounded-contexts/{downstream.slug}/bc-{downstream.slug}.md"


def build_edges(
    ctx,
    bcs: list[BoundedContextProjection],
    flows: list[CrossBcFlow],
    *,
    infer_with_llm: bool = False,
) -> list[dict]:
    """Compute per-edge view-model dicts for the Jinja template."""
    bcs_by_id = {bc.id: bc for bc in bcs}
    fanout = _fanout_count(flows)
    edges: list[dict] = []
    for flow in flows:
        downstream = bcs_by_id.get(flow.to_bc_id)
        downstream_has_acl = bool(downstream and downstream.external_integrations)
        flagged_external = False  # No "external" flag in the schema today.

        pattern_inferred = flow.recorded_pattern is None
        pattern = flow.recorded_pattern or _infer_pattern_heuristic(
            flow,
            fanout=fanout,
            downstream_has_acl=downstream_has_acl,
            flagged_external=flagged_external,
        )

        if pattern_inferred and infer_with_llm:
            upstream = bcs_by_id.get(flow.from_bc_id)
            llm_pat = llm_assist.infer_relationship_pattern(
                upstream_bc=flow.from_bc_name,
                downstream_bc=flow.to_bc_name,
                upstream_description=upstream.description if upstream else None,
                downstream_description=downstream.description if downstream else None,
                heuristic_pattern=pattern,
            )
            if llm_pat:
                pattern = llm_pat

        if pattern_inferred:
            ctx.warn(
                "relationship_pattern_inferred",
                f"Edge {flow.from_bc_name} → {flow.to_bc_name}: pattern not modeled; inferred {pattern}",
                {"from_bc_id": flow.from_bc_id, "to_bc_id": flow.to_bc_id},
            )

        spec_file = _spec_file_link(flow, bcs_by_id, pattern)
        edges.append(
            {
                "from_bc_name": flow.from_bc_name,
                "to_bc_name": flow.to_bc_name,
                "from_node_id": _safe_node_id(
                    (bcs_by_id.get(flow.from_bc_id) and bcs_by_id[flow.from_bc_id].slug) or flow.from_bc_id
                ),
                "to_node_id": _safe_node_id(
                    (bcs_by_id.get(flow.to_bc_id) and bcs_by_id[flow.to_bc_id].slug) or flow.to_bc_id
                ),
                "label": flow.message or "depends on",
                "pattern": pattern,
                "pattern_inferred": pattern_inferred,
                "direction": "upstream → downstream",
                "translation": (
                    "Anti-corruption mapping at the consumer side"
                    if "Anti-Corruption Layer" in pattern
                    else "None"
                ),
                "reason": flow.message or "Event-driven coupling",
                "spec_file": spec_file,
            }
        )
    return edges


def render(
    ctx,
    env: Environment,
    bcs: list[BoundedContextProjection],
    flows: list[CrossBcFlow],
    *,
    generated_at: str,
    overwrite: bool,
    infer_with_llm: bool = False,
) -> Optional[ArtifactFileInfo]:
    bc_views = [
        {"name": bc.name, "slug": bc.slug, "node_id": _safe_node_id(bc.slug)}
        for bc in bcs
    ]
    edges = build_edges(ctx, bcs, flows, infer_with_llm=infer_with_llm)
    template = env.get_template("context-map.md.j2")
    text = template.render(bcs=bc_views, edges=edges, generated_at=generated_at)
    target = paths_mod.context_map_path()
    wrote = paths_mod.atomic_write_text(target, text, overwrite=overwrite or not target.exists())
    if not wrote:
        ctx.record_skipped(
            SkippedItem(
                kind="context_map",
                existing_path=str(target.relative_to(paths_mod.BASE_DIR)),
                reason="already_exists",
            )
        )
        return None
    info = ArtifactFileInfo(
        kind="context_map",
        path=str(target.relative_to(paths_mod.BASE_DIR)),
    )
    ctx.record_created(info)
    return info
