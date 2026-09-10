#!/usr/bin/env python3
"""Generate the rharness cover SVG. Brand marks are inlined from icons/ untouched."""
import math
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
ICONS = HERE / "icons"
OUT = HERE / "build" / "cover.svg"

W, H = 1440, 680
CX, CY = 720, 258          # logo centre
BLUE = "#2563EB"
BLUE_DARK = "#1D4ED8"
BLUE_SOFT = "#BFDBFE"
ORBIT = "#93C5FD"
NAVY = "#172554"
CHIP_STROKE = "#E5E7EB"

# orbits: (cx, cy, rx, ry, rotation, dot angles)
ORBITS = [(CX, CY + 4, 430, 176, 0, (90, 150, 30)),
          (CX, CY + 4, 300, 104, 8, (60, 120, 240, 300))]
# chips: (file, orbit index, angle on that orbit, icon size)
CHIPS = [
    ("logos--openai-icon.svg", 0, 240, 74),
    ("logos--claude-icon.svg", 0, 180, 72),
    ("lobehub--gemini-color.svg", 0, 120, 74),
    ("logos--deepseek-icon.svg", 0, 300, 80),
    ("logos--github-copilot.svg", 0, 0, 78),
    ("logos--cursor-icon.svg", 0, 60, 68),
]
CHIP_R = 66


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
    for cx, cy, rx, ry, rot, dots in ORBITS:
        parts.append(f'<ellipse cx="{cx}" cy="{cy}" rx="{rx}" ry="{ry}" transform="rotate({rot} {cx} {cy})" '
                     f'fill="none" stroke="{ORBIT}" stroke-width="2.5" stroke-dasharray="6 8" '
                     f'class="no-center-check"/>')
        for t in dots:
            x, y = ellipse_point(cx, cy, rx, ry, rot, t)
            parts.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="9" fill="{BLUE_SOFT}"/>')
    return "\n".join(parts)


def logo():
    """Drafting compass inside a ring."""
    R = 108            # ring centre radius
    ring_w = 26
    px, py = CX, CY - R - 4        # pivot centre, sits on top of the ring
    leg_len = 222
    spread = 34                     # degrees from vertical
    parts = [
        f'<circle cx="{CX}" cy="{CY}" r="{R}" fill="none" stroke="{BLUE}" stroke-width="{ring_w}"/>',
    ]
    # tick marks on the inner side of the ring, left and right
    for side in (-1, 1):
        for k in range(-3, 4):
            ang = math.radians(90 * (1 - side) + k * 9 + (0 if side == 1 else 0))
            ang = math.radians((0 if side == 1 else 180) + k * 8)
            r0, r1 = R - ring_w / 2 - 5, R - ring_w / 2 - (18 if k % 2 == 0 else 11)
            x0, y0 = CX + r0 * math.cos(ang), CY + r0 * math.sin(ang)
            x1, y1 = CX + r1 * math.cos(ang), CY + r1 * math.sin(ang)
            parts.append(f'<line x1="{x0:.1f}" y1="{y0:.1f}" x2="{x1:.1f}" y2="{y1:.1f}" '
                         f'stroke="{BLUE}" stroke-width="3.5" stroke-linecap="round"/>')
    # legs: tapered quads from pivot to the tips, with a white halo so they read over the ring
    for side in (-1, 1):
        a = math.radians(90 + side * spread)
        tipx, tipy = px + leg_len * math.cos(a), py + leg_len * math.sin(a)
        nx, ny = -math.sin(a), math.cos(a)      # normal
        top_w, tip_w = 20, 5
        pts = [(px + nx * top_w, py + ny * top_w), (tipx + nx * tip_w, tipy + ny * tip_w),
               (tipx - nx * tip_w, tipy - ny * tip_w), (px - nx * top_w, py - ny * top_w)]
        d = " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
        parts.append(f'<polygon points="{d}" fill="{BLUE}" stroke="#FFFFFF" stroke-width="8" stroke-linejoin="round"/>')
    for side in (-1, 1):
        a = math.radians(90 + side * spread)
        tipx, tipy = px + leg_len * math.cos(a), py + leg_len * math.sin(a)
        nx, ny = -math.sin(a), math.cos(a)
        top_w, tip_w = 20, 5
        pts = [(px + nx * top_w, py + ny * top_w), (tipx + nx * tip_w, tipy + ny * tip_w),
               (tipx - nx * tip_w, tipy - ny * tip_w), (px - nx * top_w, py - ny * top_w)]
        d = " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
        parts.append(f'<polygon points="{d}" fill="{BLUE}"/>')
    # pivot head: rounded stem + hub with a hole
    x0, y0, w, h, r = px - 16, py - 50, 32, 54, 14
    stem = (f"M{x0 + r},{y0} h{w - 2 * r} a{r},{r} 0 0 1 {r},{r} v{h - r} h-{w} v-{h - r} "
            f"a{r},{r} 0 0 1 {r},-{r} z")
    parts.append(f'<path d="{stem}" fill="{BLUE}" stroke="#FFFFFF" stroke-width="8" stroke-linejoin="round"/>')
    parts.append(f'<circle cx="{px}" cy="{py}" r="36" fill="{BLUE}" stroke="#FFFFFF" stroke-width="8"/>')
    parts.append(f'<path d="M{px - 15},{py - 42} h30 v32 h-30 z" fill="{BLUE}"/>')  # fuse stem into hub
    parts.append(f'<circle cx="{px}" cy="{py}" r="12" fill="#FFFFFF"/>')
    # centre dot
    parts.append(f'<circle cx="{CX}" cy="{CY + 36}" r="19" fill="{BLUE}"/>')
    return "\n".join(parts)


def chips():
    parts = []
    for i, (name, orbit, angle, size) in enumerate(CHIPS):
        cx, cy, rx, ry, rot, _ = ORBITS[orbit]
        x, y = ellipse_point(cx, cy, rx, ry, rot, angle)
        x, y = round(x, 1), round(y, 1)
        parts.append(f'<circle cx="{x}" cy="{y}" r="{CHIP_R}" fill="#FFFFFF" stroke="{CHIP_STROKE}" stroke-width="2.5"/>')
        parts.append(inline_icon(ICONS / name, x, y, size, i))
    return "\n".join(parts)


def wordmark():
    return (f'<text x="{CX}" y="634" text-anchor="middle" font-family="Inter" font-weight="700" '
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
