## Venue: iclr2027

- Deadlines (AoE = UTC-12): abstract 2026-09-18, full paper 2026-09-25. `rharness venue` prints days remaining.
- Double-blind. No author names, affiliations, acknowledgements, funding notes, or repository URLs in the PDF.
  `rharness venue check` scans for git author names and the git remote.
- Main body limit applies before references and appendix. Build the PDF before checking:
  `rharness paper build`, or on Overleaf download the compiled PDF into `paper/main.pdf`.
- Load the style: add `\usepackage{iclr2027_conference}` at the `% rharness:venue-style` line in
  `paper/main.tex`; the style file is already in `paper/`.
- Pre-submission playbook: `research/venue-iclr2027.md` (archetype K, prefilled with the ICLR review form).
