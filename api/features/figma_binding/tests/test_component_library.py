"""Unit tests for spec 024 figma_binding.component_library.

Focus: the synchronous orchestrator that walks the Figma file, persists
:FigmaComponent rows, and surfaces a catalog string for prompt injection.
Network and VLM are mocked; Neo4j repo is patched at module boundary.
"""
from __future__ import annotations

import asyncio

import pytest
from unittest.mock import AsyncMock, patch

from api.features.figma_binding import component_library


def _fake_binding(file_key: str = "abc123") -> dict:
    return {
        "id": "singleton",
        "figmaFileKey": file_key,
        "figmaFileName": "Test",
        "status": "active",
    }


# ─── _flatten_components ──────────────────────────────────────────────────


def test_flatten_components_collects_component_and_set_only():
    page = {
        "type": "CANVAS",
        "name": "Library",
        "children": [
            {
                "type": "COMPONENT",
                "id": "1:1",
                "name": "btn-primary",
                "absoluteBoundingBox": {"width": 120, "height": 40},
            },
            {
                "type": "COMPONENT_SET",
                "id": "1:2",
                "name": "card",
                "absoluteBoundingBox": {"width": 320, "height": 180},
                "children": [
                    # Variant child should NOT appear (we don't descend into sets).
                    {"type": "COMPONENT", "id": "1:3", "name": "card/active"}
                ],
            },
            {
                "type": "FRAME",
                "id": "1:4",
                "name": "some-frame",
                "children": [
                    {
                        "type": "COMPONENT",
                        "id": "1:5",
                        "name": "deeply-nested",
                        "absoluteBoundingBox": {"width": 50, "height": 50},
                    }
                ],
            },
        ],
    }
    out: list[dict] = []
    for child in page["children"]:
        component_library._flatten_components(child, "Library", out)
    names = sorted(c["name"] for c in out)
    # card variant excluded; nested COMPONENT inside a FRAME included.
    assert names == ["btn-primary", "card", "deeply-nested"]


# ─── get_catalog_for_prompt ────────────────────────────────────────────────


def test_get_catalog_for_prompt_empty_when_no_rows():
    with patch.object(component_library, "repository") as repo:
        repo.list_figma_components.return_value = []
        assert component_library.get_catalog_for_prompt() == ""


def test_get_catalog_for_prompt_formats_by_page():
    rows = [
        {
            "name": "btn-primary",
            "pageName": "Components",
            "widthPx": 120,
            "heightPx": 40,
            "vlmDescription": "Primary action button.",
        },
        {
            "name": "card",
            "pageName": "Components",
            "widthPx": 320,
            "heightPx": 180,
            "vlmDescription": "",  # no description
        },
        {
            "name": "header",
            "pageName": "Headers",
            "widthPx": 375,
            "heightPx": 56,
            "vlmDescription": "Top bar with title.",
        },
    ]
    with patch.object(component_library, "repository") as repo:
        repo.list_figma_components.return_value = rows
        catalog = component_library.get_catalog_for_prompt()
    assert "Components" in catalog
    assert "Headers" in catalog
    assert "btn-primary" in catalog
    assert "Primary action button." in catalog
    assert "(no description)" in catalog
    # name should appear (case sensitivity is per-prompt instruction, not the row).
    assert "header" in catalog


# ─── build_name_to_node_index / get_figma_node_id_by_name ───────────────────


def test_name_to_node_index_lowercases_and_includes_size():
    rows = [
        {"name": "TopBar", "figmaNodeId": "1:1", "widthPx": 375, "heightPx": 56},
        {"name": "card", "figmaNodeId": "1:2", "widthPx": 320, "heightPx": 180},
    ]
    with patch.object(component_library, "repository") as repo:
        repo.list_figma_components.return_value = rows
        idx = component_library.build_name_to_node_index()
    assert set(idx.keys()) == {"topbar", "card"}
    assert idx["topbar"]["figmaNodeId"] == "1:1"
    assert idx["card"]["widthPx"] == 320


