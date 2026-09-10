# figures/ — paper-figure pipeline

Shared toolkit for main and summary figures across every paper in this
workspace. Goal: figures good enough to present, accurate enough to trust.

## Layout

- `figure-style.md` — the design spec every figure must follow. Read first.
- `AGENTS.md` — the short list of non-negotiables (`CLAUDE.md` includes it).
- `check_svg.py` — automated quality gate, runs on every `make`. Fails the
  build on text overflow, off-axis rows, arrows off the shared spine,
  asymmetric insets, non-standard strokes or radii, fonts below 22 px.
- `get-icon.sh` — fetch any Iconify icon as SVG into `assets/icons/`.
- `paper.mplstyle` — matplotlib style for plots (`plt.style.use(...)`).
- `Makefile.template` — copy into `figures/<paper-slug>/Makefile`.

## Workflow

1. Describe the figure: what it must communicate, and the source of truth
   for every number and label.
2. Draft `src/<paper>-<fig>.svg` following `figure-style.md`.
3. Loop: `make`, inspect `build/<fig>.png`, critique, edit the SVG, repeat.
4. Gate: the checklist at the bottom of `figure-style.md` (legibility at
   print size, greyscale via `make gray`, accuracy against the paper,
   `pdffonts` shows fonts embedded).
5. `\includegraphics{figures/build/<fig>.pdf}` in the paper.

Per-paper figures live in `figures/<paper-slug>/` with their own `src/`,
`build/`, and a Makefile that calls the shared `../check_svg.py`.

Requirements: Python 3 with Pillow, `rsvg-convert` (librsvg), `pdffonts`
(poppler), optional ImageMagick for greyscale checks, and the Inter font.
