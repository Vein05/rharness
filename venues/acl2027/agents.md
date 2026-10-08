## Venue: acl2027

- Reviewed through ACL Rolling Review (ARR), January 2027 cycle. Deadline (AoE = UTC-12):
  ARR submission 2027-01-04 (OpenReview). The ACL commitment date is not announced yet; check
  https://2027.aclweb.org/calls/main/ and `rharness venue update`. Every author must register as a reviewer.
- Long papers: 8 pages of content. Short papers: 4 pages. `rharness lint` checks the long-paper limit;
  for a short paper, check 4 pages yourself. Limitations, ethical considerations, references, and
  appendices do not count.
- Build the PDF before checking: `rharness paper build`, or on Overleaf download the compiled PDF
  into `paper/main.pdf`.
- A section titled "Limitations", after the conclusion and before the references, is required;
  papers without one are desk rejected. It may not add new results.
- Double-blind. Load the style in review mode: put `\usepackage[review]{acl}` at the
  `% rharness:venue-style` line in `paper/main.tex`, and delete the scaffold's `\usepackage{hyperref}`
  and `\bibliographystyle{plain}` lines (acl.sty loads hyperref and natbib and sets `acl_natbib`).
  The style hides `\author` in review mode; keep acknowledgements, funding, and repository URLs out.
- Complete the Responsible NLP checklist in the submission form.
- Pre-submission playbook: `research/venue-acl2027.md` (archetype K, prefilled with the ARR review form).
