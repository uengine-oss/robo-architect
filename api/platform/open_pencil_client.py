"""
HTTP client for the open-pencil wireframe service.

The service (Bun) loads a .fig component library and exposes:
  GET  /components        → component catalog JSON
  GET  /components?format=prompt → human-readable catalog for LLM injection
  POST /render            → compose wireframe from component instances → SerializedSceneGraph
  GET  /health            → health check
"""
from __future__ import annotations

import json
import os
from functools import lru_cache
from typing import Any

import httpx

from api.platform.observability.smart_logger import SmartLogger

WIREFRAME_SERVICE_URL = os.getenv("WIREFRAME_SERVICE_URL", "http://localhost:7610")
_TIMEOUT = 30.0


def _base_url() -> str:
    return WIREFRAME_SERVICE_URL.rstrip("/")


# ------------------------------------------------------------------ #
#  Health                                                              #
# ------------------------------------------------------------------ #

def health_check() -> dict[str, Any]:
    """Check if the wireframe service is running."""
    try:
        resp = httpx.get(f"{_base_url()}/health", timeout=5.0)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        return {"status": "unavailable", "error": str(e)}


def is_available() -> bool:
    """Return True if the wireframe service is reachable and healthy."""
    try:
        info = health_check()
        return info.get("status") == "ok"
    except Exception:
        return False


# ------------------------------------------------------------------ #
#  Component catalog                                                   #
# ------------------------------------------------------------------ #

_catalog_cache: str | None = None
_catalog_json_cache: dict | None = None


def get_component_catalog_for_prompt() -> str:
    """
    Fetch the component catalog formatted as a human-readable prompt.
    Result is cached in-process for the lifetime of the service.
    """
    global _catalog_cache
    if _catalog_cache is not None:
        return _catalog_cache
    try:
        resp = httpx.get(
            f"{_base_url()}/components",
            params={"format": "prompt"},
            timeout=_TIMEOUT,
        )
        resp.raise_for_status()
        _catalog_cache = resp.text
        return _catalog_cache
    except Exception as e:
        SmartLogger.log(
            "WARN",
            f"Failed to fetch component catalog from wireframe service: {e}",
            category="open_pencil.catalog.error",
        )
        return ""


def get_component_catalog_json() -> dict:
    """Fetch the full component catalog as JSON."""
    global _catalog_json_cache
    if _catalog_json_cache is not None:
        return _catalog_json_cache
    try:
        resp = httpx.get(f"{_base_url()}/components", timeout=_TIMEOUT)
        resp.raise_for_status()
        _catalog_json_cache = resp.json()
        return _catalog_json_cache
    except Exception as e:
        SmartLogger.log(
            "WARN",
            f"Failed to fetch component catalog JSON: {e}",
            category="open_pencil.catalog.error",
        )
        return {"count": 0, "components": []}


def invalidate_catalog_cache() -> None:
    """Clear the cached catalog (e.g. after the .fig library changes)."""
    global _catalog_cache, _catalog_json_cache
    _catalog_cache = None
    _catalog_json_cache = None


# ------------------------------------------------------------------ #
#  Render                                                              #
# ------------------------------------------------------------------ #

def render_wireframe(
    *,
    components: list[dict[str, Any]] | None = None,
    jsx: str | None = None,
    name: str = "Wireframe",
    width: int = 375,
    height: int = 812,
) -> dict[str, Any] | None:
    """
    Call the wireframe service to produce a SerializedSceneGraph.

    Either ``components`` (list of {component, overrides}) or ``jsx`` must be
    provided.  Returns the SerializedSceneGraph dict on success, or None on
    failure.
    """
    body: dict[str, Any] = {"name": name, "width": width, "height": height}
    if jsx:
        body["jsx"] = jsx
    elif components:
        body["components"] = components
    else:
        return None

    try:
        resp = httpx.post(
            f"{_base_url()}/render",
            json=body,
            timeout=60.0,
        )
        resp.raise_for_status()
        return resp.json()
    except httpx.HTTPStatusError as e:
        SmartLogger.log(
            "ERROR",
            f"Wireframe render HTTP error: {e.response.status_code} {e.response.text[:500]}",
            category="open_pencil.render.error",
            params={"name": name, "status": e.response.status_code},
        )
        return None
    except Exception as e:
        SmartLogger.log(
            "ERROR",
            f"Wireframe render failed: {e}",
            category="open_pencil.render.error",
            params={"name": name, "error": str(e)},
        )
        return None


# ------------------------------------------------------------------ #
#  Convenience: parse LLM JSON output → render                        #
# ------------------------------------------------------------------ #

def parse_and_render_llm_output(
    raw_text: str,
    *,
    name: str = "Wireframe",
    width: int = 375,
    height: int = 812,
) -> dict[str, Any] | None:
    """
    Parse LLM output (expected JSON with ``components`` array) and call render.

    The LLM is expected to return JSON like:
    {
      "components": [
        {"component": "top-bar", "overrides": {"title": "주문 관리"}},
        {"component": "com-card-product", "overrides": {}},
        ...
      ]
    }

    Returns SerializedSceneGraph dict, or None on failure.
    """
    # Strip markdown fences if present
    text = raw_text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        # Remove first and last fence lines
        lines = [l for l in lines if not l.strip().startswith("```")]
        text = "\n".join(lines).strip()

    try:
        data = json.loads(text, strict=False)
    except json.JSONDecodeError as e:
        SmartLogger.log(
            "WARN",
            f"LLM output is not valid JSON: {e}",
            category="open_pencil.parse.error",
            params={"raw_length": len(raw_text)},
        )
        return None

    components = data.get("components")
    if not isinstance(components, list) or len(components) == 0:
        SmartLogger.log(
            "WARN",
            "LLM output has no 'components' array",
            category="open_pencil.parse.error",
        )
        return None

    return render_wireframe(
        components=components,
        name=name,
        width=width,
        height=height,
    )
