"""Tests for the scene-graph element-tree extractor + local SVG renderer (T015)."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from api.features.ddd_spec import paths as paths_mod
from api.features.ddd_spec import wireframe_render


# --- element-tree extractor ----------------------------------------------


def test_empty_scene_graph_returns_empty_string():
    assert wireframe_render.extract_element_tree(None) == ""
    assert wireframe_render.extract_element_tree("") == ""
    assert wireframe_render.extract_element_tree("not-json") == ""


def test_legacy_inline_text_node_renders_with_content():
    """Backward-compat: the original {"root": {... children: [...]}} shape."""
    sg = json.dumps({"root": {"type": "text", "characters": "Hello"}})
    out = wireframe_render.extract_element_tree(sg)
    assert 'text: "Hello"' in out


def test_legacy_button_renders_with_label():
    sg = json.dumps({"root": {"type": "button", "name": "Buy", "label": "Buy now"}})
    out = wireframe_render.extract_element_tree(sg)
    assert 'button: "Buy now"' in out


def test_legacy_input_renders_with_placeholder():
    sg = json.dumps({"root": {"type": "input", "placeholder": "email"}})
    out = wireframe_render.extract_element_tree(sg)
    assert 'input: "email"' in out


def test_legacy_nested_children_indented():
    sg = json.dumps(
        {
            "root": {
                "type": "frame",
                "name": "Page",
                "children": [
                    {"type": "text", "characters": "Title"},
                    {
                        "type": "frame",
                        "name": "Body",
                        "children": [
                            {"type": "button", "label": "Go"},
                        ],
                    },
                ],
            }
        }
    )
    out = wireframe_render.extract_element_tree(sg)
    title_line = next(ln for ln in out.splitlines() if "Title" in ln)
    button_line = next(ln for ln in out.splitlines() if "Go" in ln)
    assert (len(button_line) - len(button_line.lstrip())) > (
        len(title_line) - len(title_line.lstrip())
    )


def test_open_pencil_flat_node_map_walked_via_childIds():
    """The real open-pencil structure: ``{nodes:{...},rootId,...}`` with
    ``childIds`` arrays (NOT inline ``children`` arrays)."""
    sg = json.dumps(
        {
            "nodes": {
                "root": {
                    "id": "root",
                    "type": "FRAME",
                    "name": "Document",
                    "width": 0,
                    "height": 0,
                    "childIds": ["page"],
                },
                "page": {
                    "id": "page",
                    "type": "FRAME",
                    "name": "Login",
                    "width": 375,
                    "height": 640,
                    "childIds": ["title", "submit"],
                },
                "title": {
                    "id": "title",
                    "type": "TEXT",
                    "text": "Welcome",
                    "fontSize": 24,
                    "x": 20,
                    "y": 40,
                    "width": 200,
                    "height": 28,
                    "childIds": [],
                },
                "submit": {
                    "id": "submit",
                    "type": "RECTANGLE",
                    "name": "Submit",
                    "x": 20,
                    "y": 100,
                    "width": 200,
                    "height": 48,
                    "childIds": ["submit_label"],
                },
                "submit_label": {
                    "id": "submit_label",
                    "type": "TEXT",
                    "text": "Sign in",
                    "x": 50,
                    "y": 15,
                    "width": 100,
                    "height": 24,
                    "childIds": [],
                },
            },
            "rootId": "root",
        }
    )
    out = wireframe_render.extract_element_tree(sg)
    # The primary visible frame is "Login" (375x640) — element tree anchors there.
    assert "frame: Login" in out
    assert 'text: "Welcome"' in out
    assert "rect: Submit" in out
    assert 'text: "Sign in"' in out


# --- SVG renderer --------------------------------------------------------


_PAGE_SG = json.dumps(
    {
        "nodes": {
            "root": {
                "id": "root",
                "type": "FRAME",
                "name": "Document",
                "width": 0,
                "height": 0,
                "childIds": ["page"],
            },
            "page": {
                "id": "page",
                "type": "FRAME",
                "name": "Login",
                "width": 375,
                "height": 640,
                "fills": [{"type": "SOLID", "color": {"r": 1, "g": 1, "b": 1, "a": 1}}],
                "childIds": ["title", "submit"],
            },
            "title": {
                "id": "title",
                "type": "TEXT",
                "text": "Welcome",
                "fontSize": 24,
                "fontWeight": 700,
                "x": 20,
                "y": 40,
                "width": 200,
                "height": 28,
                "fills": [{"type": "SOLID", "color": {"r": 0.1, "g": 0.1, "b": 0.1, "a": 1}}],
                "childIds": [],
            },
            "submit": {
                "id": "submit",
                "type": "RECTANGLE",
                "name": "Submit",
                "x": 20,
                "y": 100,
                "width": 200,
                "height": 48,
                "cornerRadius": 8,
                "fills": [
                    {"type": "SOLID", "color": {"r": 0.15, "g": 0.4, "b": 0.95, "a": 1}}
                ],
                "childIds": [],
            },
        },
        "rootId": "root",
    }
)


def test_scene_graph_to_svg_emits_frame_text_rect():
    svg = wireframe_render.scene_graph_to_svg(_PAGE_SG)
    assert svg is not None
    body = svg.decode("utf-8")
    assert "<svg" in body and 'viewBox="0 0 375 640"' in body
    # Background rect for the page frame.
    assert "<rect" in body
    # Rounded button with the brand fill.
    assert 'rx="8"' in body
    assert "rgb(38,102,242)" in body
    # Title text. SVG attribute values may use single or double quotes; accept either.
    assert "Welcome" in body
    assert 'font-size="24"' in body or "font-size='24'" in body


def test_scene_graph_to_svg_returns_none_for_invalid():
    assert wireframe_render.scene_graph_to_svg(None) is None
    assert wireframe_render.scene_graph_to_svg("") is None
    assert wireframe_render.scene_graph_to_svg("garbage") is None


def test_render_svg_to_file_writes_local_render(tmp_path, monkeypatch):
    """The default path uses the local renderer — no service call needed."""
    monkeypatch.setattr(paths_mod, "SPECS_DIR", tmp_path)
    target = tmp_path / "ui.svg"
    wrote, err = wireframe_render.render_svg_to_file(
        target=target, scene_graph_json=_PAGE_SG, overwrite=True
    )
    assert wrote is True
    assert err is None
    body = target.read_text()
    assert "<svg" in body and "Welcome" in body


def test_render_svg_to_file_handles_empty_scene_graph(tmp_path, monkeypatch):
    monkeypatch.setattr(paths_mod, "SPECS_DIR", tmp_path)
    target = tmp_path / "empty.svg"
    wrote, err = wireframe_render.render_svg_to_file(
        target=target, scene_graph_json="", overwrite=True
    )
    assert wrote is False
    assert err == "svg_render_failed"
    assert not target.exists()


def test_render_svg_to_file_service_variant_falls_back_to_local(tmp_path, monkeypatch):
    """When ``WIREFRAME_SERVICE_VARIANT=service`` is requested but the
    service is unreachable, the local renderer fills the gap silently —
    SVG is still produced."""
    import httpx

    monkeypatch.setenv("WIREFRAME_SERVICE_VARIANT", "service")
    monkeypatch.setattr(paths_mod, "SPECS_DIR", tmp_path)

    def boom(*a, **kw):
        raise httpx.ConnectError("nope")

    monkeypatch.setattr(wireframe_render.httpx, "post", boom)
    target = tmp_path / "fallback.svg"
    wrote, err = wireframe_render.render_svg_to_file(
        target=target, scene_graph_json=_PAGE_SG, overwrite=True
    )
    assert wrote is True
    assert err is None
    assert "Welcome" in target.read_text()
