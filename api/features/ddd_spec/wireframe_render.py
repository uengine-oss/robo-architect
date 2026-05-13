"""Render UI wireframes from the open-pencil ``SerializedSceneGraph`` JSON.

Always produces:
  (a) a nested textual element tree (markdown bullet list, inline in
      ``requirements.md``) — the structural reference for downstream code.
  (b) an SVG rendering, rendered locally from the scene graph (no Figma
      call) — the visual reference.

Scene-graph JSON sidecars (``.scene.json``) are no longer emitted
(2026-05-12 amendment) — they leaked too much Figma-shaped structural
detail into the agent's working set, encouraging pixel-by-pixel
reproduction instead of intent-driven generation.

The open-pencil scene graph is a Figma-compatible flat node map: ``{nodes:
{id: {...}}, rootId, images}``. Each node carries position (``x``,``y``
relative to parent), size, fills, strokes, text + font properties, corner
radius, etc. The SVG renderer below traverses that structure and emits
``<rect>`` / ``<text>`` / ``<line>`` primitives at absolute positions —
sufficient for a code-generation agent to read the original design
fidelity (colors, layout, text, hierarchy) from a single static file.

If a request explicitly asks for the upstream open-pencil service (set
``WIREFRAME_SERVICE_VARIANT=service`` in the environment), we still
attempt the remote ``/render-svg`` route first and fall back to the local
renderer when it's missing — but local is the default because the
open-pencil Bun service does not currently expose a scene-graph→SVG
endpoint.
"""
from __future__ import annotations

import html
import json
import math
import os
from pathlib import Path
from typing import Any, Iterable, Literal, Optional

import httpx

from api.platform import open_pencil_client
from api.platform.observability.smart_logger import SmartLogger

from api.features.ddd_spec.paths import atomic_write_bytes, atomic_write_text


# Viewport classification thresholds (research D7+ amendment, 2026-05-12).
# Anchors taken from common breakpoint conventions: ≤480px is phone-class,
# 481–1024 is tablet-class, >1024 is desktop-class. The frontend-engineer
# agent reads the dominant class from ``framework.md`` to decide whether to
# ask the user "should the whole IA be mobile-first / desktop-first?".
ViewportClass = Literal["mobile", "tablet", "desktop"]
MOBILE_MAX_WIDTH: float = 480.0
TABLET_MAX_WIDTH: float = 1024.0


# --- scene-graph traversal ----------------------------------------------


def _parse_scene_graph(scene_graph_json: Optional[str]) -> Optional[dict[str, Any]]:
    """Return the parsed scene graph dict, or None for missing/invalid input."""
    if not scene_graph_json:
        return None
    try:
        data = json.loads(scene_graph_json)
    except (TypeError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict):
        return None
    return data


def _scene_nodes(graph: dict[str, Any]) -> tuple[dict[str, Any], Optional[str]]:
    """Return the ``(nodes, root_id)`` pair for a parsed scene graph.

    Accepts both the open-pencil ``{nodes, rootId, ...}`` shape and a
    legacy ``{root: {... children: [Node]}}`` shape — the latter is
    flattened by treating each inline node as its own entry in a synthetic
    nodes map.
    """
    nodes = graph.get("nodes")
    root_id = graph.get("rootId") or graph.get("root_id")
    if isinstance(nodes, dict) and isinstance(root_id, str):
        return nodes, root_id

    # Legacy inline-tree shape: synthesize a flat nodes map.
    root = graph.get("root") if isinstance(graph.get("root"), dict) else graph
    flat: dict[str, Any] = {}
    counter = [0]

    def _walk(node: Any, parent_id: Optional[str]) -> Optional[str]:
        if not isinstance(node, dict):
            return None
        nid = node.get("id") or f"n{counter[0]}"
        counter[0] += 1
        child_ids: list[str] = []
        for child in node.get("children", []) or []:
            cid = _walk(child, nid)
            if cid is not None:
                child_ids.append(cid)
        record = dict(node)
        record["childIds"] = child_ids
        record["parentId"] = parent_id
        flat[nid] = record
        return nid

    rid = _walk(root, None)
    return flat, rid


def _primary_frame(nodes: dict[str, Any], root_id: Optional[str]) -> Optional[str]:
    """Find the visible frame id whose dimensions define the viewport.

    open-pencil scene graphs nest a ``Document → Canvas → Frame`` chain
    where only the innermost ``Frame`` has real ``width``/``height``. Walk
    until we hit the first descendant with non-zero size.
    """
    if not root_id or root_id not in nodes:
        return None
    queue = [root_id]
    while queue:
        nid = queue.pop(0)
        node = nodes.get(nid) or {}
        if node.get("width") and node.get("height"):
            return nid
        queue.extend(node.get("childIds") or [])
    return root_id


