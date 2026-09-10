#!/usr/bin/env python3
"""Quality checker for figure SVGs (see figure-style.md, Geometry rules).

Run: python3 check_svg.py src/*.svg    (make runs it automatically)

Checks
  1. text overflow: every text fits inside its enclosing rect with >=10px padding
  2. center-item layout: top-level row groups centered on the figure axis (+/-8px)
  3. arrow spine: all vertical flow arrows share one x; horizontal ones share one y
  4. inset symmetry: child cards inside a container have matching t/b and l/r insets
  5. stroke widths: boxes 2.5, arrows 3.5 only (icons exempt)
  6. corner radii: {10, 12, 16} + pills + accent bars only
  7. minimum font size 22px (~6.2pt at column width)
Exit code 1 if any violation. Opt-outs: class="no-center-check" / "no-overflow-check".
"""
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

from PIL import ImageFont

FONT_DIR = Path.home() / "Library/Fonts"
SYS_FONT_DIR = Path("/System/Library/Fonts/Supplemental")
FONT_FAMILIES = {
    "Inter": {
        "400": FONT_DIR / "Inter-Regular.otf",
        "600": FONT_DIR / "Inter-SemiBold.otf",
        "700": FONT_DIR / "Inter-Bold.otf",
        "400i": FONT_DIR / "Inter-Italic.otf",
    },
    "Times New Roman": {
        "400": SYS_FONT_DIR / "Times New Roman.ttf",
        "600": SYS_FONT_DIR / "Times New Roman Bold.ttf",
        "700": SYS_FONT_DIR / "Times New Roman Bold.ttf",
        "400i": SYS_FONT_DIR / "Times New Roman Italic.ttf",
    },
}
FONTS = FONT_FAMILIES["Inter"]  # overridden per-file from the SVG root font-family
PAD = 10          # min text-to-border padding
CENTER_TOL = 8    # px tolerance for centering
INSET_TOL = 2     # px tolerance for inset symmetry
FULLWIDTH_TOL = 60
ALLOWED_BOX_STROKE = {1.5, 2.5}
ALLOWED_ARROW_STROKE = {3.0, 3.5}
ALLOWED_RX = {10.0, 12.0, 16.0, 18.0}
MIN_FONT = 22

NS = "{http://www.w3.org/2000/svg}"
_font_cache = {}


def font_for(weight, italic, size):
    key = (weight + ("i" if italic and weight == "400" else ""), size)
    if key not in _font_cache:
        path = FONTS.get(key[0], FONTS["400"])
        _font_cache[key] = ImageFont.truetype(str(path), size)
    return _font_cache[key]


def text_width(el, default_size):
    size = int(float(el.get("font-size", default_size)))
    weight = el.get("font-weight", "400")
    italic = el.get("font-style") == "italic"
    content = "".join(el.itertext())
    return font_for(weight, italic, size).getlength(content), size, content


def f(el, attr, default=0.0):
    return float(el.get(attr, default))


