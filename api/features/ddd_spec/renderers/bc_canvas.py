"""Render ``bc-<slug>.md`` (Bounded Context Canvas)."""
from __future__ import annotations

from typing import Optional

from jinja2 import Environment

from api.features.ddd_spec import paths as paths_mod
from api.features.ddd_spec.projection import BoundedContextProjection, CrossBcFlow
from api.features.ddd_spec.schemas import ArtifactFileInfo, SkippedItem


def _decorate_flow(flow: CrossBcFlow) -> dict:
    pattern = flow.recorded_pattern or "Customer-Supplier"
    pattern_display = pattern + ("" if flow.recorded_pattern else " *(inferred — confirm)*")
    return {
        "from_bc_name": flow.from_bc_name,
        "to_bc_name": flow.to_bc_name,
        "channel": flow.channel,
        "message": flow.message,
        "pattern_display": pattern_display,
    }


def render(
    ctx,
    env: Environment,
    bc: BoundedContextProjection,
    generated_at: str,
    *,
    overwrite: bool = True,
) -> Optional[ArtifactFileInfo]:
    if bc.purpose is None:
        ctx.warn(
            "bc_purpose_missing",
            f"Bounded Context '{bc.name}' has no purpose statement modeled.",
            {"bounded_context_id": bc.id},
        )
    if bc.strategic is None:
        ctx.warn(
            "bc_not_classified",
            f"Bounded Context '{bc.name}' has no strategic classification modeled.",
            {"bounded_context_id": bc.id},
        )

    bc_view = bc.model_copy(
        update={
            "inbound_flows": [_decorate_flow(f) for f in bc.inbound_flows],  # type: ignore[arg-type]
            "outbound_flows": [_decorate_flow(f) for f in bc.outbound_flows],  # type: ignore[arg-type]
        }
    )

    template = env.get_template("bc-canvas.md.j2")
    text = template.render(bc=bc_view, generated_at=generated_at)
    target = paths_mod.bc_dir(bc.slug) / f"bc-{bc.slug}.md"
    wrote = paths_mod.atomic_write_text(target, text, overwrite=overwrite or not target.exists())
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
        kind="bc_canvas",
        path=str(target.relative_to(paths_mod.BASE_DIR)),
        bounded_context_id=bc.id,
    )
    ctx.record_created(info)
    return info
