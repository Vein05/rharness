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
