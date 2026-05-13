"""Inline SVG renderers for the HTML policy document.

Produces self-contained SVG strings (no external font/CSS dependencies)
suitable for direct embedding in `document.html.j2` via `{{ ... | safe }}`.
Layouts are grid-based and intentionally simple — graphviz/mermaid would
require a system dependency we don't want here.
"""
from __future__ import annotations

from html import escape
from typing import Optional

from api.features.prd_generation.html_templates.schema import (
    ActorInfo,
    ProcessRow,
    UseCaseRow,
)


def _svg_text(s: str) -> str:
    """Escape text for inclusion as SVG `<text>` content."""
    return escape(s or "", quote=False)


# ----- use-case diagram ---------------------------------------------------


def render_usecase_diagram(
    actors: list[ActorInfo],
    use_cases: list[UseCaseRow],
) -> Optional[str]:
    """Render an actor↔use-case diagram in the style of the input sample.

    Left column: primary/secondary actors. Right column: external actors.
    Centre: vertical stack of use-case ellipses inside a system boundary box.
    Returns `None` when there's nothing meaningful to draw.
    """
    if not use_cases:
        return None

    left = [a for a in actors if a.kind != "external"]
    right = [a for a in actors if a.kind == "external"]
    ucs = use_cases

    box_w = 540
    margin_x = 290
    width = 1120
    row_step = 70
    box_h = max(180, 80 + row_step * len(ucs))
    height = max(box_h + 80, 360, 80 + max(len(left), len(right)) * 140 + 40)

    uc_cx = margin_x + box_w / 2
    parts: list[str] = []
    parts.append(
        f'<svg viewBox="0 0 {width} {height}" width="{width}" height="{height}" '
        f'xmlns="http://www.w3.org/2000/svg" role="img" aria-label="Use-case diagram">'
    )
    parts.append(
        '<defs>'
        '<marker id="arrow" markerHeight="7" markerWidth="7" orient="auto-start-reverse" '
        'refX="9" refY="5" viewBox="0 0 10 10">'
        '<path d="M 0 0 L 10 5 L 0 10 z" fill="#8a94a6"></path></marker>'
        '<style>.sysbox{fill:#fff;stroke:#c6cfdb;stroke-width:1.5}'
        '.title{font:700 15px Arial,sans-serif;fill:#222}'
        '.uc{fill:#f7f9fc;stroke:#8fa3bf;stroke-width:1.5}'
        '.uc-text{font:13px Arial,sans-serif;fill:#1f2937}'
        '.actor-line{stroke:#4f5b6a;stroke-width:2;fill:none}'
        '.actor-text{font:14px Arial,sans-serif;fill:#222}'
        '.conn{stroke:#8a94a6;stroke-width:1.4;fill:none}'
        '.label{font:12px Arial,sans-serif;fill:#5b6472}</style></defs>'
    )

    parts.append(
        f'<rect class="sysbox" x="{margin_x}" y="30" width="{box_w}" height="{box_h}" rx="12" ry="12"/>'
    )
    parts.append(
        f'<text class="title" x="{uc_cx}" y="55" text-anchor="middle">시스템 경계</text>'
    )

    for idx, uc in enumerate(ucs):
        cy = 110 + idx * row_step
        parts.append(
            f'<ellipse class="uc" cx="{uc_cx}" cy="{cy}" rx="180" ry="24"/>'
        )
        parts.append(
            f'<text class="uc-text" x="{uc_cx}" y="{cy + 5}" text-anchor="middle">'
            f'{_svg_text(uc.name)}</text>'
        )

    def _stick_figure(cx: int, cy: int, label: str) -> str:
        return (
            f'<circle class="actor-line" cx="{cx}" cy="{cy}" r="18"/>'
            f'<line class="actor-line" x1="{cx}" y1="{cy + 18}" x2="{cx}" y2="{cy + 65}"/>'
            f'<line class="actor-line" x1="{cx - 26}" y1="{cy + 35}" x2="{cx + 26}" y2="{cy + 35}"/>'
            f'<line class="actor-line" x1="{cx}" y1="{cy + 65}" x2="{cx - 20}" y2="{cy + 100}"/>'
            f'<line class="actor-line" x1="{cx}" y1="{cy + 65}" x2="{cx + 20}" y2="{cy + 100}"/>'
            f'<text class="actor-text" x="{cx}" y="{cy + 125}" text-anchor="middle">'
            f'{_svg_text(label)}</text>'
        )

    left_x = 110
    for i, actor in enumerate(left):
        cy = 110 + i * 160
        if cy + 130 > height:
            break
        parts.append(_stick_figure(left_x, cy, actor.name))
        parts.append(
            f'<line class="conn" x1="{left_x + 20}" y1="{cy + 10}" '
            f'x2="{margin_x - 20}" y2="{110 + (len(ucs) // 2) * row_step}"/>'
        )

    right_x = 1010
    for i, actor in enumerate(right):
        cy = 110 + i * 160
        if cy + 130 > height:
            break
        parts.append(_stick_figure(right_x, cy, actor.name))
        parts.append(
            f'<line class="conn" x1="{right_x - 20}" y1="{cy + 10}" '
            f'x2="{margin_x + box_w + 20}" y2="{110 + (len(ucs) // 2) * row_step}"/>'
        )

    parts.append('</svg>')
    return "".join(parts)