def classify_viewport(width: float, height: float) -> Optional[ViewportClass]:
    """Bucket a primary-frame ``(width, height)`` pair into a viewport class.

    Returns ``None`` when the input is missing or non-positive — callers
    treat that as "unknown" and skip it in the dominant-viewport summary.

    Classification uses ``width`` directly: designers in open-pencil
    always set the frame width to the *device* width (375 / 390 for
    phones, 768 for tablet portrait, 1280+ for desktop), regardless of
    how tall the screen is. ``max(w, h)`` misfires on portrait phones
    (375×812 looks "tablet") and ``min(w, h)`` misfires on shorter
    desktops (1440×900 looks "tablet"). Width tracks designer intent.
    """
    try:
        w = float(width)
        h = float(height)
    except (TypeError, ValueError):
        return None
    if w <= 0 or h <= 0:
        return None
    if w <= MOBILE_MAX_WIDTH:
        return "mobile"
    if w <= TABLET_MAX_WIDTH:
        return "tablet"
    return "desktop"


def extract_viewport_class(scene_graph_json: Optional[str]) -> Optional[ViewportClass]:
    """Parse a scene graph and classify its primary frame's viewport.

    Returns ``None`` for missing / invalid / dimensionless graphs so the
    repository can leave the projection field unset (and the summary
    can skip that wireframe entirely instead of bucketing it as a guess).
    """
    graph = _parse_scene_graph(scene_graph_json)
    if graph is None:
        return None
    nodes, root_id = _scene_nodes(graph)
    if not nodes or not root_id:
        return None
    frame_id = _primary_frame(nodes, root_id)
    if frame_id is None:
        return None
    frame = nodes.get(frame_id) or {}
    width = frame.get("width")
    height = frame.get("height")
    if not width or not height:
        return None
    return classify_viewport(width, height)


def _abs_positions(
    nodes: dict[str, Any], frame_id: str
) -> Iterable[tuple[str, float, float]]:
    """Yield ``(node_id, abs_x, abs_y)`` for ``frame_id`` and every descendant.

    Coordinates are accumulated from the frame's own origin (so the frame
    itself sits at ``(0, 0)`` in SVG-space).
    """
    stack: list[tuple[str, float, float]] = [(frame_id, 0.0, 0.0)]
    while stack:
        nid, ox, oy = stack.pop()
        node = nodes.get(nid) or {}
        x = float(node.get("x") or 0)
        y = float(node.get("y") or 0)
        ax, ay = ox + x, oy + y
        yield nid, ax, ay
        # Reverse-extend so we emit children in order.
        for cid in (node.get("childIds") or [])[::-1]:
            stack.append((cid, ax, ay))


# --- textual element tree ------------------------------------------------


def _node_label(node: dict[str, Any]) -> Optional[str]:
    """One bullet line for a node, or None to skip it from the tree."""
    if not isinstance(node, dict):
        return None
    ntype = (node.get("type") or "").upper()
    name = node.get("name") or ""

    # Open-pencil uses ``text``; older / synthetic graphs use ``characters``,
    # ``label``, ``value``, ``content``. Take the first non-empty match.
    text_content = ""
    for key in ("text", "characters", "label", "value", "content"):
        candidate = node.get(key)
        if isinstance(candidate, str) and candidate.strip():
            text_content = candidate.strip()
            break

    if ntype == "TEXT" and text_content:
        return f'text: "{text_content}"'
    if ntype in {"BUTTON"}:
        return f'button: "{text_content or name or "(no label)"}"'
    if ntype in {"INPUT", "TEXTINPUT", "TEXTFIELD"}:
        placeholder = node.get("placeholder") or text_content or name
        return f'input: "{placeholder or "(no label)"}"'
    if ntype in {"FRAME", "GROUP", "CONTAINER", "STACK", "SECTION", "COMPONENT", "INSTANCE"}:
        layout = node.get("layoutMode") or ""
        layout_str = ""
        if isinstance(layout, str) and layout not in ("", "NONE"):
            layout_str = f" · layout: {layout.lower()}"
        if name:
            return f"frame: {name}{layout_str}"
        return f"frame{layout_str}"
    if ntype == "RECTANGLE":
        # Rectangles often act as button backgrounds; surface the name + text
        # of the rectangle and its descendant TEXT (handled by the walker).
        if name:
            return f"rect: {name}"
        return None
    if ntype == "VECTOR":
        return f"icon: {name}" if name else "icon"
    if ntype == "CANVAS":
        return None
    if text_content:
        return f'text: "{text_content}"'
    if name:
        return f"{ntype.lower() or 'node'}: {name}"
    return None


