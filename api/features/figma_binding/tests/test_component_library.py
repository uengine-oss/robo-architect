"""Unit tests for figma_binding.component_library (plugin-pushed scan).

REST + API-token path was retired — the Figma plugin walks the document and
ships pre-rendered PNGs to the backend, so these tests exercise the
``components`` payload directly. VLM and Neo4j repo are mocked.
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


def _png_b64() -> str:
    # Smallest valid PNG (1x1 transparent) — content doesn't matter, the
    # tests mock the VLM call. Just need *something* truthy in pngBase64.
    return "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII="


# ─── get_catalog_for_prompt (unchanged) ────────────────────────────────────


def test_get_catalog_for_prompt_empty_when_no_rows():
    with patch.object(component_library, "repository") as repo:
        repo.list_figma_components.return_value = []
        assert component_library.get_catalog_for_prompt() == ""


def test_get_catalog_for_prompt_formats_by_page():
    rows = [
        {"name": "btn-primary", "pageName": "Components", "widthPx": 120, "heightPx": 40, "vlmDescription": "Primary action button."},
        {"name": "card", "pageName": "Components", "widthPx": 320, "heightPx": 180, "vlmDescription": ""},
        {"name": "header", "pageName": "Headers", "widthPx": 375, "heightPx": 56, "vlmDescription": "Top bar with title."},
    ]
    with patch.object(component_library, "repository") as repo:
        repo.list_figma_components.return_value = rows
        catalog = component_library.get_catalog_for_prompt()
    assert "Components" in catalog and "Headers" in catalog
    assert "btn-primary" in catalog and "header" in catalog
    assert "Primary action button." in catalog
    assert "(no description)" in catalog


# ─── build_name_to_node_index / get_figma_node_id_by_name (unchanged) ─────


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
        assert component_library.get_figma_node_id_by_name("Btn-Main-Task") == "9:1"
        assert component_library.get_figma_node_id_by_name("input-search") == "9:2"
        assert component_library.get_figma_node_id_by_name("nonexistent") is None
        assert component_library.get_figma_node_id_by_name("") is None


# ─── scan_components (plugin-pushed) ───────────────────────────────────────


def test_scan_components_requires_active_binding():
    with patch.object(component_library, "repository") as repo:
        repo.get_active_binding.return_value = None
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as ei:
            asyncio.run(
                component_library.scan_components(components=[], actor="tester")
            )
        assert ei.value.status_code == 404


def test_scan_components_happy_path_plugin_payload():
    binding = _fake_binding("file-1")
    pushed = [
        {
            "figmaNodeId": "1:1",
            "name": "btn-primary",
            "pageName": "Components",
            "widthPx": 120,
            "heightPx": 40,
            "pngBase64": _png_b64(),
        },
        {
            "figmaNodeId": "1:2",
            "name": "card",
            "pageName": "Components",
            "widthPx": 320,
            "heightPx": 180,
            "pngBase64": _png_b64(),
        },
    ]
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
         patch.object(component_library, "component_vlm") as vlm:
        repo.get_active_binding.return_value = binding
        repo.list_figma_components.return_value = []
        repo.upsert_figma_component.side_effect = _upsert
        repo.delete_stale_figma_components.side_effect = _delete_stale
        repo.count_figma_components.return_value = 2
        vlm.describe_components = AsyncMock(return_value=described)
        component_library._scan_in_flight = False

        out = asyncio.run(
            component_library.scan_components(components=pushed, actor="tester")
        )

    assert out["scanned"] == 2
    assert out["added"] == 2
    assert out["updated"] == 0
    assert out["componentCount"] == 2
    assert out["vlmDescribed"] == 1
    assert out["vlmFailures"] == 1
    assert sorted(delete_calls[0]) == ["1:1", "1:2"]
    descs = {c["figma_node_id"]: c["vlm_description"] for c in upsert_calls}
    assert descs["1:1"].startswith("A primary")
    assert descs["1:2"] == ""
    # VLM was handed data: URIs, never raw URLs.
    vlm.describe_components.assert_awaited_once()
    args = vlm.describe_components.await_args
    handed_in = list(args.args[0]) if args.args else list(args.kwargs.get("inputs") or [])
    assert all(url.startswith("data:image/png;base64,") for _, _, url in handed_in)


def test_scan_components_skips_items_without_png():
    """A plugin-pushed item without pngBase64 still persists as a row but
    contributes no VLM input (so it falls into vlmFailures)."""
    binding = _fake_binding("file-1")
    pushed = [
        {"figmaNodeId": "1:1", "name": "no-image", "pageName": "P", "widthPx": 1, "heightPx": 1, "pngBase64": ""},
    ]
    with patch.object(component_library, "repository") as repo, \
         patch.object(component_library, "component_vlm") as vlm:
        repo.get_active_binding.return_value = binding
        repo.list_figma_components.return_value = []
        repo.upsert_figma_component.return_value = {}
        repo.delete_stale_figma_components.return_value = 0
        repo.count_figma_components.return_value = 1
        vlm.describe_components = AsyncMock(return_value={})
        component_library._scan_in_flight = False
        out = asyncio.run(
            component_library.scan_components(components=pushed, actor="tester")
        )
    assert out["scanned"] == 1
    assert out["vlmDescribed"] == 0
    assert out["vlmFailures"] == 1
    # VLM helper called with an empty input list — caller filters png-less items.
    vlm.describe_components.assert_not_awaited()


def test_scan_components_concurrent_returns_409():
    binding = _fake_binding("file-1")
    component_library._scan_in_flight = True
    try:
        with patch.object(component_library, "repository") as repo:
            repo.get_active_binding.return_value = binding
            from fastapi import HTTPException
            with pytest.raises(HTTPException) as ei:
                asyncio.run(
                    component_library.scan_components(components=[], actor="tester")
                )
            assert ei.value.status_code == 409
    finally:
        component_library._scan_in_flight = False