# ----- process flowchart --------------------------------------------------


def render_process_flowchart(processes: list[ProcessRow]) -> Optional[str]:
    """Render a process flowchart: one row per process, boxes per step.

    Returns `None` when there's nothing meaningful to draw.
    """
    if not processes:
        return None
    rows = [pr for pr in processes if pr.steps]
    if not rows:
        return None

    box_w = 170
    box_h = 56
    gap_x = 30
    gap_y = 28
    label_w = 200
    width = 1120
    row_h = box_h + gap_y
    max_steps = max(len(pr.steps) for pr in rows)
    inner_w = label_w + (box_w + gap_x) * max_steps
    if inner_w > width - 40:
        # Allow horizontal scroll via viewBox without resizing the SVG.
        width = inner_w + 40
    height = 40 + row_h * len(rows) + 20

    parts: list[str] = []
    parts.append(
        f'<svg viewBox="0 0 {width} {height}" width="{width}" height="{height}" '
        f'xmlns="http://www.w3.org/2000/svg" role="img" aria-label="Process flowchart">'
    )
    parts.append(
        '<defs>'
        '<marker id="parrow" markerHeight="7" markerWidth="7" orient="auto" '
        'refX="9" refY="5" viewBox="0 0 10 10">'
        '<path d="M 0 0 L 10 5 L 0 10 z" fill="#7b8798"></path></marker>'
        '<style>.pbox{fill:#f7f9fc;stroke:#8fa3bf;stroke-width:1.5}'
        '.ptext{font:12px Arial,sans-serif;fill:#1f2937}'
        '.plabel{font:700 13px Arial,sans-serif;fill:#222}'
        '.pflow{stroke:#7b8798;stroke-width:1.4;fill:none}</style></defs>'
    )

    for r_idx, pr in enumerate(rows):
        y = 30 + r_idx * row_h
        parts.append(
            f'<text class="plabel" x="20" y="{y + box_h / 2 + 4}">{_svg_text(pr.name)}</text>'
        )
        prev_x_end: Optional[int] = None
        for s_idx, step in enumerate(pr.steps):
            x = label_w + s_idx * (box_w + gap_x)
            parts.append(
                f'<rect class="pbox" x="{x}" y="{y}" width="{box_w}" height="{box_h}" rx="6"/>'
            )
            label = step.name or f"단계 {step.seq}"
            if len(label) > 26:
                label = label[:25] + "…"
            parts.append(
                f'<text class="ptext" x="{x + box_w / 2}" y="{y + box_h / 2 + 4}" '
                f'text-anchor="middle">{_svg_text(label)}</text>'
            )
            if prev_x_end is not None:
                parts.append(
                    f'<line class="pflow" x1="{prev_x_end}" y1="{y + box_h / 2}" '
                    f'x2="{x}" y2="{y + box_h / 2}" marker-end="url(#parrow)"/>'
                )
            prev_x_end = x + box_w

    parts.append('</svg>')
    return "".join(parts)
