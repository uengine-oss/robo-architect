"""Render ``acl-<external-slug>.md`` (Anti-Corruption Layer Spec).

Produced only when a Bounded Context models an external-system
integration. With zero entries, the BC Canvas note suffices.
"""
from __future__ import annotations

from typing import Optional

from jinja2 import Environment

from api.features.ddd_spec import paths as paths_mod
from api.features.ddd_spec.projection import BoundedContextProjection, ExternalIntegrationProjection
from api.features.ddd_spec.schemas import ArtifactFileInfo, SkippedItem


def render(
    ctx,
    env: Environment,
    bc: BoundedContextProjection,
    ext: ExternalIntegrationProjection,
    generated_at: str,
    overwrite: bool,
) -> Optional[ArtifactFileInfo]:
    template = env.get_template("acl-spec.md.j2")
    text = template.render(bc=bc, ext=ext, generated_at=generated_at)
    target = paths_mod.bc_dir(bc.slug) / f"acl-{ext.slug}.md"
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
        kind="acl_spec",
        path=str(target.relative_to(paths_mod.BASE_DIR)),
        bounded_context_id=bc.id,
    )
    ctx.record_created(info)
    return info