def extract_element_tree(scene_graph_json: Optional[str]) -> str:
    """Walk the scene graph and emit a nested markdown bullet list."""
    graph = _parse_scene_graph(scene_graph_json)
    if graph is None:
        return ""
    nodes, root_id = _scene_nodes(graph)
    if not nodes or not root_id:
        return ""
    start = _primary_frame(nodes, root_id) or root_id

    out: list[str] = []

    def walk(nid: str, depth: int) -> None:
        node = nodes.get(nid) or {}
        label = _node_label(node)
        next_depth = depth
        if label is not None:
            out.append(("  " * depth) + f"- {label}")
            next_depth = depth + 1
        for cid in node.get("childIds") or []:
            walk(cid, next_depth)

    walk(start, 0)
    return "\n".join(out).strip()


# --- SVG rendering -------------------------------------------------------


def _color_str(fill: dict[str, Any], opacity_multiplier: float = 1.0) -> Optional[str]:
    """Return a CSS color string for a fill/stroke entry, or None to skip."""
    if not isinstance(fill, dict) or fill.get("visible") is False:
        return None
    if fill.get("type", "SOLID") != "SOLID":
        return None
    color = fill.get("color")
    if not isinstance(color, dict):
        return None
    r = int(round(float(color.get("r", 0)) * 255))
    g = int(round(float(color.get("g", 0)) * 255))
    b = int(round(float(color.get("b", 0)) * 255))
    a = float(color.get("a", 1)) * float(fill.get("opacity", 1)) * opacity_multiplier
    a = max(0.0, min(1.0, a))
    if a >= 0.999:
        return f"rgb({r},{g},{b})"
    return f"rgba({r},{g},{b},{a:.3f})"


def _first_solid(fills: Any) -> Optional[dict[str, Any]]:
    if not isinstance(fills, list):
        return None
    for f in fills:
        if isinstance(f, dict) and f.get("type", "SOLID") == "SOLID" and f.get("visible") is not False:
            return f
    return None


def _font_family(node: dict[str, Any]) -> str:
    raw = (node.get("fontFamily") or "Inter").strip() or "Inter"
    # Add CJK fallbacks so Korean glyphs render in viewers without Inter-CJK.
    return f'"{raw}", "Apple SD Gothic Neo", "Pretendard", "Noto Sans KR", sans-serif'


def _font_weight(node: dict[str, Any]) -> str:
    fw = node.get("fontWeight")
    if isinstance(fw, (int, float)) and 100 <= fw <= 1000:
        return str(int(fw))
    return "400"


def _text_anchor(node: dict[str, Any]) -> str:
    align = (node.get("textAlignHorizontal") or "LEFT").upper()
    if align == "CENTER":
        return "middle"
    if align == "RIGHT":
        return "end"
    return "start"


def _svg_attr_escape(value: str) -> str:
    return html.escape(value, quote=True)


def _render_rect(node: dict[str, Any], x: float, y: float, w: float, h: float) -> Optional[str]:
    """Emit a <rect> for FRAME/RECTANGLE-like nodes."""
    fill = _first_solid(node.get("fills"))
    stroke = _first_solid(node.get("strokes"))
    if fill is None and stroke is None:
        return None
    fill_color = _color_str(fill) if fill else "none"
    stroke_attrs = ""
    if stroke:
        stroke_color = _color_str(stroke) or "none"
        # ``strokes`` entries can be {"weight":N} or attached on the node.
        weight = stroke.get("weight") or node.get("strokeWeight") or 1
        stroke_attrs = f' stroke="{stroke_color}" stroke-width="{weight}"'
    rx = node.get("cornerRadius") or 0
    rx_attrs = f' rx="{rx}" ry="{rx}"' if rx else ""
    opacity = float(node.get("opacity") or 1)
    opacity_attrs = f' opacity="{opacity:.3f}"' if opacity < 1 else ""
    return (
        f'<rect x="{x:g}" y="{y:g}" width="{w:g}" height="{h:g}"'
        f' fill="{fill_color}"{stroke_attrs}{rx_attrs}{opacity_attrs} />'
    )


