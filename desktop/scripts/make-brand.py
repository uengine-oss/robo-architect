#!/usr/bin/env python3
"""Brand artwork, in one colour: the Ra mark knocked out of a rounded box, and the lockup
(box + "Robo Architect" wordmark). Same construction as Ontological Studio's brand (its
scripts/make-brand.py) so the two apps read as one family.

    python3 desktop/scripts/make-brand.py --font <Roboto-Bold.ttf>

Writes (desktop/resources/brand/, copied to frontend/public/brand/)
  ra-mark.svg        the mark alone, black on transparent
  ra-box.svg         box with the mark cut out (transparent), for 40 px and up
  ra-box-small.svg   the same with wider gaps, for menu bars, tabs and favicons
  ra-lockup.svg      box + wordmark, 240 px tall

The mark: an R whose leg runs into the ring of a single-storey a and stops inside it — the
ring passes over the leg, so the R is hooked into the a. Strokes are monoline like the OL
mark; the gap where the ring crosses the leg is real transparency (a mask), so the mark
sits on any background. Everything is black: pages flip it for dark themes with a CSS
invert filter, and the cut-out mark shows whatever is behind the box. The wordmark is
Roboto Bold (Apache License 2.0, github.com/googlefonts/roboto) converted to outlines, so no
font ships with the app.
"""
import argparse
import math
import os
import shutil

from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from fontTools.ttLib import TTFont

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT = os.path.join(ROOT, "desktop", "resources", "brand")
COPY_TO = os.path.join(ROOT, "frontend", "public", "brand")
BOX = 240            # box size; the lockup is BOX tall
RADIUS = 54          # 22.5 % — the macOS icon tile's corner (185 / 824), as Ontological Studio
WORD = "Robo Architect"
INK = "#000"

# ── mark geometry (units: the R is 560 tall, baseline y 660) ─────────────────────────────
W = 96                       # stroke
STEM, TOP, BASE = 150, 100, 660
BOWL_R, BAR = 150, 150       # R's bowl: top bar → half circle → bottom bar
LEG_FROM, LEG_ANGLE = (300, 400), 30
RING_R, RING_CX = 140, 640   # the a: ring on the baseline + stem on its right
RING_CY = BASE - RING_R - W / 2
LEG_STOP = 10                # the leg ends this far past the ring's centre (inside the counter)
VIEW = (85, 40, 690, 640)    # what the mark covers (x, y, w, h)


def _arc(cx, cy, r, a0, a1, n=72):
    return [(cx + r * math.cos(math.radians(a0 + (a1 - a0) * i / n)),
             cy + r * math.sin(math.radians(a0 + (a1 - a0) * i / n))) for i in range(n + 1)]


def _d(pts):
    return "M" + " L".join(f"{x:.1f} {y:.1f}" for x, y in pts)


def geometry():
    bx = STEM + BAR
    bowl = [(STEM, BASE + 60), (STEM, TOP), (bx, TOP)] + _arc(bx, TOP + BOWL_R, BOWL_R, -90, 90)[1:] + [(STEM, TOP + 2 * BOWL_R)]
    ux, uy = math.cos(math.radians(LEG_ANGLE)), math.sin(math.radians(LEG_ANGLE))
    t = (RING_CX - LEG_FROM[0]) * ux + (RING_CY - LEG_FROM[1]) * uy + LEG_STOP
    leg = [LEG_FROM, (LEG_FROM[0] + ux * t, LEG_FROM[1] + uy * t)]
    ring = _arc(RING_CX, RING_CY, RING_R, 0, 360, 120)
    a_stem = [(RING_CX + RING_R, RING_CY - RING_R), (RING_CX + RING_R, BASE + 60)]
    # where the ring crosses the leg (entering the ring): the leg passes under the ring there
    d = (RING_CX - LEG_FROM[0]) * ux + (RING_CY - LEG_FROM[1]) * uy
    px, py = LEG_FROM[0] + ux * d, LEG_FROM[1] + uy * d
    h = math.sqrt(max(0.0, RING_R ** 2 - math.dist((px, py), (RING_CX, RING_CY)) ** 2))
    cross = (px - ux * h, py - uy * h)
    r_path = _d(bowl) + " " + _d(leg)
    a_path = _d(ring) + "Z " + _d(a_stem)
    return r_path, a_path, cross


