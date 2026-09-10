#!/usr/bin/env python3
"""Generate the rharness cover SVG. Brand marks are inlined from icons/ untouched."""
import math
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
ICONS = HERE / "icons"
OUT = HERE / "build" / "cover.svg"

W, H = 1800, 600
CX, CY = 900, 268          # logo centre
BLUE = "#2563EB"
BLUE_DARK = "#1D4ED8"
BLUE_SOFT = "#BFDBFE"
ORBIT = "#93C5FD"
NAVY = "#172554"
CHIP_STROKE = "#E5E7EB"

# (file, chip centre x, chip centre y, icon size)
CHIPS = [
    ("logos--openai-icon.svg", 560, 126, 60),
    ("logos--claude-icon.svg", 462, 270, 60),
    ("lobehub--gemini-color.svg", 596, 414, 60),
    ("logos--deepseek-icon.svg", 1240, 126, 66),
    ("logos--github-copilot.svg", 1338, 270, 64),
    ("logos--cursor-icon.svg", 1204, 414, 56),
]
CHIP_R = 54


def inline_icon(path: Path, x: float, y: float, size: float, idx: int) -> str:
    """Return the icon as a nested <svg> centred at (x, y) with its longest side = size."""
    text = path.read_text()
    m = re.search(r'viewBox="([\d.\s-]+)"', text)
    vx, vy, vw, vh = (float(v) for v in m.group(1).split())
    scale = size / max(vw, vh)
    w, h = vw * scale, vh * scale
    # make ids unique across inlined icons
    ids = set(re.findall(r'\bid="([^"]+)"', text))
    for i in ids:
        text = text.replace(f'id="{i}"', f'id="i{idx}_{i}"')
        text = text.replace(f"url(#{i})", f"url(#i{idx}_{i})")
        text = text.replace(f'href="#{i}"', f'href="#i{idx}_{i}"')
    text = re.sub(r"<title>.*?</title>", "", text, flags=re.S)
    inner = re.sub(r"^.*?<svg[^>]*>", "", text, count=1, flags=re.S)
    inner = re.sub(r"</svg>\s*$", "", inner, flags=re.S)
    return (f'<svg x="{x - w / 2:.1f}" y="{y - h / 2:.1f}" width="{w:.1f}" height="{h:.1f}" '
            f'viewBox="{vx:g} {vy:g} {vw:g} {vh:g}">{inner}</svg>')


def ellipse_point(cx, cy, rx, ry, rot_deg, t_deg):
    t, r = math.radians(t_deg), math.radians(rot_deg)
    x, y = rx * math.cos(t), ry * math.sin(t)
    return cx + x * math.cos(r) - y * math.sin(r), cy + x * math.sin(r) + y * math.cos(r)


def orbits():
    parts = []
    specs = [(CX, CY + 6, 470, 150, -7, (22, 158, 202, 338)),
             (CX, CY + 6, 320, 100, 9, (62, 242))]
    for cx, cy, rx, ry, rot, dots in specs:
        parts.append(f'<ellipse cx="{cx}" cy="{cy}" rx="{rx}" ry="{ry}" transform="rotate({rot} {cx} {cy})" '
                     f'fill="none" stroke="{ORBIT}" stroke-width="2.5" stroke-dasharray="6 8" '
                     f'class="no-center-check"/>')
        for t in dots:
            x, y = ellipse_point(cx, cy, rx, ry, rot, t)
            parts.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="9" fill="{BLUE_SOFT}"/>')
    return "\n".join(parts)