def test_get_figma_node_id_by_name_exact_and_substring():
    rows = [
        {"name": "btn-main-task", "figmaNodeId": "9:1"},
        {"name": "input-search-gray", "figmaNodeId": "9:2"},
    ]
    with patch.object(component_library, "repository") as repo:
        repo.list_figma_components.return_value = rows
        # Exact (case-insensitive).
        assert component_library.get_figma_node_id_by_name("Btn-Main-Task") == "9:1"
        # Substring.
        assert component_library.get_figma_node_id_by_name("input-search") == "9:2"
        # Miss.
        assert component_library.get_figma_node_id_by_name("nonexistent") is None
        # Empty.
        assert component_library.get_figma_node_id_by_name("") is None


# ─── scan_components: 404 when no binding ──────────────────────────────────


def test_scan_components_requires_active_binding():
    with patch.object(component_library, "repository") as repo:
        repo.get_active_binding.return_value = None
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as ei:
            asyncio.run(
                component_library.scan_components(api_token="x", actor="tester")
            )
        assert ei.value.status_code == 404


# ─── scan_components: happy path with mocked deps ──────────────────────────


def test_scan_components_happy_path():
    binding = _fake_binding("file-1")
    components_from_figma = [
        {
            "figmaNodeId": "1:1",
            "name": "btn-primary",
            "pageName": "Components",
            "widthPx": 120,
            "heightPx": 40,
        },
        {
            "figmaNodeId": "1:2",
            "name": "card",
            "pageName": "Components",
            "widthPx": 320,
            "heightPx": 180,
        },
    ]
    image_map = {"1:1": "https://figma-image/1.png", "1:2": "https://figma-image/2.png"}
    described = {"1:1": "A primary call-to-action button.", "1:2": ""}

    upsert_calls: list[dict] = []
    delete_calls: list[list[str]] = []

    def _upsert(**kwargs):
        upsert_calls.append(kwargs)
        return {}

    def _delete_stale(file_key, kept):
        delete_calls.append(list(kept))
        return 0

    with patch.object(component_library, "repository") as repo, \
         patch.object(component_library, "_fetch_component_nodes",
                      new=AsyncMock(return_value=components_from_figma)), \
         patch.object(component_library, "_fetch_thumbnails",
                      new=AsyncMock(return_value=image_map)), \
         patch.object(component_library, "component_vlm") as vlm:
        repo.get_active_binding.return_value = binding
        repo.list_figma_components.return_value = []
        repo.upsert_figma_component.side_effect = _upsert
        repo.delete_stale_figma_components.side_effect = _delete_stale
        repo.count_figma_components.return_value = 2
        vlm.describe_components = AsyncMock(return_value=described)
        # Reset the module-level scan-lock from a prior test that may have hit a fault.
        component_library._scan_in_flight = False

        out = asyncio.run(
            component_library.scan_components(api_token="x", actor="tester")
        )

    assert out["scanned"] == 2
    assert out["added"] == 2
    assert out["updated"] == 0
    assert out["componentCount"] == 2
    assert out["vlmDescribed"] == 1
    assert out["vlmFailures"] == 1
    # delete_stale received both kept ids.
    assert sorted(delete_calls[0]) == ["1:1", "1:2"]
    # upsert called once per component with the described value (empty for the second).
    descs = {c["figma_node_id"]: c["vlm_description"] for c in upsert_calls}
    assert descs["1:1"].startswith("A primary")
    assert descs["1:2"] == ""


def test_scan_components_concurrent_returns_409():
    """A second scan while one is in-flight should immediately 409."""
    binding = _fake_binding("file-1")
    component_library._scan_in_flight = True
    try:
        with patch.object(component_library, "repository") as repo:
            repo.get_active_binding.return_value = binding
            from fastapi import HTTPException
            with pytest.raises(HTTPException) as ei:
                asyncio.run(
                    component_library.scan_components(api_token="x", actor="tester")
                )
            assert ei.value.status_code == 409
    finally:
        component_library._scan_in_flight = False
