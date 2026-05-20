"""In-process helper for embedding DDD-spec artifacts into other features
(notably the PRD-generation ZIP / Claude Code project-setup flows).

The public entry point :func:`build_artifacts_to_basedir` runs the full
``ddd_spec`` pipeline against a caller-supplied base directory (rather than
the repo's ``specs/``), then returns the list of files produced.

Internally we re-bind the module-level path constants for the duration of
the call. A re-entrant lock serializes concurrent callers so the swap is
safe at request-level concurrency — this matches the existing
``ddd_spec_lock`` posture (a single tenant generation lock).
"""
from __future__ import annotations

import contextlib
import os
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator, Optional

from api.features.ddd_spec import paths as paths_mod
from api.features.ddd_spec import service
from api.features.ddd_spec.schemas import (
    ArtifactFileInfo,
    GenerateAllRequest,
    GenerateBoundedContextRequest,
    GenerateContextMapRequest,
)

_REBIND_LOCK = threading.Lock()


@contextlib.contextmanager
def _rebind_paths(base_dir: Path) -> Iterator[None]:
    """Temporarily swap ``paths.BASE_DIR`` / ``SPECS_DIR`` / ``BC_ROOT`` /
    ``LOCK_PATH`` so the renderers write under ``base_dir`` instead of the
    repo's ``specs/``.

    Serialized by ``_REBIND_LOCK`` because the module constants are
    process-wide. Each call still acquires the disk-level ``flock`` inside
    the renderers themselves.
    """
    with _REBIND_LOCK:
        snapshot = (
            paths_mod.BASE_DIR,
            paths_mod.SPECS_DIR,
            paths_mod.BC_ROOT,
            paths_mod.LOCK_PATH,
        )
        try:
            # The renderers compare `target.relative_to(paths_mod.BASE_DIR)`
            # after the writer has already passed `target` through
            # `os.path.realpath`. On macOS, `/var/folders/...` is a symlink
            # to `/private/var/folders/...`, so a non-realpath'd BASE_DIR
            # breaks `relative_to`. Match the production `BASE_DIR =
            # Path(__file__).resolve().parents[3]` invariant by realpathing
            # the rebound base too.
            base_dir = Path(os.path.realpath(str(base_dir)))
            paths_mod.BASE_DIR = base_dir
            paths_mod.SPECS_DIR = base_dir / "specs"
            paths_mod.BC_ROOT = base_dir / "specs" / "bounded-contexts"
            paths_mod.LOCK_PATH = paths_mod.BC_ROOT / ".ddd-spec.lock"
            paths_mod.BC_ROOT.mkdir(parents=True, exist_ok=True)
            yield
        finally:
            (
                paths_mod.BASE_DIR,
                paths_mod.SPECS_DIR,
                paths_mod.BC_ROOT,
                paths_mod.LOCK_PATH,
            ) = snapshot


@dataclass
class DddArtifactsBuildResult:
    """Files created by :func:`build_artifacts_to_basedir`."""

    files: list[ArtifactFileInfo]
    warnings_count: int


def build_artifacts_to_basedir(
    base_dir: Path,
    *,
    overwrite: bool = True,
    smooth_ears: bool = False,
    render_svg: bool = True,
    aliases_to_avoid: str = "omit",
    infer_patterns_with_llm: bool = False,
) -> DddArtifactsBuildResult:
    """Project every BC + the context map under ``base_dir/specs/``.

    The defaults keep external services out of the loop:
    ``smooth_ears=False`` and ``aliases_to_avoid="omit"`` skip the LLM,
    while ``render_svg=True`` is now safe to leave on because the SVG
    renderer runs locally from the scene graph (no open-pencil call) —
    see :func:`api.features.ddd_spec.wireframe_render.render_svg_to_file`.
    """
    from api.features.ddd_spec import repository

    files: list[ArtifactFileInfo] = []
    warnings_total = 0

    with _rebind_paths(base_dir):
        bcs = repository.load_all_bounded_contexts()
        if not bcs:
            return DddArtifactsBuildResult(files=[], warnings_count=0)

        # Per-BC artifacts.
        for bc in bcs:
            if not bc.aggregates and not bc.user_stories:
                continue
            try:
                bc_result = service.generate_bounded_context(
                    GenerateBoundedContextRequest(
                        bounded_context_id=bc.id,
                        overwrite=overwrite,
                        aliases_to_avoid=aliases_to_avoid,  # type: ignore[arg-type]
                        smooth_ears=smooth_ears,
                        render_svg=render_svg,
                    )
                )
            except ValueError:
                continue
            files.extend(bc_result.created)
            warnings_total += len(bc_result.warnings)

        # System-wide context map.
        try:
            cm_result = service.generate_context_map(
                GenerateContextMapRequest(
                    overwrite=overwrite,
                    infer_patterns_with_llm=infer_patterns_with_llm,
                )
            )
            files.extend(cm_result.created)
            warnings_total += len(cm_result.warnings)
        except ValueError:
            pass

    return DddArtifactsBuildResult(files=files, warnings_count=warnings_total)


def pack_ddd_artifacts_to_zip(
    zf,
    *,
    overwrite: bool = True,
    smooth_ears: bool = False,
    render_svg: bool = True,
    aliases_to_avoid: str = "omit",
) -> list[str]:
    """Render the DDD-for-SDD artifact set into the open ``zipfile.ZipFile``.

    Returns the list of arcnames written. Files are stored with paths
    relative to the temp base dir, i.e. exactly the same layout the user
    sees in ``specs/`` on disk (``specs/bounded-contexts/...``,
    ``specs/context-map.md``).
    """
    import tempfile

    written: list[str] = []
    with tempfile.TemporaryDirectory(prefix="ddd-pack-") as tmp:
        base = Path(tmp)
        build_artifacts_to_basedir(
            base,
            overwrite=overwrite,
            smooth_ears=smooth_ears,
            render_svg=render_svg,
            aliases_to_avoid=aliases_to_avoid,
        )
        for path in (base / "specs").rglob("*"):
            if not path.is_file():
                continue
            if path.name == ".ddd-spec.lock":
                continue
            arcname = str(path.relative_to(base))
            zf.write(path, arcname)
            written.append(arcname)
    return written


