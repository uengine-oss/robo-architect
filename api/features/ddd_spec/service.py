"""Service scaffolding for DDD-spec generation.

This module hosts ``GenerationContext`` (correlation-id + SmartLogger +
warning/created/skipped accumulators) and the public service entry-points
that the router calls.

Phase 2 / T011 lands the scaffold + logging helpers; later tasks (T021,
T026, T029, T032) layer the per-endpoint pipelines on top of it.
"""
from __future__ import annotations

import json
import secrets
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from jinja2 import Environment, FileSystemLoader, StrictUndefined, select_autoescape

from api.platform.observability.smart_logger import SmartLogger

from api.features.ddd_spec import ears as ears_mod
from api.features.ddd_spec import llm_assist
from api.features.ddd_spec import paths as paths_mod
from api.features.ddd_spec import wireframe_render
from api.features.ddd_spec.projection import (
    AggregateProjection,
    BoundedContextProjection,
)
from api.features.ddd_spec.schemas import (
    ArtifactFileInfo,
    GenerateAggregateRequest,
    GenerateAllRequest,
    GenerateBoundedContextRequest,
    GenerateContextMapRequest,
    GenerationResult,
    GenerationWarning,
    SkippedItem,
)


# --- correlation + logging ----------------------------------------------


def _new_correlation_id() -> str:
    return "req-ddd-" + secrets.token_hex(6)


PHASE_EVENTS = {
    "generation_started",
    "bc_subgraph_loaded",
    "wireframe_rendered",
    "templates_rendered",
    "files_written",
    "warning",
    "generation_completed",
    "generation_failed",
}


@dataclass
class GenerationContext:
    """Per-operation context — correlation id, accumulators, log helper."""

    correlation_id: str = field(default_factory=_new_correlation_id)
    created: list[ArtifactFileInfo] = field(default_factory=list)
    skipped: list[SkippedItem] = field(default_factory=list)
    warnings: list[GenerationWarning] = field(default_factory=list)
    started_at: float = field(default_factory=time.perf_counter)

    # --- logging --------------------------------------------------------

    def log(
        self,
        event: str,
        *,
        level: str = "INFO",
        message: Optional[str] = None,
        params: Optional[dict[str, Any]] = None,
    ) -> None:
        full_params = {"correlation_id": self.correlation_id, "event": event}
        if params:
            full_params.update(params)
        SmartLogger.log(
            level,
            message or event,
            category=f"ddd_spec.{event}",
            params=full_params,
        )

    # --- warning helper -------------------------------------------------

    def warn(self, code: str, message: str, target: Optional[dict[str, str]] = None) -> None:
        warning = GenerationWarning(code=code, message=message, target=target or {})
        self.warnings.append(warning)
        self.log("warning", level="WARN", message=message, params={"code": code, **(target or {})})

    # --- record helpers -------------------------------------------------

    def record_created(self, info: ArtifactFileInfo) -> None:
        self.created.append(info)

    def record_skipped(self, item: SkippedItem) -> None:
        self.skipped.append(item)

    # --- finalize -------------------------------------------------------

    def result(self) -> GenerationResult:
        return GenerationResult(
            created=list(self.created),
            skipped=list(self.skipped),
            warnings=list(self.warnings),
            correlation_id=self.correlation_id,
        )


# --- jinja env ----------------------------------------------------------


_TEMPLATE_DIR = Path(__file__).resolve().parent / "templates"


def _jinja_env() -> Environment:
    env = Environment(
        loader=FileSystemLoader(str(_TEMPLATE_DIR)),
        autoescape=select_autoescape(disabled_extensions=("md", "j2"), default=False),
        keep_trailing_newline=True,
        undefined=StrictUndefined,
        trim_blocks=False,
        lstrip_blocks=False,
    )
    return env


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# --- service: generate one Bounded Context ------------------------------


