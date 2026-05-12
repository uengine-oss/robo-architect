"""Render ``domain-terms.md`` from a Bounded Context projection."""
from __future__ import annotations

from typing import Any, Optional

from jinja2 import Environment

from api.features.ddd_spec import llm_assist, paths as paths_mod
from api.features.ddd_spec.projection import BoundedContextProjection
from api.features.ddd_spec.schemas import (
    ArtifactFileInfo,
    GenerateBoundedContextRequest,
)


def _term(
    *,
    name: str,
    definition: str,
    business_context: str,
    related_terms: list[str],
    aliases_to_avoid_mode: str,
    aliases_to_avoid: list[str],
    aliases_to_avoid_suggested: bool = False,
) -> dict[str, Any]:
    return {
        "name": name,
        "definition": definition,
        "business_context": business_context,
        "related_terms": related_terms,
        "aliases_to_avoid_mode": aliases_to_avoid_mode,
        "aliases_to_avoid": aliases_to_avoid,
        "aliases_to_avoid_suggested": aliases_to_avoid_suggested,
    }


def _build_terms(
    ctx, bc: BoundedContextProjection, req: GenerateBoundedContextRequest
) -> list[dict[str, Any]]:
    terms: list[dict[str, Any]] = []
    context_str = f"Bounded Context: {bc.name}. {bc.description or ''}"
    aliases_unavailable_warned = False

    def _aliases(term_name: str) -> tuple[str, list[str], bool]:
        nonlocal aliases_unavailable_warned
        if req.aliases_to_avoid == "omit":
            return "omit", [], False
        suggestions, ok = llm_assist.suggest_aliases_to_avoid(term_name, context_str)
        if ok:
            return "suggest", suggestions, True
        if not aliases_unavailable_warned:
            ctx.warn(
                "aliases_to_avoid_unavailable",
                "'aliases_to_avoid=suggest' requested but the LLM runtime is unavailable; aliases omitted.",
                {"bounded_context_id": bc.id},
            )
            aliases_unavailable_warned = True
        return "omit", [], False

    for agg in bc.aggregates:
        mode, aliases, suggested = _aliases(agg.name)
        terms.append(
            _term(
                name=agg.name,
                definition=agg.description or f"The {agg.name} aggregate.",
                business_context=f"Transaction consistency boundary in '{bc.name}'.",
                related_terms=[c.name for c in agg.commands] + [e.name for e in agg.events],
                aliases_to_avoid_mode=mode,
                aliases_to_avoid=aliases,
                aliases_to_avoid_suggested=suggested,
            )
        )
        for cmd in agg.commands:
            mode, aliases, suggested = _aliases(cmd.name)
            terms.append(
                _term(
                    name=cmd.name,
                    definition=cmd.description or f"Command on {agg.name}.",
                    business_context=f"Operation invoked by an actor on the {agg.name} aggregate.",
                    related_terms=cmd.events_emitted,
                    aliases_to_avoid_mode=mode,
                    aliases_to_avoid=aliases,
                    aliases_to_avoid_suggested=suggested,
                )
            )
        for evt in agg.events:
            mode, aliases, suggested = _aliases(evt.name)
            terms.append(
                _term(
                    name=evt.name,
                    definition=evt.description or f"Domain event emitted by {agg.name}.",
                    business_context=f"Past-tense fact about {agg.name}; consumed by policies and read models.",
                    related_terms=[agg.name],
                    aliases_to_avoid_mode=mode,
                    aliases_to_avoid=aliases,
                    aliases_to_avoid_suggested=suggested,
                )
            )
        for rm in agg.read_models:
            mode, aliases, suggested = _aliases(rm.name)
            terms.append(
                _term(
                    name=rm.name,
                    definition=rm.description or f"Read model for {agg.name}.",
                    business_context="Query projection consumed by clients.",
                    related_terms=[agg.name],
                    aliases_to_avoid_mode=mode,
                    aliases_to_avoid=aliases,
                    aliases_to_avoid_suggested=suggested,
                )
            )
        for attr in agg.attributes:
            if not attr.name:
                continue
            mode, aliases, suggested = _aliases(attr.name)
            terms.append(
                _term(
                    name=attr.name,
                    definition=attr.description or f"`{attr.type}` field of {agg.name}.",
                    business_context=f"Property of {agg.name}; {attr.mutability}.",
                    related_terms=[agg.name],
                    aliases_to_avoid_mode=mode,
                    aliases_to_avoid=aliases,
                    aliases_to_avoid_suggested=suggested,
                )
            )
    return terms


def render(
    ctx,
    env: Environment,
    bc: BoundedContextProjection,
    req: GenerateBoundedContextRequest,
    generated_at: str,
) -> Optional[ArtifactFileInfo]:
    template = env.get_template("domain-terms.md.j2")
    terms = _build_terms(ctx, bc, req)
    text = template.render(bc=bc, terms=terms, generated_at=generated_at)
    target = paths_mod.bc_dir(bc.slug) / "domain-terms.md"
    wrote = paths_mod.atomic_write_text(target, text, overwrite=True if req.overwrite or not target.exists() else False)
    if not wrote:
        ctx.record_skipped(_skip_info(target))
        return None
    info = ArtifactFileInfo(
        kind="domain_terms",
        path=str(target.relative_to(paths_mod.BASE_DIR)),
        bounded_context_id=bc.id,
    )
    ctx.record_created(info)
    return info


def _skip_info(target):
    from api.features.ddd_spec.schemas import SkippedItem

    return SkippedItem(
        kind="artifact_file",
        existing_path=str(target.relative_to(paths_mod.BASE_DIR)),
        reason="already_exists",
    )