def logo():
    """Drafting compass inside a ring."""
    R = 138            # ring centre radius
    ring_w = 32
    px, py = CX, CY - R - 4        # pivot centre, sits on top of the ring
    leg_len = 284
    spread = 34                     # degrees from vertical
    parts = [
        f'<circle cx="{CX}" cy="{CY}" r="{R}" fill="none" stroke="{BLUE}" stroke-width="{ring_w}"/>',
    ]
    # tick marks on the inner side of the ring, left and right
    for side in (-1, 1):
        for k in range(-3, 4):
            ang = math.radians(90 * (1 - side) + k * 9 + (0 if side == 1 else 0))
            ang = math.radians((0 if side == 1 else 180) + k * 8)
            r0, r1 = R - ring_w / 2 - 6, R - ring_w / 2 - (22 if k % 2 == 0 else 14)
            x0, y0 = CX + r0 * math.cos(ang), CY + r0 * math.sin(ang)
            x1, y1 = CX + r1 * math.cos(ang), CY + r1 * math.sin(ang)
            parts.append(f'<line x1="{x0:.1f}" y1="{y0:.1f}" x2="{x1:.1f}" y2="{y1:.1f}" '
                         f'stroke="{BLUE}" stroke-width="3.5" stroke-linecap="round"/>')
    # legs: tapered quads from pivot to the tips, with a white halo so they read over the ring
    for side in (-1, 1):
        a = math.radians(90 + side * spread)
        tipx, tipy = px + leg_len * math.cos(a), py + leg_len * math.sin(a)
        nx, ny = -math.sin(a), math.cos(a)      # normal
        top_w, tip_w = 26, 6
        pts = [(px + nx * top_w, py + ny * top_w), (tipx + nx * tip_w, tipy + ny * tip_w),
               (tipx - nx * tip_w, tipy - ny * tip_w), (px - nx * top_w, py - ny * top_w)]
        d = " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
        parts.append(f'<polygon points="{d}" fill="{BLUE}" stroke="#FFFFFF" stroke-width="10" stroke-linejoin="round"/>')
    for side in (-1, 1):
        a = math.radians(90 + side * spread)
        tipx, tipy = px + leg_len * math.cos(a), py + leg_len * math.sin(a)
        nx, ny = -math.sin(a), math.cos(a)
        top_w, tip_w = 26, 6
        pts = [(px + nx * top_w, py + ny * top_w), (tipx + nx * tip_w, tipy + ny * tip_w),
               (tipx - nx * tip_w, tipy - ny * tip_w), (px - nx * top_w, py - ny * top_w)]
        d = " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
        parts.append(f'<polygon points="{d}" fill="{BLUE}"/>')
    # pivot head: rounded stem + hub with a hole
    x0, y0, w, h, r = px - 21, py - 62, 42, 66, 18
    stem = (f"M{x0 + r},{y0} h{w - 2 * r} a{r},{r} 0 0 1 {r},{r} v{h - r} h-{w} v-{h - r} "
            f"a{r},{r} 0 0 1 {r},-{r} z")
    parts.append(f'<path d="{stem}" fill="{BLUE}" stroke="#FFFFFF" stroke-width="10" stroke-linejoin="round"/>')
    parts.append(f'<circle cx="{px}" cy="{py}" r="46" fill="{BLUE}" stroke="#FFFFFF" stroke-width="10"/>')
    parts.append(f'<path d="M{px - 20},{py - 53} h40 v41 h-40 z" fill="{BLUE}"/>')  # fuse stem into hub
    parts.append(f'<circle cx="{px}" cy="{py}" r="15" fill="#FFFFFF"/>')
    # centre dot
    parts.append(f'<circle cx="{CX}" cy="{CY + 46}" r="24" fill="{BLUE}"/>')
    return "\n".join(parts)


def chips():
    parts = []
    for i, (name, x, y, size) in enumerate(CHIPS):
        parts.append(f'<circle cx="{x}" cy="{y}" r="{CHIP_R}" fill="#FFFFFF" stroke="{CHIP_STROKE}" stroke-width="2.5"/>')
        parts.append(inline_icon(ICONS / name, x, y, size, i))
    return "\n".join(parts)


def wordmark():
    return (f'<text x="{CX}" y="556" text-anchor="middle" font-family="Inter" font-weight="700" '
            f'font-size="112" letter-spacing="-3" fill="{NAVY}">rharness</text>')


svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" font-family="Inter">
<rect width="{W}" height="{H}" fill="#FFFFFF"/>
{orbits()}
{chips()}
{logo()}
{wordmark()}
</svg>
'''
OUT.parent.mkdir(exist_ok=True)
OUT.write_text(svg)
print(f"wrote {OUT}")
