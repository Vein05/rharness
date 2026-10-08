# Issues and pull requests

How work is tracked in this repository. Issues live on GitHub
(`github.com/Vein05/rharness/issues`); this file is the format they follow.
The issue forms under `.github/ISSUE_TEMPLATE/` ask for the same sections.

## When to open an issue

- A bug: rharness does something other than what the spec
  (`docs/superpowers/specs/`) or the README says.
- Friction found while using rharness on a real project (label
  `source:dogfood`).
- A change that needs a decision before code (label `needs-design`).

Typos and one-line doc fixes go straight to a pull request.

## Format

Title: `<area>: <what is wrong or wanted>`, in plain words, for example
`brief: newest handoff is truncated from the top, hiding the latest decisions`.

Body, in this order. Leave out a section only when it does not apply.

1. **Problem.** What happens and what should happen instead. For a bug,
   include the exact command and output.
2. **Where.** `file:function` for the code involved, when known.
3. **Repro.** The smallest sequence of commands that shows it.
4. **Proposed fix.** Optional. If there are several options, list them
   with their trade-offs and say which one you would pick.
5. **Acceptance.** Testable statements: what a test asserts once this is
   fixed.
6. **Related.** Other issues and pull requests, by number.

Rules:

- Dates are absolute (`2026-10-07`), never "yesterday".
- Mark what was observed, what is inferred, and what is a guess.
- **This repository is public.** Never paste private research content into
  an issue: project data, unpublished results, costs, co-author names, or
  file paths under a home directory. Write "a dogfood project, 2026-10-07"
  and describe the mechanism, not the research.

## Labels

Give every issue one type label, at least one area label, and a priority
once it has been triaged.

| group | labels |
|---|---|
| type | `bug`, `enhancement`, `documentation`, `question` |
| area | `area:lint`, `area:brief`, `area:session`, `area:records`, `area:venue`, `area:paper`, `area:plugin`, `area:install` |
| priority | `priority:high` (breaks continuity or gives false reassurance), `priority:medium` (friction worth fixing soon) |
| status | `needs-design` (decide first; record the decision in the spec's revision notes), `good first issue`, `help wanted`, `duplicate`, `wontfix` |
| source | `source:dogfood` (found while using rharness on a real project) |

## Pull requests

- One concern per pull request. Write `Fixes #N` in the body when it closes
  an issue.
- Work that builds on unmerged work goes in a stack: the bottom pull
  request targets `main`, and each one above it targets the branch below.
  Use [`gh stack`](https://docs.github.com/en/pull-requests/get-started/about-stacked-prs):
  `gh stack link <bottom> ... <top>` for existing pull requests,
  `gh stack rebase` after a lower layer changes, and `gh stack merge` to
  merge from the bottom up.
- Every pull request says what changed, how it was tested (with the test
  count), and which docs it updated: README, spec section and revision
  note, `changelog/YYYY-MM-DD.md`.
- CI (`.github/workflows/ci.yml`) must pass on macOS and Ubuntu with
  Python 3.9 and 3.13.
