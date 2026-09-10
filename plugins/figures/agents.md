## Paper figures — use the central pipeline

All paper figures (main, summary, framework diagrams) are made with the
shared toolkit in `figures/`. Do NOT hand-roll figures elsewhere or paste
AI-generated raster images.

- Rules: `figures/AGENTS.md` (non-negotiables) and `figures/figure-style.md` (spec).
- Per-paper figures live in `figures/<paper-slug>/` with their own `src/`,
  `build/`, and Makefile (copy `figures/Makefile.template`); `make` runs the
  geometry and overflow checker automatically.
- Plots use `figures/paper.mplstyle`.
- Icons via `figures/get-icon.sh` (Iconify).
