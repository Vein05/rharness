# Figure pipeline — binding rules

Read `figure-style.md` BEFORE authoring or editing any figure. It is the spec;
this file is the short list of non-negotiables.

1. Vector only. Author SVG in `src/`, build with `make`. Never raster art,
   never AI-generated images, never mascots.
2. `make` runs `check_svg.py` and MUST pass before showing a figure to the user.
   Fix the SVG, not the checker.
3. Closed loop: render → visually inspect `build/*.png` → critique → fix.
   Never present an un-inspected figure. Also check greyscale (`make gray`)
   and print size before calling a figure done.
4. **BANNED: side/left color accent bars on cards.** Color goes in title text,
   tinted glyphs, or soft tinted fills.
5. Geometry: one margin grid, symmetric insets, identical peer elements,
   center-axis layout, one arrow spine. Fonts ≥ 22 px at 800 px column scale
   (≥ 23 px for anything that matters). Strokes 1.5 or 2.5 (uniform per
   figure), arrows 3.5. Radii 10/12/16 or pill.
6. Accuracy before polish: every label, number, and math symbol must be
   verified against the paper before styling. Numbers come from the paper,
   not from memory.
7. Icons via `./get-icon.sh prefix:name` (Iconify). Flat sets as accents only;
   brand icons (`logos:`) only when the figure refers to that system, never
   recolored.