def _render_text(node: dict[str, Any], x: float, y: float, w: float, h: float) -> Optional[str]:
    text = node.get("text")
    if not isinstance(text, str) or not text.strip():
        return None
    fill = _first_solid(node.get("fills"))
    color = _color_str(fill) if fill else "rgb(20,20,20)"
    fs = float(node.get("fontSize") or 14)
    fw = _font_weight(node)
    style = "italic" if node.get("italic") else "normal"
    anchor = _text_anchor(node)
    # SVG <text> y is the baseline. Approximate baseline = top + 0.8*fontSize.
    baseline_y = y + fs * 0.85
    tx = x
    if anchor == "middle":
        tx = x + w / 2
    elif anchor == "end":
        tx = x + w

    lines = [ln for ln in text.splitlines() if ln is not None]
    if not lines:
        lines = [""]
    line_height = float(node.get("lineHeight") or fs * 1.2)
    spans: list[str] = []
    for i, ln in enumerate(lines):
        dy = "0" if i == 0 else f"{line_height:g}"
        spans.append(
            f'<tspan x="{tx:g}" dy="{dy}">{_svg_attr_escape(ln)}</tspan>'
        )
    family = _font_family(node)
    # SVG attribute values are wrapped in single quotes so the double-quoted
    # CSS font names inside ``family`` don't need escaping. CJK fallback
    # names propagate through to viewers that lack Inter glyphs.
    return (
        f"<text x='{tx:g}' y='{baseline_y:g}' font-family='{family}'"
        f" font-size='{fs:g}' font-weight='{fw}' font-style='{style}'"
        f" fill='{color}' text-anchor='{anchor}'>"
        + "".join(spans)
        + "</text>"
    )


def _render_vector(node: dict[str, Any], x: float, y: float, w: float, h: float) -> Optional[str]:
    """Minimal VECTOR support — draws straight-line segments from the
    ``vectorNetwork`` if present. Curves and arcs are skipped."""
    vn = node.get("vectorNetwork")
    if not isinstance(vn, dict):
        return None
    verts = vn.get("vertices") or []
    segs = vn.get("segments") or []
    stroke = _first_solid(node.get("strokes"))
    stroke_color = _color_str(stroke) if stroke else "rgb(80,80,80)"
    weight = (stroke or {}).get("weight") or 2
    pieces: list[str] = []
    for seg in segs:
        s = seg.get("start")
        e = seg.get("end")
        if not isinstance(s, int) or not isinstance(e, int):
            continue
        if s < 0 or s >= len(verts) or e < 0 or e >= len(verts):
            continue
        sv = verts[s]
        ev = verts[e]
        if not (isinstance(sv, dict) and isinstance(ev, dict)):
            continue
        x1 = x + float(sv.get("x", 0))
        y1 = y + float(sv.get("y", 0))
        x2 = x + float(ev.get("x", 0))
        y2 = y + float(ev.get("y", 0))
        pieces.append(
            f'<line x1="{x1:g}" y1="{y1:g}" x2="{x2:g}" y2="{y2:g}"'
            f' stroke="{stroke_color}" stroke-width="{weight}" stroke-linecap="round" />'
        )
    return "".join(pieces) if pieces else None


def scene_graph_to_svg(scene_graph_json: str) -> Optional[bytes]:
    """Render the scene graph to an SVG byte payload.

    Returns ``None`` when the input is missing or unrenderable. The
    coordinate system is anchored at the primary visible frame, so the
    resulting SVG matches the wireframe's intended viewport.
    """
    graph = _parse_scene_graph(scene_graph_json)
    if graph is None:
        return None
    nodes, root_id = _scene_nodes(graph)
    if not nodes or not root_id:
        return None
    frame_id = _primary_frame(nodes, root_id)
    if frame_id is None:
        return None
    frame = nodes.get(frame_id) or {}
    width = float(frame.get("width") or 0) or 375
    height = float(frame.get("height") or 0) or 640

    elements: list[str] = []
    elements.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width:g} {height:g}"'
        f' width="{width:g}" height="{height:g}">'
    )
    # Background frame fill, if any.
    rect = _render_rect(frame, 0, 0, width, height)
    if rect is not None:
        elements.append(rect)

    # Walk descendants relative to the frame.
    for nid, ax, ay in _abs_positions(nodes, frame_id):
        if nid == frame_id:
            continue
        node = nodes.get(nid) or {}
        if node.get("visible") is False:
            continue
        ntype = (node.get("type") or "").upper()
        w = float(node.get("width") or 0)
        h = float(node.get("height") or 0)
        if ntype in {"FRAME", "RECTANGLE", "GROUP", "COMPONENT", "INSTANCE"}:
            piece = _render_rect(node, ax, ay, w, h)
            if piece:
                elements.append(piece)
        elif ntype == "TEXT":
            piece = _render_text(node, ax, ay, w, h)
            if piece:
                elements.append(piece)
        elif ntype == "VECTOR":
            piece = _render_vector(node, ax, ay, w, h)
            if piece:
                elements.append(piece)
        elif ntype == "ELLIPSE":
            cx = ax + w / 2
            cy = ay + h / 2
            rx = w / 2
            ry = h / 2
            fill = _first_solid(node.get("fills"))
            fill_color = _color_str(fill) if fill else "none"
            elements.append(
                f'<ellipse cx="{cx:g}" cy="{cy:g}" rx="{rx:g}" ry="{ry:g}" fill="{fill_color}" />'
            )
        # Other types (CANVAS, etc.) are structural — children still walked.

    elements.append("</svg>")
    return ("\n".join(elements) + "\n").encode("utf-8")


