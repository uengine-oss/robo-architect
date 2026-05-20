"""Render ``aggregates/aggregate-<slug>.md`` (Aggregate Design Spec)."""
from __future__ import annotations

from typing import Callable, Optional

from jinja2 import Environment

from api.features.ddd_spec import ears as ears_mod
from api.features.ddd_spec import paths as paths_mod
from api.features.ddd_spec.projection import AggregateProjection, BoundedContextProjection
from api.features.ddd_spec.schemas import ArtifactFileInfo, SkippedItem


def render(
    ctx,
    env: Environment,
    bc: BoundedContextProjection,
    agg: AggregateProjection,
    *,
    generated_at: str,
    smoother: Optional[Callable[[list[str]], list[str]]] = None,
    overwrite: bool = True,
) -> Optional[ArtifactFileInfo]:
    open_decisions: list[str] = []
    commands_for_invariants = []
    for c in agg.commands:
        if not c.gwt:
            open_decisions.append(f"Command `{c.name}` has no GWT modeled — confirm its preconditions / postconditions.")
            ctx.warn(
                "command_missing_gwt",
                f"Command '{c.name}' has no Given/When/Then modeled.",
                {"aggregate_id": agg.id, "command_id": c.id},
            )
        else:
            commands_for_invariants.extend(c.gwt)

    invariant_lines = ears_mod.aggregate_invariant_lines(
        agg.name,
        unconditional=agg.invariants,
        commands_gwt=commands_for_invariants,
        smoother=smoother,
    )

    template = env.get_template("aggregate-spec.md.j2")
    text = template.render(
        bc=bc,
        agg=agg,
        invariant_lines=invariant_lines,
        open_decisions=open_decisions,
        generated_at=generated_at,
    )
    target = paths_mod.aggregates_dir(bc.slug) / f"aggregate-{agg.slug}.md"
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
        kind="aggregate_spec",
        path=str(target.relative_to(paths_mod.BASE_DIR)),
        bounded_context_id=bc.id,
        aggregate_id=agg.id,
    )
    ctx.record_created(info)
    return info