def generate_bounded_context(req: GenerateBoundedContextRequest) -> GenerationResult:
    """T021: project one BC into its DDD-for-SDD artifact folder.

    Returns a ``GenerationResult``. Outcomes:

    - BC not found → ``ValueError("bounded_context_not_found")``.
    - Empty BC (no aggregates AND no user stories) → ``ValueError("empty_bounded_context")``.
    - Lock contended → ``BlockingIOError`` (raised by ``paths.ddd_spec_lock``);
      caller maps to HTTP 409.
    - All other internal errors → propagate.

    On overwrite=False and pre-existing folder, returns a result with the
    skipped folder recorded and ``created`` empty.
    """
    # Lazy import — keeps the heavy renderers off the import path of this
    # module so the router can import GenerationContext cheaply.
    from api.features.ddd_spec import repository
    from api.features.ddd_spec.renderers import (
        aggregate_spec as aggregate_renderer,
        bc_canvas as bc_canvas_renderer,
        domain_terms as domain_terms_renderer,
        acl_spec as acl_spec_renderer,
        requirements_md as requirements_md_renderer,
    )

    ctx = GenerationContext()
    ctx.log(
        "generation_started",
        params={
            "operation": "generate_bounded_context",
            "bounded_context_id": req.bounded_context_id,
            "overwrite": req.overwrite,
            "aliases_to_avoid": req.aliases_to_avoid,
            "smooth_ears": req.smooth_ears,
            "render_svg": req.render_svg,
        },
    )

    bc = repository.load_bounded_context(req.bounded_context_id)
    if bc is None:
        ctx.log("generation_failed", level="ERROR", params={"code": "bounded_context_not_found"})
        raise ValueError("bounded_context_not_found")

    if not bc.aggregates and not bc.user_stories:
        ctx.log("generation_failed", level="ERROR", params={"code": "empty_bounded_context"})
        raise ValueError("empty_bounded_context")

    ctx.log(
        "bc_subgraph_loaded",
        params={
            "bounded_context_id": bc.id,
            "aggregates": len(bc.aggregates),
            "user_stories": len(bc.user_stories),
        },
    )

    target_bc_dir = paths_mod.bc_dir(bc.slug)
    pre_existing = target_bc_dir.exists() and any(target_bc_dir.iterdir())
    if pre_existing and not req.overwrite:
        ctx.record_skipped(
            SkippedItem(
                kind="bounded_context",
                id=bc.id,
                existing_path=str(target_bc_dir.relative_to(paths_mod.BASE_DIR)),
                reason="already_exists",
                message="Folder already exists; pass overwrite=true to regenerate.",
            )
        )
        ctx.log(
            "generation_completed",
            params={"bounded_context_id": bc.id, "outcome": "skipped"},
        )
        return ctx.result()

    smoother = (
        (lambda lines: _safe_smoother(ctx, lines)) if req.smooth_ears else None
    )

    env = _jinja_env()
    generated_at = _now_iso()

    with paths_mod.ddd_spec_lock():
        # Render each file in turn (lock held across the create critical
        # section — research D5). We don't need a staging dir for each
        # individual file because atomic_write_text already uses tempfile +
        # os.replace.

        # domain-terms.md
        domain_terms_renderer.render(ctx, env, bc, req, generated_at)

        # bc-<slug>.md
        bc_canvas_renderer.render(ctx, env, bc, generated_at)

        # aggregates/aggregate-<slug>.md
        for agg in bc.aggregates:
            aggregate_renderer.render(
                ctx, env, bc, agg, generated_at=generated_at, smoother=smoother, overwrite=req.overwrite
            )

        # acl-<slug>.md (only when external integrations modeled — none in graph today)
        if bc.external_integrations:
            for ext in bc.external_integrations:
                acl_spec_renderer.render(ctx, env, bc, ext, generated_at, req.overwrite)
        else:
            ctx.warn(
                "no_external_integrations",
                f"No external-system integrations modeled for '{bc.name}'; no acl-*.md produced.",
                {"bounded_context_id": bc.id},
            )

        # requirements.md (+ scene.json sidecars + best-effort SVGs)
        requirements_md_renderer.render(
            ctx,
            env,
            bc,
            req,
            generated_at=generated_at,
            smoother=smoother,
        )

    ctx.log(
        "generation_completed",
        params={
            "bounded_context_id": bc.id,
            "files_written": len(ctx.created),
            "warnings": len(ctx.warnings),
            "elapsed_ms": int((time.perf_counter() - ctx.started_at) * 1000),
        },
    )
    return ctx.result()