# --- file writing --------------------------------------------------------


# Note: scene-graph JSON sidecars (`.scene.json`) are no longer emitted
# (2026-05-12 amendment). The SVG below is the sole visual asset; the
# element tree inside requirements.md is the structural reference.


def _try_render_svg_via_service(scene_graph_json: str) -> tuple[Optional[bytes], Optional[str]]:
    """Best-effort SVG render via the open-pencil HTTP service.

    Returns ``(svg_bytes, error_code)``. The open-pencil Bun service does
    not currently expose a scene-graph→SVG route, so this almost always
    returns ``(None, "wireframe_service_unavailable" | "svg_render_failed")``
    today — callers should fall back to :func:`scene_graph_to_svg`.
    """
    base = open_pencil_client.WIREFRAME_SERVICE_URL.rstrip("/")
    try:
        payload = json.loads(scene_graph_json)
    except json.JSONDecodeError:
        return None, "svg_render_failed"
    try:
        for path in ("/render-svg", "/scene-graph/svg"):
            try:
                resp = httpx.post(
                    f"{base}{path}",
                    json={"sceneGraph": payload},
                    timeout=30.0,
                )
            except httpx.ConnectError:
                return None, "wireframe_service_unavailable"
            except httpx.TimeoutException:
                return None, "svg_render_failed"
            if resp.status_code == 404:
                continue
            if resp.is_success:
                ctype = resp.headers.get("content-type", "")
                if "svg" in ctype or resp.content.lstrip().startswith(b"<"):
                    return resp.content, None
                try:
                    body = resp.json()
                    svg = body.get("svg") if isinstance(body, dict) else None
                    if isinstance(svg, str) and svg.strip():
                        return svg.encode("utf-8"), None
                except json.JSONDecodeError:
                    pass
                return None, "svg_render_failed"
            return None, "svg_render_failed"
    except Exception as e:  # noqa: BLE001 — never raise out of best-effort render
        SmartLogger.log(
            "WARN",
            f"DDD-spec SVG service render failed: {e}",
            category="ddd_spec.wireframe.svg_service_failed",
        )
        return None, "svg_render_failed"
    return None, "svg_render_failed"


def render_svg_to_file(
    *,
    target: Path,
    scene_graph_json: str,
    overwrite: bool,
) -> tuple[bool, Optional[str]]:
    """Try to render and write an SVG.

    Strategy (research D4 with a local-renderer addendum):

    1. If ``WIREFRAME_SERVICE_VARIANT=service`` is set, attempt the
       open-pencil HTTP route first and only fall back to the local
       renderer when the service has no route.
    2. Otherwise (the default), render directly from the scene graph in
       Python via :func:`scene_graph_to_svg`. The local renderer covers
       the layout-faithful subset every code-generation agent needs
       (frames, rectangles, text, basic vectors) and runs offline.

    Returns ``(written, error_code)``. ``error_code`` is ``None`` on
    success, otherwise a warning code suitable for the caller's warning
    list (``wireframe_service_unavailable`` only when the operator
    *requested* the service variant and it was down).
    """
    if not scene_graph_json:
        return False, "svg_render_failed"

    use_service_first = os.getenv("WIREFRAME_SERVICE_VARIANT", "").lower() == "service"
    svc_error: Optional[str] = None
    if use_service_first:
        svg, err = _try_render_svg_via_service(scene_graph_json)
        if svg is not None:
            return atomic_write_bytes(target, svg, overwrite=overwrite), None
        svc_error = err

    svg = scene_graph_to_svg(scene_graph_json)
    if svg is None:
        return False, svc_error or "svg_render_failed"
    wrote = atomic_write_bytes(target, svg, overwrite=overwrite)
    return wrote, None