def extract_ddd_artifacts_to_dir(
    target_project_dir: Path,
    *,
    overwrite: bool = True,
    smooth_ears: bool = False,
    render_svg: bool = True,
    aliases_to_avoid: str = "omit",
) -> list[str]:
    """Write the DDD-for-SDD artifact set directly into ``target_project_dir``
    under ``specs/``. Returns the list of repo-relative paths written.

    Used by the Claude Code project-setup flow so the user can open the
    extracted project in their IDE and immediately see the artifacts.
    """
    target_project_dir = Path(target_project_dir)
    target_project_dir.mkdir(parents=True, exist_ok=True)
    result = build_artifacts_to_basedir(
        target_project_dir,
        overwrite=overwrite,
        smooth_ears=smooth_ears,
        render_svg=render_svg,
        aliases_to_avoid=aliases_to_avoid,
    )
    return [info.path for info in result.files]


def planned_paths_for_preview(*, include_frontend: bool = False) -> list[str]:
    """Return the list of repo-relative paths that the ``ddd`` flow would
    produce for the current graph state — for the modal's "Files to Generate"
    preview, without actually writing anything to disk.

    When ``include_frontend=True`` the list also names the three
    ``specs/frontend/*.md`` files produced by US5.
    """
    from api.features.ddd_spec import repository

    bcs = repository.load_all_bounded_contexts()
    if not bcs:
        return []

    paths: list[str] = []
    for bc in bcs:
        bc_root = f"specs/bounded-contexts/{bc.slug}"
        paths.append(f"{bc_root}/domain-terms.md")
        paths.append(f"{bc_root}/bc-{bc.slug}.md")
        for agg in bc.aggregates:
            paths.append(f"{bc_root}/aggregates/aggregate-{agg.slug}.md")
        for ext in bc.external_integrations:
            paths.append(f"{bc_root}/acl-{ext.slug}.md")
        paths.append(f"{bc_root}/requirements.md")
        for us in bc.user_stories:
            for wf in us.wireframes:
                # SVG is best-effort; we still list it in the planned
                # paths so the preview surfaces what the user will get
                # when the renderer succeeds. The scene-graph JSON
                # sidecar is no longer emitted (2026-05-12 amendment).
                paths.append(f"{bc_root}/requirements.assets/{us.id}-{wf.slug}.svg")
    paths.append("specs/context-map.md")
    if include_frontend:
        paths.append("specs/frontend/framework.md")
        paths.append("specs/frontend/menu-structure.md")
        paths.append("specs/frontend/ui-flow.md")
    return paths


def render_frontend_spec_to_zip(
    zf,
    framework: str,
    framework_conventions=None,
    *,
    overwrite: bool = True,
) -> list[str]:
    """Render ``specs/frontend/{framework,menu-structure,ui-flow}.md`` into
    the open ``zipfile.ZipFile`` (US5).

    Args:
        zf: an open :class:`zipfile.ZipFile` in write mode.
        framework: the declared frontend framework value (``vue`` /
            ``react`` / ``svelte`` / …) — echoed verbatim into
            ``framework.md``'s machine-readable preamble.
        framework_conventions: caller-resolved
            :class:`api.features.ddd_spec.projection.FrameworkConventions`
            for ``framework``, or ``None`` if the catalog doesn't recognise
            it (the renderer then emits ``frontend_framework_unsupported``).
            Resolved by the caller so this module stays decoupled from
            ``prd_generation``'s catalog.
        overwrite: forwarded to the disk writer; the zip path uses a
            tempdir so this is always effectively True.

    Returns:
        The list of zip arcnames written (e.g.
        ``["specs/frontend/framework.md", ...]``).

    Side effects:
        Uses the same temp-base-dir rebind as :func:`pack_ddd_artifacts_to_zip`
        so the renderer's ``realpath`` sandbox stays under the temp tree;
        no real ``specs/frontend/`` on the repo is touched.
    """
    import tempfile
    from datetime import datetime, timezone

    from api.features.ddd_spec import frontend_renderer, repository, service

    written: list[str] = []

    # The frontend renderer needs a GenerationContext for warning emission;
    # we use the same context shape the other renderers use, but discard
    # the result (caller doesn't surface warnings through this path).
    ctx = service.GenerationContext()
    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    with tempfile.TemporaryDirectory(prefix="frontend-pack-") as tmp:
        base = Path(tmp)
        with _rebind_paths(base):
            bcs = repository.load_all_bounded_contexts()
            flows = repository.load_cross_bc_flows() if bcs else []
            comp = repository.load_frontend_composition(
                framework, framework_conventions, bcs, flows
            )
            cross_bc_edges = sum(
                1 for f in flows if f.from_bc_id != f.to_bc_id
            )
            env = service._jinja_env()  # reuse the loader pointing at our templates
            frontend_renderer.render_to_disk(
                ctx,
                env,
                comp,
                generated_at=generated_at,
                overwrite=overwrite,
                cross_bc_edge_count=cross_bc_edges,
            )
            for path in (base / "specs" / "frontend").rglob("*"):
                if not path.is_file():
                    continue
                arcname = str(path.relative_to(base))
                zf.write(path, arcname)
                written.append(arcname)
    return written
