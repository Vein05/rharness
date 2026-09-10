# Figure Style Spec

Design language for all paper figures (main/summary/teaser diagrams). Derived from
the references in `references/` — CaMeL (DeepMind), Mem0, LLMs-Lost-in-Multi-Turn
(Microsoft), LoCoMo, BLT (Meta). Every figure must obey this spec; deviations need a
stated reason.

## Non-negotiables

- **Vector only.** Author figures as SVG, render to PDF via `make`. Never raster
  screenshots of diagrams; never AI-image-generated raster.
- **Closed loop.** No SVG ships without being rendered to PNG and visually inspected
  (alignment, overlap, arrow logic, crowding). Expect 5–10 critique cycles.
- **Accuracy gate.** Before polish, verify every label, number, and arrow against the
  paper's actual method/results. A beautiful wrong figure is worse than an ugly one.

## Typography

- Font: **match the paper's body font.** ACL/EMNLP template (`\usepackage{times}`)
  -> `font-family="Times New Roman"` on the SVG root (regular / bold / italic all
  installed; `check_svg.py` reads the root font-family and measures with the right
  metrics). For non-LaTeX contexts (slides, web) Inter remains the fallback.
- Sizes at final print scale (ACL single column ≈ 3.03 in wide):
  box labels ≥ 7 pt, panel titles 8–9 pt, annotations ≥ 6.5 pt. Nothing smaller than 6 pt.
- Panel tags: **(a) (b) (c)** bold in the figure font, sentence-case captions.
- No ALL-CAPS body labels; no italics except math symbols.

## Palette (pastel fill + darker same-hue stroke, colorblind-safe)

| Role | Fill | Stroke/Text |
|---|---|---|
| Primary / method | `#DBEAFE` | `#1D4ED8` |
| Secondary / data | `#DCFCE7` | `#15803D` |
| Warning / failure | `#FEE2E2` | `#B91C1C` |
| Highlight / result | `#FEF3C7` | `#B45309` |
| Neutral / container | `#F3F4F6` | `#4B5563` |
| Accent / query | `#F3E8FF` | `#7E22CE` |

- Grey text `#374151` for labels; pure black only for math.
- Max 4 hues per figure. Failure=red, success=green, method=blue — consistent across
  ALL figures in a paper.
- Must survive greyscale: pair color with shape/position, never color alone.

## Shapes & lines

- Rounded rects, radii 16/12/10 (containers/cards/chips), strokes 1.5 or 2.5
  (uniform per figure) — see Geometry rules. **No drop shadows, no gradients,
  no clip-art.**
- Containers (grouping boxes): neutral fill or none, dashed `4 3` stroke `#9CA3AF`
  when denoting scope/boundary.
- **BANNED: left/side accent bars on cards** (the thin colored strip — looks like a
  SaaS dashboard). Carry color through the title text, a tinted glyph, or a soft
  tinted card fill instead. `check_svg.py` enforces this.
- Stage/section panels may use very soft full-panel tints (e.g. `#FAF3E8`, `#EFF5FC`,
  `#FCF0F0`) with dashed sub-group boxes inside for readability; each sub-group gets
  a 48 px flat icon + title header.
- Arrows: `#4B5563`, 1.5 px, small solid triangle head (see template marker). Dashed
  arrows = optional/feedback paths only. Arrows never cross unless unavoidable;
  never overlap text.
- Spacing grid: 8 px. Align edges; equal gaps between siblings.

## Geometry rules (strict — run this audit before every render)

At 800 px = single column (multiply ×2.1 for 1680 px full-width figures):

- **One margin grid:** outer margin 20 px on ALL sides; full-width elements span
  exactly x=20..780. Sibling elements share left AND right edges — no ragged edges
  unless the element is semantically different (e.g., a chat bubble).
- **Insets:** container → child inset 20 px on every side (top = bottom, left = right).
  Text inside a card: 20 px from left edge, first baseline 32 px from top, subsequent
  baselines +32.
- **Gaps:** siblings 12 px apart inside a container, 20 px between top-level blocks.
- **Strokes:** exactly two widths per figure — 2.5 px for all boxes, 3.5 px for arrows.
  Never mix 2.5 and 3 on peer elements.
- **Radii:** three values only — 16 (containers), 12 (cards), 10 (inner chips).
- **Peer elements are identical:** same width, same height, same font size, same
  internal layout. Three verdict boxes = three clones with different content.
- **Arrows** start/end 6–10 px clear of box borders; never begin inside a container.
- **Center-item layout:** in a vertical-flow figure, every non-full-width item is
  horizontally centered on the figure's center axis (x = width/2), and ALL vertical
  flow arrows sit on that same axis. Attachments (tags like "= s(q)") count as part
  of the item group when centering. In a vertical-flow figure, band headers stay
  left-aligned with each other on the margin grid; in a multi-panel figure, each
  panel's header is centered on its panel's axis.
- Audit method: `make` runs `check_svg.py` automatically and fails on violations
  (text overflow, off-axis rows, off-spine arrows, asymmetric insets, stroke/radius
  drift, small fonts). Fix the SVG, not the checker — loosen a rule only with an
  explicit per-element opt-out class. Then confirm visually at 100% and print size.

## Composition patterns (steal from references)

- **Teaser (Fig. 1):** concept panel (left) + evidence mini-plot (right), like
  lost-multiturn-fig1. One sentence of takeaway inside the figure is allowed and good.
- **Pipeline:** left→right flow, stages as rounded rects, data as document/cylinder
  glyphs, like camel-fig1 / mem0-fig1.
- **Conversation:** chat bubbles (rounded, tail optional), user left / assistant
  right, session boundaries as dashed containers, like locomo-fig1.
- Figure width: design at 800 px = single column, 1660 px = full width (`figure*`).

## Energy vocabulary (liveliness without mascots or raster art)

All drawn vector, all in `src/template.svg` as copyable exemplars:

- **Span bracket** — |——— *label* ———| across a region; phases, latency, scope
  (the LightMem-style bracket). Color = the phase's semantic hue.
- **Loop-back arrow + N× pill** — curved return path for iteration/retry.
- **Spark accent** — small 4-point star pair marking THE novelty or result point.
  Max one per figure; amber only.
- **Stat badge** — amber pill with the one number that carries the story.
- **Verdict chips** — ✓/✗ pills (drawn glyphs, not emoji fonts).
- Flat icons (Iconify via `./get-icon.sh prefix:name`) as small accents in headers
  and labels — never as primary content. Brand icons (`logos:` set) only when the
  figure genuinely refers to that system; never recolor a brand mark.
- NO mascot characters, no AI-generated raster art, no clip-art scenes. Energy comes
  from color discipline + these annotations, not from illustrations.

## Plots (matplotlib)

- Use `paper.mplstyle` in this dir; export PDF. Same palette strokes as above.
- No chartjunk: no top/right spines, horizontal gridlines only, direct line labels
  preferred over legends when ≤ 4 series.

## Review checklist (before a figure is "done")

1. Rendered PNG inspected at 100% and at 50% (print size) — all text legible?
2. Greyscale render checked (`make gray`)?
3. Every element accurate w.r.t. the paper? Numbers match results tables?
4. Fonts embedded in PDF (`pdffonts build/<fig>.pdf` shows the figure font embedded)?
5. Consistent with the other figures in the same paper (palette, font sizes)?