def mark_body(p, ink, gap):
    """Mark shapes (+ their defs) in mark units: the R under the ring at the crossing, both
    clipped flat at the baseline."""
    r_path, a_path, (cx, cy) = geometry()
    x, y, w, h = VIEW
    defs = f'''<clipPath id="{p}base"><rect x="{x}" y="{y}" width="{w}" height="{BASE - y}"/></clipPath>
    <clipPath id="{p}x"><circle cx="{cx:.1f}" cy="{cy:.1f}" r="{W * 0.95:.0f}"/></clipPath>
    <mask id="{p}under" maskUnits="userSpaceOnUse" x="{x}" y="{y}" width="{w}" height="{h}">
      <rect x="{x}" y="{y}" width="{w}" height="{h}" fill="#fff"/>
      <path d="{a_path}" fill="none" stroke="#000" stroke-width="{W + 2 * gap}" clip-path="url(#{p}x)"/>
    </mask>'''
    shapes = (f'<g clip-path="url(#{p}base)">'
              f'<path d="{r_path}" fill="none" stroke="{ink}" stroke-width="{W}" stroke-linejoin="round" stroke-linecap="round" mask="url(#{p}under)"/>'
              f'<path d="{a_path}" fill="none" stroke="{ink}" stroke-width="{W}" stroke-linejoin="round"/></g>')
    return defs, shapes


def box_svg(p, gap, x=0, share=0.74):
    vx, vy, vw, vh = VIEW
    s = BOX * share / vw
    tx = x + BOX / 2 - (vx + vw / 2) * s
    ty = BOX / 2 - (vy + vh / 2) * s
    defs, shapes = mark_body(p, "#000", gap)
    return f'''<defs>{defs}
    <mask id="{p}cut" maskUnits="userSpaceOnUse" x="{x}" y="0" width="{BOX}" height="{BOX}">
      <rect x="{x}" width="{BOX}" height="{BOX}" fill="#fff"/>
      <g transform="translate({tx:.2f} {ty:.2f}) scale({s:.5f})">{shapes}</g>
    </mask>
  </defs>
  <rect x="{x}" width="{BOX}" height="{BOX}" rx="{RADIUS}" fill="{INK}" mask="url(#{p}cut)"/>'''


def word_path(font_path, x, cap_height, baseline):
    font = TTFont(font_path)
    glyphs = font.getGlyphSet()
    cmap = font.getBestCmap()
    s = cap_height / font["OS/2"].sCapHeight
    pen = SVGPathPen(glyphs)
    cursor = 0.0
    for ch in WORD:
        name = cmap[ord(ch)]
        glyphs[name].draw(TransformPen(pen, (s, 0, 0, -s, x + cursor * s, baseline)))
        cursor += font["hmtx"][name][0]
    return pen.getCommands(), cursor * s


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--font", required=True, help="Roboto-Bold.ttf (Roboto 2.x, Apache-2.0)")
    a = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)
    head = '<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="{vb}" fill="none">\n  <title>Robo Architect</title>\n  '
    note = ("<!-- Generated by desktop/scripts/make-brand.py — edit that, not this. One colour (black on "
            "transparent); the mark is cut out of the box. -->\n  ")
    vx, vy, vw, vh = VIEW
    defs, shapes = mark_body("mk", INK, 30)
    with open(os.path.join(OUT, "ra-mark.svg"), "w") as f:
        f.write(head.format(w=vw, h=vh, vb=f"{vx} {vy} {vw} {vh}") + note.replace(" the mark is cut out of the box.", "")
                + f"<defs>{defs}</defs>\n  {shapes}\n</svg>\n")
    for name, gap in (("ra-box.svg", 30), ("ra-box-small.svg", 52)):
        with open(os.path.join(OUT, name), "w") as f:
            f.write(head.format(w=BOX, h=BOX, vb=f"0 0 {BOX} {BOX}") + note + box_svg("bx", gap) + "\n</svg>\n")
    cap = BOX * 0.42
    gap_x = BOX * 0.24
    d, width = word_path(a.font, BOX + gap_x, cap, BOX / 2 + cap / 2)
    total = round(BOX + gap_x + width + 4)
    with open(os.path.join(OUT, "ra-lockup.svg"), "w") as f:
        f.write(head.format(w=total, h=BOX, vb=f"0 0 {total} {BOX}") + note.replace("-->", "Wordmark: Roboto Bold (Apache-2.0) as outlines. -->")
                + box_svg("lk", 30) + f'\n  <path d="{d}" fill="{INK}"/>\n</svg>\n')
    os.makedirs(COPY_TO, exist_ok=True)
    for name in ("ra-mark.svg", "ra-box.svg", "ra-box-small.svg", "ra-lockup.svg"):
        shutil.copy(os.path.join(OUT, name), os.path.join(COPY_TO, name))
    print("ra-mark.svg, ra-box.svg, ra-box-small.svg, ra-lockup.svg", f"(lockup {total}×{BOX}) → {OUT} + {COPY_TO}")


if __name__ == "__main__":
    main()
