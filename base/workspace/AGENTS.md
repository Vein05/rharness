# Research workspace — agent orientation

This is the root of a set of research projects. Each subdirectory listed
below is an independent paper project with its own git repo, its own
`CHARTER.md` (the research contract), and its own `AGENTS.md` (start there).

## Projects

If this table and a project's own README disagree, the project's own docs
win — update this row to match.

| dir | paper | venue target | status |
|---|---|---|---|

<!-- rharness:begin base -->
## Scaffolding a new paper project

Run `rharness new <slug>` from anywhere inside this workspace. It creates
the directory, initialises git and Git LFS, writes the orientation files,
and adds a row to the table above. Then:

1. Fill in `CHARTER.md`: core question, thesis, in/out scope, success
   criterion, kill criterion. Do not proceed without a kill criterion.
2. Fill in `AGENTS.md`: what the project is, the repo map, known traps
   (even if "none yet"), infrastructure.
3. Write `spec/scoring.md` before any code: the headline table, its
   control and ceiling rows, and the rules that keep a win honest.
4. Write the first research doc. It is almost always a novelty scan
   (archetype E), a dataset source survey (C), or a cost estimate (F).
5. After the first working session, write `handoff/YYYY-MM-DD.md`.

## Research doc archetypes

When creating a new research doc, copy the matching skeleton from
`.rharness/archetypes/` and name the file after the thing it documents.

| Code | Archetype | When to use |
|---|---|---|
| A | Method spec | How a scorer, detector, or pipeline works and why it is defensible |
| B | Experiment report | One completed run, dated, never rewritten |
| C | Survey / registry | Auditing candidates: datasets, models, papers, tools |
| D | Audit log | Running catalog of what human inspection caught |
| E | Novelty / positioning | Prior-art check before committing to a framing |
| F | Cost / planning | Budgeting a model panel or experiment batch |
| G | Runbook | How to run things on specific infrastructure |
| H | Results ledger | Central table of every scored run |
| I | Taxonomy / theory | A classification that emerged from data |
| J | Audit + guidance pair | Corpus study with codebook and paper guidance |
| K | So-what playbook | Pre-submission strategy against reviewer objections |

## Cross-cutting rules

These apply to every project in this workspace.

1. **Kill criteria before spend.** No paid run without a kill criterion in
   `CHARTER.md` and a cost estimate in `research/`.
2. **Never rewrite history.** Handoffs, changelogs, and experiment reports
   are append-only. Correct by adding a dated note at the top.
3. **Numbers trace to versions.** Every reported number links to a scorer
   version and run provenance. Never copy rounded values between docs.
4. **Manual audit before belief.** Never report a detector's first output.
   Read hits, spot-check categories, check traces.
5. **Authoritative vs historical.** Each project's `AGENTS.md` lists which
   docs are current-state and which are dated records.
6. **Absolute dates only.** Never "last Thursday" in a persistent doc.
   Always `YYYY-MM-DD`.
7. **LFS for large files.** JSONL data, PDF papers, traces.
8. **Cost gates.** Frozen schema, complete manifest, exact cost estimate,
   smoke test, explicit user approval — all before a broad run.
9. **Spec before code.** A component gets a `spec/` file before its code;
   `spec/scoring.md` fixes the headline table before any run. Code without
   a spec is a probe and does not produce paper numbers.
10. **Prose follows `paper/writing.md`.** Living docs and the paper pass its
    three-reader test.

Run `rharness lint` to check every project against these rules.
<!-- rharness:end base -->