# --- helpers shared across renderers ------------------------------------


def _safe_smoother(ctx: GenerationContext, lines: list[str]) -> list[str]:
    smoothed, ok = llm_assist.smooth_ears(lines)
    if not ok:
        ctx.warn(
            "llm_unavailable",
            "EARS grammar smoothing requested but the LLM runtime is unavailable; deterministic output kept.",
        )
    return smoothed


def jinja_env() -> Environment:
    """Public hook for renderers that need the same configured env."""
    return _jinja_env()


def generate_context_map(req: GenerateContextMapRequest) -> GenerationResult:
    """T026: regenerate ``specs/context-map.md`` from all BCs + cross-BC flows.

    - No BCs in graph → ``ValueError("no_bounded_contexts")``.
    - Lock contended → ``BlockingIOError``.
    """
    from api.features.ddd_spec import repository
    from api.features.ddd_spec.renderers import context_map as context_map_renderer

    ctx = GenerationContext()
    ctx.log(
        "generation_started",
        params={
            "operation": "generate_context_map",
            "overwrite": req.overwrite,
            "infer_patterns_with_llm": req.infer_patterns_with_llm,
        },
    )
    bcs = repository.load_all_bounded_contexts()
    if not bcs:
        ctx.log("generation_failed", level="ERROR", params={"code": "no_bounded_contexts"})
        raise ValueError("no_bounded_contexts")

    flows = repository.load_cross_bc_flows()

    env = _jinja_env()
    generated_at = _now_iso()
    with paths_mod.ddd_spec_lock():
        context_map_renderer.render(
            ctx,
            env,
            bcs,
            flows,
            generated_at=generated_at,
            overwrite=req.overwrite,
            infer_with_llm=req.infer_patterns_with_llm,
        )

    ctx.log(
        "generation_completed",
        params={
            "operation": "generate_context_map",
            "files_written": len(ctx.created),
            "warnings": len(ctx.warnings),
        },
    )
    return ctx.result()


def generate_aggregate(req: GenerateAggregateRequest) -> GenerationResult:
    """T029: refresh just ``aggregates/aggregate-<slug>.md`` for one Aggregate."""
    from api.features.ddd_spec import repository
    from api.features.ddd_spec.renderers import aggregate_spec as aggregate_renderer

    ctx = GenerationContext()
    ctx.log(
        "generation_started",
        params={
            "operation": "generate_aggregate",
            "aggregate_id": req.aggregate_id,
            "overwrite": req.overwrite,
            "smooth_ears": req.smooth_ears,
        },
    )

    pair = repository.load_aggregate(req.aggregate_id)
    if pair is None:
        ctx.log("generation_failed", level="ERROR", params={"code": "aggregate_not_found"})
        raise ValueError("aggregate_not_found")
    bc, agg = pair
    ctx.log(
        "bc_subgraph_loaded",
        params={
            "bounded_context_id": bc.id,
            "aggregate_id": agg.id,
        },
    )

    smoother = (lambda lines: _safe_smoother(ctx, lines)) if req.smooth_ears else None

    env = _jinja_env()
    generated_at = _now_iso()
    with paths_mod.ddd_spec_lock():
        aggregate_renderer.render(
            ctx,
            env,
            bc,
            agg,
            generated_at=generated_at,
            smoother=smoother,
            overwrite=req.overwrite,
        )

    ctx.log(
        "generation_completed",
        params={
            "operation": "generate_aggregate",
            "files_written": len(ctx.created),
            "warnings": len(ctx.warnings),
        },
    )
    return ctx.result()