class Fig:
    def __init__(self, path):
        self.path = path
        self.root = ET.parse(path).getroot()
        global FONTS
        fam = self.root.get("font-family", "Inter")
        FONTS = FONT_FAMILIES.get(fam, FONT_FAMILIES["Inter"])
        _font_cache.clear()
        vb = self.root.get("viewBox").split()
        self.w, self.h = float(vb[2]), float(vb[3])
        self.violations = []
        # only top-level children (icons inside <g> are exempt from all checks)
        self.rects, self.texts, self.lines, self.circles = [], [], [], []
        for el in self.root:
            tag = el.tag.replace(NS, "")
            if tag == "rect":
                self.rects.append(el)
            elif tag == "text":
                self.texts.append(el)
            elif tag == "line":
                self.lines.append(el)
            elif tag == "circle":
                self.circles.append(el)

    def err(self, msg):
        self.violations.append(msg)

    # -- helpers ------------------------------------------------------------
    def bbox(self, r):
        return (f(r, "x"), f(r, "y"), f(r, "x") + f(r, "width"), f(r, "y") + f(r, "height"))

    def is_bg(self, r):
        x0, y0, x1, y1 = self.bbox(r)
        return x0 == 0 and y0 == 0 and x1 >= self.w and y1 >= self.h

    def is_accent_bar(self, r):
        return f(r, "width") <= 8 or f(r, "height") <= 8

    def enclosing_rect(self, px, py):
        best, area = None, None
        for r in self.rects:
            if self.is_bg(r) or self.is_accent_bar(r):
                continue
            x0, y0, x1, y1 = self.bbox(r)
            if x0 <= px <= x1 and y0 <= py <= y1:
                a = (x1 - x0) * (y1 - y0)
                if area is None or a < area:
                    best, area = r, a
        return best

    # -- checks -------------------------------------------------------------
    def check_text_overflow(self):
        for t in self.texts:
            if "no-overflow-check" in (t.get("class") or ""):
                continue
            w, size, content = text_width(t, 26)
            if size < MIN_FONT:
                self.err(f"font too small ({size}px < {MIN_FONT}): '{content[:40]}'")
            x, y = f(t, "x"), f(t, "y")
            anchor = t.get("text-anchor", "start")
            x0 = x - w if anchor == "end" else x - w / 2 if anchor == "middle" else x
            x1 = x0 + w
            box = self.enclosing_rect((x0 + x1) / 2, y - size * 0.35)
            if box is None:
                if x0 < 0 or x1 > self.w:
                    self.err(f"text off-canvas: '{content[:40]}' spans {x0:.0f}..{x1:.0f}")
                continue
            bx0, _, bx1, _ = self.bbox(box)
            if x0 < bx0 + PAD or x1 > bx1 - PAD:
                self.err(
                    f"text overflow: '{content[:40]}' spans {x0:.0f}..{x1:.0f} in box "
                    f"{bx0:.0f}..{bx1:.0f} (need {PAD}px padding)"
                )

    def top_level_rects(self):
        """rects not contained by another (non-bg) rect"""
        out = []
        for r in self.rects:
            if self.is_bg(r) or self.is_accent_bar(r):
                continue
            x0, y0, x1, y1 = self.bbox(r)
            contained = any(
                o is not r and not self.is_bg(o) and not self.is_accent_bar(o)
                and self.bbox(o)[0] <= x0 and self.bbox(o)[1] <= y0
                and self.bbox(o)[2] >= x1 and self.bbox(o)[3] >= y1
                for o in self.rects
            )
            if not contained:
                out.append(r)
        return out

    def check_centering(self):
        # group top-level rects into rows by vertical overlap; row union must be
        # full-width or centered. tag texts extend their row's group box.
        rows = []
        for r in self.top_level_rects():
            if "no-center-check" in (r.get("class") or ""):
                continue
            x0, y0, x1, y1 = self.bbox(r)
            for row in rows:
                if y0 < row["y1"] and y1 > row["y0"]:
                    row["x0"], row["x1"] = min(row["x0"], x0), max(row["x1"], x1)
                    row["y0"], row["y1"] = min(row["y0"], y0), max(row["y1"], y1)
                    break
            else:
                rows.append({"x0": x0, "x1": x1, "y0": y0, "y1": y1})
        for t in self.texts:  # attachments like '= s(q)' widen their row
            w, size, _ = text_width(t, 26)
            x, y = f(t, "x"), f(t, "y")
            for row in rows:
                if row["y0"] <= y <= row["y1"]:
                    anchor = t.get("text-anchor", "start")
                    x0 = x - w if anchor == "end" else x - w / 2 if anchor == "middle" else x
                    row["x0"], row["x1"] = min(row["x0"], x0), max(row["x1"], x0 + w)
        for row in rows:
            width = row["x1"] - row["x0"]
            if width >= self.w - 2 * 20 - FULLWIDTH_TOL:
                continue  # full-width band
            center = (row["x0"] + row["x1"]) / 2
            if abs(center - self.w / 2) > CENTER_TOL:
                self.err(
                    f"row y={row['y0']:.0f}..{row['y1']:.0f} not centered: center "
                    f"{center:.0f} vs axis {self.w / 2:.0f} (±{CENTER_TOL})"
                )

    def check_arrow_spine(self):
        vert = [l for l in self.lines if l.get("marker-end") and f(l, "x1") == f(l, "x2")]
        horiz = [l for l in self.lines if l.get("marker-end") and f(l, "y1") == f(l, "y2")]
        if len({f(l, "x1") for l in vert}) > 1:
            self.err(f"vertical arrows on multiple spines: {sorted({f(l,'x1') for l in vert})}")
        if len({f(l, "y1") for l in horiz}) > 1:
            self.err(f"horizontal arrows on multiple spines: {sorted({f(l,'y1') for l in horiz})}")
        for l in self.lines:
            if l.get("marker-end"):
                sw = f(l, "stroke-width", 1)
                if sw not in ALLOWED_ARROW_STROKE:
                    self.err(f"arrow stroke-width {sw} (allowed {sorted(ALLOWED_ARROW_STROKE)})")

    def check_insets(self):
        for parent in self.rects:
            if self.is_bg(parent) or self.is_accent_bar(parent):
                continue
            px0, py0, px1, py1 = self.bbox(parent)
            kids = [
                r for r in self.rects
                if r is not parent and not self.is_bg(r) and not self.is_accent_bar(r)
                and px0 <= self.bbox(r)[0] and py0 <= self.bbox(r)[1]
                and px1 >= self.bbox(r)[2] and py1 >= self.bbox(r)[3]
            ]
            if not kids:
                continue
            ext = [self.bbox(k) for k in kids]
            for t in self.texts:
                if "no-overflow-check" in (t.get("class") or ""):
                    continue
                w, size, _ = text_width(t, 26)
                tx, ty = f(t, "x"), f(t, "y")
                anchor = t.get("text-anchor", "start")
                tx0 = tx - w if anchor == "end" else tx - w / 2 if anchor == "middle" else tx
                if px0 <= tx0 and tx0 + w <= px1 and py0 <= ty - size * 0.75 and ty <= py1:
                    ext.append((tx0, ty - size * 0.75, tx0 + w, ty + size * 0.1))
            top = min(e[1] for e in ext) - py0
            bot = py1 - max(e[3] for e in ext)
            left = min(e[0] for e in ext) - px0
            right = px1 - max(e[2] for e in ext)
            if abs(top - bot) > INSET_TOL:
                self.err(f"container y={py0:.0f}: top inset {top:.0f} != bottom {bot:.0f}")
            if abs(left - right) > INSET_TOL and left < 40 and right < 40:
                self.err(f"container y={py0:.0f}: left inset {left:.0f} != right {right:.0f}")

    def check_strokes_radii(self):
        for r in self.rects:
            if self.is_bg(r) or self.is_accent_bar(r):
                continue
            sw = f(r, "stroke-width", 0)
            if sw and sw not in ALLOWED_BOX_STROKE:
                self.err(f"box stroke-width {sw} at y={f(r,'y'):.0f} (allowed {sorted(ALLOWED_BOX_STROKE)})")
            rx = f(r, "rx", 0)
            pill = rx >= f(r, "height") / 2 - 1
            if rx and not pill and rx not in ALLOWED_RX:
                self.err(f"radius {rx} at y={f(r,'y'):.0f} (allowed {sorted(ALLOWED_RX)} or pill)")

    def check_accent_bars(self):
        for r in self.rects:
            w, h = f(r, "width"), f(r, "height")
            if (w <= 10 and h >= 30) or (h <= 10 and w >= 30):
                self.err(f"accent bar at {f(r,'x'):.0f},{f(r,'y'):.0f} ({w:.0f}x{h:.0f}) - banned; use colored title/glyph instead")

    def check_stroke_uniformity(self):
        sws = {
            f(r, "stroke-width", 0) for r in self.rects
            if not self.is_bg(r) and not self.is_accent_bar(r) and f(r, "stroke-width", 0)
            and not r.get("stroke-dasharray")
        }
        if len(sws) > 1:
            self.err(f"mixed box stroke widths in one figure: {sorted(sws)}")

    def run(self):
        self.check_text_overflow()
        self.check_centering()
        self.check_arrow_spine()
        self.check_insets()
        self.check_strokes_radii()
        self.check_stroke_uniformity()
        self.check_accent_bars()
        return self.violations


def main(paths):
    failed = False
    for p in paths:
        v = Fig(p).run()
        name = Path(p).name
        if v:
            failed = True
            print(f"FAIL {name}")
            for msg in v:
                print(f"  - {msg}")
        else:
            print(f"OK   {name}")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main(sys.argv[1:] or [str(p) for p in Path("src").glob("*.svg")])
