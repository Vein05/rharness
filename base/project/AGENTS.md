# {{title}} — agent orientation and execution rules

Start here. If something here contradicts an older doc, this file wins.

## What this project is

<!-- 2-3 sentences. Link to CHARTER.md. -->

See `CHARTER.md` (law).

## Repo map — authoritative vs historical

**Authoritative (keep current, trust these):**

| doc | role |
|---|---|
| `CHARTER.md` | core question, success and kill criteria |
| `spec/` | what we build, written before code; `spec/scoring.md` is the headline table |
| `research/README.md` | index of research docs |

**Historical (dated records — do NOT update numbers in them):**
`handoff/*`, `changelog/*`, `research/*_YYYY-MM-DD.md`.

**Known traps for new agents:**

- None recorded yet. Add the first misinterpretation you catch.

## Infrastructure

<!-- Compute hosts, API key environment variables (names only, never values),
     serve commands, version pins. -->

## Standing rules

1. Spec before code. A component gets a `spec/` file before its code. Code
   without a spec is a probe and does not produce paper numbers.
2. Prose follows `paper/writing.md`. Living docs and the paper pass its
   three-reader test.
3. Never report a detector's first output. Read hits, spot-check categories,
   check traces. Every catch becomes a regression test.
4. Every number traces to a scorer version and a run provenance.
5. Absolute dates only.
6. Read the newest `handoff/YYYY-MM-DD.md` at session start; write one at
   session end. Append to `changelog/YYYY-MM-DD.md` as you go.
7. Never copy, print, log, or commit credentials. `.env` is gitignored.

<!-- rharness:begin base -->
## Session protocol

1. Run `rharness brief` before anything else. It prints the charter status,
   the newest handoff, the last changelog entry, and open lint findings for
   this project. In Claude Code this runs automatically at session start.
2. Work inside the charter. If a task does not answer the core question,
   say so before doing it.
3. Before finishing: append to `changelog/YYYY-MM-DD.md`, write
   `handoff/YYYY-MM-DD.md`, and run `rharness lint`.

## Workspace rules

These apply to every project in the workspace; the root `AGENTS.md` is the
authority.

1. Kill criteria before spend: no paid run without a kill criterion in
   `CHARTER.md` and a cost estimate in `research/`.
2. Never rewrite history: handoffs, changelogs, and experiment reports are
   append-only; correct with a dated note.
3. Numbers trace to versions: every reported number links to a scorer
   version and a run; record frozen artifacts with `rharness hash`.
4. Manual audit before belief: never report a detector's first output.
5. Authoritative vs historical: the repo map above says which is which.
6. Absolute dates only.
7. LFS for data, papers, and traces.
8. Cost gates before any broad run: frozen schema, manifest, cost estimate,
   smoke test, explicit user approval.
9. Spec before code; `spec/scoring.md` first.
10. Prose follows `paper/writing.md`.
<!-- rharness:end base -->