async def generate_all(req: GenerateAllRequest):
    """T032: SSE generator — regenerate context-map + every BC's folder.

    Yields ``(event_name, payload_dict)`` tuples. ``payload_dict`` is the
    JSON-serializable event body; the router serializes them to SSE frames.
    """
    from api.features.ddd_spec import repository

    ctx = GenerationContext()
    ctx.log(
        "generation_started",
        params={
            "operation": "generate_all",
            "overwrite": req.overwrite,
        },
    )

    yield (
        "phase",
        {"phase": "loading_model", "message": "Loading all Bounded Contexts from Neo4j"},
    )
    try:
        bcs = repository.load_all_bounded_contexts()
    except Exception as e:  # noqa: BLE001
        ctx.log("generation_failed", level="ERROR", params={"error": str(e)})
        yield (
            "error",
            {"error_code": "load_failed", "message": str(e), "correlation_id": ctx.correlation_id},
        )
        return

    if not bcs:
        yield (
            "error",
            {
                "error_code": "no_bounded_contexts",
                "message": "The graph contains no Bounded Contexts",
                "correlation_id": ctx.correlation_id,
            },
        )
        return

    # 1. Context Map.
    yield ("phase", {"phase": "context_map", "message": "Rendering context-map.md"})
    cm_req = GenerateContextMapRequest(
        overwrite=req.overwrite,
        infer_patterns_with_llm=req.infer_patterns_with_llm,
    )
    try:
        cm_result = generate_context_map(cm_req)
        ctx.created.extend(cm_result.created)
        ctx.skipped.extend(cm_result.skipped)
        for w in cm_result.warnings:
            ctx.warnings.append(w)
            yield ("warning", w.model_dump())
    except ValueError as e:
        yield (
            "warning",
            {"code": str(e), "message": "Context map step failed", "target": {}},
        )
    except BlockingIOError:
        yield (
            "error",
            {
                "error_code": "lock_busy",
                "message": "Another DDD-spec generation is in progress.",
                "correlation_id": ctx.correlation_id,
            },
        )
        return

    # 2. Per-BC pipelines.
    yield (
        "phase",
        {"phase": "bounded_contexts", "message": f"Generating {len(bcs)} Bounded Context folders"},
    )
    for idx, bc in enumerate(bcs, start=1):
        yield (
            "bc_started",
            {
                "bounded_context_id": bc.id,
                "bounded_context_name": bc.name,
                "index": idx,
                "total": len(bcs),
            },
        )
        bc_req = GenerateBoundedContextRequest(
            bounded_context_id=bc.id,
            overwrite=req.overwrite,
            aliases_to_avoid=req.aliases_to_avoid,
            smooth_ears=req.smooth_ears,
            render_svg=req.render_svg,
        )
        try:
            bc_result = generate_bounded_context(bc_req)
        except ValueError as e:
            yield (
                "bc_failed",
                {
                    "bounded_context_id": bc.id,
                    "error_code": str(e),
                    "message": f"BC {bc.name} failed: {e}",
                },
            )
            continue
        except BlockingIOError:
            yield (
                "bc_failed",
                {
                    "bounded_context_id": bc.id,
                    "error_code": "lock_busy",
                    "message": "Lock held mid-run; BC skipped",
                },
            )
            continue
        except Exception as e:  # noqa: BLE001
            yield (
                "bc_failed",
                {
                    "bounded_context_id": bc.id,
                    "error_code": "internal_error",
                    "message": str(e),
                },
            )
            continue

        ctx.created.extend(bc_result.created)
        ctx.skipped.extend(bc_result.skipped)
        for w in bc_result.warnings:
            ctx.warnings.append(w)
            yield ("warning", w.model_dump())

        yield (
            "bc_completed",
            {
                "bounded_context_id": bc.id,
                "files": [f.model_dump() for f in bc_result.created],
            },
        )

    ctx.log(
        "generation_completed",
        params={
            "operation": "generate_all",
            "files_written": len(ctx.created),
            "warnings": len(ctx.warnings),
        },
    )
    yield ("complete", ctx.result().model_dump())


__all__ = [
    "GenerationContext",
    "generate_bounded_context",
    "generate_context_map",
    "generate_aggregate",
    "generate_all",
    "jinja_env",
]
