"""Top-level renderer for HTML policy documents.

`render_policy_doc(template_id, bcs, project_name=..., use_llm=...)` returns
a self-contained HTML string. It always succeeds: LLM failures degrade to
deterministic fallbacks recorded in `ctx['warnings']` and surfaced as a
warning box in the document.
"""
from __future__ import annotations

import logging
from typing import Any, Optional

from jinja2 import Environment, FileSystemLoader, select_autoescape

from api.features.ddd_spec.projection import BoundedContextProjection
from api.features.prd_generation.html_templates import (
    data_extractor,
    diagram_render,
    llm_sections,
    registry,
)


logger = logging.getLogger(__name__)


def _jinja_env_for_template(template_id: str) -> Environment:
    folder = registry.template_dir(template_id)
    return Environment(
        loader=FileSystemLoader(str(folder)),
        autoescape=select_autoescape(enabled_extensions=("html", "htm", "j2", "xml"), default=False),
        keep_trailing_newline=True,
    )


def _enrich_context_with_diagrams(ctx: dict[str, Any]) -> None:
    actors = ctx.get("actors") or []
    use_cases = ctx.get("use_cases") or []
    processes = ctx.get("processes") or []
    ctx["usecase_diagram_svg"] = diagram_render.render_usecase_diagram(actors, use_cases) or ""
    ctx["process_flowchart_svg"] = diagram_render.render_process_flowchart(processes) or ""


def _enrich_context_with_lookups(ctx: dict[str, Any]) -> None:
    actors = ctx.get("actors") or []
    ctx["actor_name_by_id"] = {a.id: a.name for a in actors}

    # Functions-by-process: a process's wireframe-attached commands link
    # back to function rows via wireframe.attached_to_name → command name.
    processes = ctx.get("processes") or []
    functions = ctx.get("functions") or []
    fn_by_id = {f.id: f for f in functions}
    fns_by_process: dict[str, list] = {}
    seen_per_process: dict[str, set[str]] = {}
    for pr in processes:
        seen_per_process[pr.id] = set()
        for step in pr.steps:
            if step.function_id and step.function_id in fn_by_id:
                if step.function_id not in seen_per_process[pr.id]:
                    fns_by_process.setdefault(pr.id, []).append(fn_by_id[step.function_id])
                    seen_per_process[pr.id].add(step.function_id)
    ctx["functions_by_process"] = fns_by_process


def render_policy_doc(
    template_id: str,
    bcs: list[BoundedContextProjection],
    *,
    project_name: str = "",
    use_llm: bool = True,
) -> str:
    """Render the HTML policy document for `template_id`.

    Args:
        template_id: a folder name under `html_templates/templates/`.
        bcs: pre-loaded BC projections (typically from
            `api.features.ddd_spec.repository.load_all_bounded_contexts`).
        project_name: shown in the document title and eyebrow.
        use_llm: when False, skips all LLM section runners (useful for tests).

    Raises:
        TemplateNotFoundError: when `template_id` has no folder/manifest.
        TemplateManifestError: when the manifest fails validation.
    """
    manifest = registry.load(template_id)
    env = _jinja_env_for_template(template_id)

    ctx = data_extractor.build_base_context(
        bcs, manifest=manifest, project_name=project_name
    )

    if use_llm:
        for section in manifest.sections:
            if section.kind == "derived":
                continue
            llm_sections.run_section(
                section=section,
                manifest=manifest,
                template_dir=registry.template_dir(template_id),
                ctx=ctx,
            )

    _enrich_context_with_diagrams(ctx)
    _enrich_context_with_lookups(ctx)

    template = env.get_template(manifest.master_template)
    return template.render(**ctx)


def render_policy_doc_from_neo4j(
    template_id: str,
    *,
    project_name: str = "",
    use_llm: bool = True,
) -> str:
    """Convenience wrapper that loads BC projections via the DDD repository.

    Catches Neo4j connection errors by re-raising; callers map them to
    HTTP 503 responses.
    """
    from api.features.ddd_spec.repository import load_all_bounded_contexts

    bcs = load_all_bounded_contexts()
    return render_policy_doc(
        template_id,
        bcs,
        project_name=project_name,
        use_llm=use_llm,
    )
