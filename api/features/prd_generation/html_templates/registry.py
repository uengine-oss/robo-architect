"""Filesystem discovery + loading of HTML policy-document templates.

Templates live under `api/features/prd_generation/html_templates/templates/<id>/`.
Each is auto-registered by directory name; the `manifest.yaml` inside drives
the section pipeline. Adding a new template = new folder, no code changes.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml
from pydantic import ValidationError

from api.features.prd_generation.html_templates.schema import TemplateManifest


TEMPLATES_ROOT = Path(__file__).parent / "templates"


class TemplateNotFoundError(LookupError):
    """Raised when the requested template id has no folder under TEMPLATES_ROOT."""


class TemplateManifestError(ValueError):
    """Raised when a manifest.yaml fails schema validation."""


def list_templates() -> list[str]:
    """Return all registered template ids (folder names with a manifest.yaml)."""
    if not TEMPLATES_ROOT.exists():
        return []
    out: list[str] = []
    for child in sorted(TEMPLATES_ROOT.iterdir()):
        if child.is_dir() and (child / "manifest.yaml").is_file():
            out.append(child.name)
    return out


def template_dir(template_id: str) -> Path:
    """Resolve a template id to its directory or raise `TemplateNotFoundError`."""
    folder = TEMPLATES_ROOT / template_id
    if not folder.is_dir() or not (folder / "manifest.yaml").is_file():
        raise TemplateNotFoundError(
            f"HTML template '{template_id}' not found under {TEMPLATES_ROOT}"
        )
    return folder


@lru_cache(maxsize=8)
def load(template_id: str) -> TemplateManifest:
    """Load and validate a template manifest. Cached; bypass cache via `load.cache_clear()`."""
    folder = template_dir(template_id)
    raw = yaml.safe_load((folder / "manifest.yaml").read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise TemplateManifestError(
            f"manifest.yaml for '{template_id}' did not parse to a mapping"
        )
    try:
        manifest = TemplateManifest(**raw)
    except ValidationError as exc:
        raise TemplateManifestError(
            f"manifest.yaml for '{template_id}' failed validation: {exc}"
        ) from exc
    if manifest.id != template_id:
        raise TemplateManifestError(
            f"manifest.yaml id '{manifest.id}' does not match folder name '{template_id}'"
        )
    return manifest
