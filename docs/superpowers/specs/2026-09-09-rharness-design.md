# rharness — design

Status: approved in chat 2026-09-09. Authority for version one.
Sections 10 to 12 approved in chat 2026-09-10; they are the scope of 0.3.0.

## 1. What this is

A one-command setup for ML/NLP researchers who use coding agents. It writes
the markdown contracts and scripts that make an agent-driven research
workspace disciplined: a charter with a kill criterion per paper, an agent
orientation file, daily handoffs and changelogs, spec-before-code, dated
experiment reports, and a lint that reports drift. It is markdown and
scripts, not an app.

Source material: the `~/Documents/research` workspace, distilled from four
published or submitted papers. Personal names, deadlines, lab hosts, and
project specifics are stripped.

Targets for version one: Claude Code and Codex. `AGENTS.md` is the shared
source of truth; `CLAUDE.md` is a one-line include. Claude Code additionally
gets skills and hooks through plugins; Codex gets only markdown and scripts.

Non-goals for version one: Cursor and Gemini adapters, a plugin registry
outside this repo, any web UI, restyling the figures toolkit.

## 2. Repository layout

```
rharness/
  install.sh                  curl target; bash; downloads a release, links the CLI
  bin/rharness                six-line entrypoint; adds lib/ to sys.path
  lib/rharness/               Python 3.9+ stdlib package, no pip dependencies:
                              cli, templates, manifest, regions, workspace, gitutil,
                              plugin, lint, lintcfg, doctor, update, brief, session
  base/
    workspace/
      AGENTS.md               root orientation with managed region
      CLAUDE.md               "@AGENTS.md" include
      lint.toml               lint thresholds (handoff staleness days, etc.)
    project/
      CHARTER.md  AGENTS.md  README.md  .gitignore  .gitattributes  requirements.txt
      spec/README.md  spec/scoring.md
      research/README.md
      paper/writing.md  paper/Makefile  paper/main.tex  paper/references.bib
      data/README.md  papers/INDEX.md
      handoff/README.md  changelog/README.md
      tests/.gitkeep  tools/.gitkeep
    archetypes/
      A-method-spec.md  B-experiment-report.md  C-survey-registry.md
      D-audit-log.md  E-novelty-positioning.md  F-cost-planning.md
      G-runbook.md  H-results-ledger.md  I-taxonomy-theory.md
      J-audit-guidance-pair.md  K-so-what-playbook.md
  plugins/
    rtk/  figures/  review-panel/  wandb/  ideas/
  venues/                     project-scoped venue packages, fetched on demand, not in the tarball
    INDEX.json  iclr2027/
  tests/                      pytest
  docs/superpowers/specs/     this file
  README.md  LICENSE (MIT)  VERSION
```

Every file under `base/` and `plugins/*/files/` is a template. Templates use
`{{slug}}`, `{{title}}`, `{{date}}`, and `{{workspace}}` placeholders only.
No other templating.

## 3. Install and update

`curl -fsSL https://raw.githubusercontent.com/Vein05/rharness/main/install.sh | sh`

`install.sh`:

1. Requires `curl`, `tar`, `python3` >= 3.9. Exits with a message naming the
   missing one.
2. Resolves the latest release tag from the GitHub API, or uses
   `RHARNESS_VERSION` if set.
3. Downloads the release tarball to `~/.rharness/store/<version>/` (override
   with `RHARNESS_HOME`).
4. Writes `~/.rharness/bin/rharness`, a two-line shim that execs
   `python3 "$RHARNESS_HOME/store/current/bin/rharness" "$@"`, and points the
   `current` symlink at the version.
5. Appends `export PATH="$HOME/.rharness/bin:$PATH"` to the shell rc
   (`.zshrc`, `.bashrc`, or `.profile`, whichever exists first) if not
   already present, guarded by a marker comment.
6. Prints next steps: `rharness init ~/research`.

`rharness update` repeats steps 2 to 4 and then re-applies managed files in
the current workspace per section 5.

Idempotent: running `install.sh` twice is a no-op except for a newer version.

## 4. CLI

`bin/rharness` dispatches to `lib/rharness/cli.py`. Subcommands:

| Command | Behavior |
|---|---|
| `init [dir]` | Creates a workspace in `dir` (default `.`). Writes `base/workspace/*`, `.rharness/manifest.json`, then runs `add rtk`. Refuses if a manifest already exists; suggests `adopt`. |
| `new <slug> [--title T]` | Inside a workspace. Creates `dir/<slug>/` from `base/project/`, substitutes placeholders, `git init`, `git lfs install --local`, writes `handoff/<date>.md` stub, appends a row to the root `AGENTS.md` project table, records files in the manifest. |
| `adopt [dir]` | Detects whether `dir` is a workspace (has a root `AGENTS.md` and subdirectories with `CHARTER.md`) or a project. Adds every missing managed file, never overwrites an existing one, writes the manifest, prints what was added and what was skipped. |
| `add <plugin>` | Copies `plugins/<name>/files/` into the workspace, inserts the plugin's `agents.md` snippet as a marked region in the root `AGENTS.md`, applies harness extras (section 6), runs the plugin's `setup` script if present, records the plugin in the manifest. |
| `remove <plugin>` | Deletes the files the manifest attributes to the plugin if unmodified, removes its marked region, unregisters harness extras. Modified files are left and listed. |
| `lint [dir]` | Section 7. Exit 0 clean, 1 findings, 2 error. `--json` for machine output. |
| `doctor` | Machine checks: python version, git, git-lfs, rtk binary on PATH, RTK hook present in the effective Claude Code settings, session hooks, workspace manifest readable. Exit 1 on any failed check. Optional tools (`latexmk`, `pdfinfo`, `pdftotext`) are printed as notes with a third state that never affects the exit code. |
| `update` | Section 3, then re-applies managed files on the current workspace; `--no-fetch` does only the re-apply. |
| `list` | Installed plugins, available plugins, versions. |
| `version` | Prints the store version. |
| `brief [project]` | Orientation bundle for a fresh session: charter status, newest handoff, last changelog entry, authoritative docs, lint findings. Workspace table when run at the root. |
| `session-check` | Stop-hook check: a project touched today must have today's handoff and changelog; emits a block decision otherwise. |
| `hash <paths> [--note N]` | Records frozen artifacts in `research/PROVENANCE.md` with sha16, size, date, and code commit. Lint errors when a recorded file changes or disappears. |
| `plugin new <name>` | Scaffolds a plugin directory. |
| `venue` | Section 10. Bare `venue` prints status. Subcommands `add`, `change`, `lock`, `unlock`, `check [--build]`, `update`, `remove`, `list`. `--project <slug>` names the project from outside one. |
| `paper build` | Section 11. Runs the LaTeX build in `paper/`; with TinyTeX present, installs missing packages through `tlmgr`. |

Global flags: `--workspace <dir>` to override discovery (walk up from cwd
until a `.rharness/manifest.json` is found), `--dry-run` for every writing
command, `--yes` to skip confirmations.

Exit codes: 0 success, 1 findings or refusal, 2 usage or environment error.

## 5. Managed files and the manifest

`.rharness/manifest.json` at the workspace root:

```json
{
  "rharness_version": "0.1.0",
  "created": "2026-09-09",
  "plugins": ["rtk"],
  "files": {
    "AGENTS.md": {"sha256": "...", "owner": "base", "region": true},
    "seam/CHARTER.md": {"sha256": "...", "owner": "base"},
    "figures/check_svg.py": {"sha256": "...", "owner": "plugin:figures"}
  }
}
```

Rules:

- On `update` (or `update --no-fetch`), for each managed file: if the on-disk hash equals
  the recorded hash, replace with the new template and record the new hash.
  If it differs, leave it, print a unified diff to the new template, and
  keep the old hash. `--force` overwrites after backing up to
  `.rharness/backup/<date>/`.
- Region files (`AGENTS.md`, `CLAUDE.md`) are never replaced whole. rharness
  owns text between `<!-- rharness:begin base -->` and
  `<!-- rharness:end base -->`, and each plugin owns
  `<!-- rharness:begin plugin:<name> -->` … `<!-- rharness:end plugin:<name> -->`.
  Update rewrites only inside markers. Text outside markers is the user's.
  From 0.3.0 the manifest's `region` field records the region name, not a
  boolean, so a project-scoped plugin region can be refreshed; the shipped
  code hardcodes `base`.
- `adopt` never overwrites. It only adds missing files and records hashes
  for files it wrote. Existing files are recorded with `"owner": "user"` so
  later updates skip them.
- Paper projects that are their own git repos get a `.rharness/project.json`
  with the same shape scoped to that project. The workspace manifest lists
  projects; project manifests list the project's files.

## 6. Plugins

Directory `plugins/<name>/`:

```
plugin.json
agents.md           snippet inserted into the root AGENTS.md managed region
files/              copied into the workspace root, paths preserved
project-files/      optional; copied into each project on `new` and `adopt`
claude/skills/<skill>/SKILL.md     optional; Claude Code only
claude/hooks.json                  optional; Claude Code only
setup.sh            optional; run after files are copied, may install binaries
```

`plugin.json`:

```json
{
  "name": "rtk",
  "description": "Token-saving command rewriter for Claude Code",
  "version": "0.1.0",
  "harness": ["claude"],
  "requires": {"binaries": ["rtk"], "python": ">=3.9"}
}
```

Optional fields added in 0.3.0: `"scope": "workspace" | "project"` (default
`workspace`) and `"kind": "venue"`. A project-scoped plugin installs into
exactly one project: its `project-files/` go into that project, its
`agents.md` becomes a `plugin:<name>` region in that project's `AGENTS.md`,
and its files are recorded in that project's `.rharness/project.json`,
not the workspace manifest. `files/` and `claude/` are ignored for
project-scoped plugins. A project-scoped plugin is never added to the
workspace manifest's `plugins` list, so it is never re-applied to other
projects by `new` or `adopt`. Plain `rharness add` refuses a `scope:
project` plugin with exit 2 and points at `rharness venue add`. Section 10
is the only user of this in 0.3.0.

Harness adapters:

- **claude**: copies `claude/skills/*` to `<workspace>/.claude/skills/`,
  deep-merges `claude/hooks.json` into `<workspace>/.claude/settings.json`
  (creating it if absent, never deleting keys it did not add, tracking added
  hook entries in the manifest so `remove` can drop them), and ensures
  `CLAUDE.md` exists with `@AGENTS.md`.
- **codex**: no extras. `AGENTS.md` plus copied files only.

Harness is chosen at `init` with `--harness claude,codex` (default: both)
and stored in the manifest. Plugins whose `harness` list does not intersect
are still installed for their markdown and files; only the extras are
skipped.

Plugins in version one:

| Plugin | Default | Contents |
|---|---|---|
| `rtk` | yes | `setup.sh` installs rtk via Homebrew or cargo if missing; `files/.rharness/hooks/rtk-rewrite.sh`; `claude/hooks.json` with the PreToolUse Bash hook; `agents.md` with the RTK usage note. `doctor` verifies the hook is present in the effective settings. |
| `figures` | no | The `figures/` toolkit copied as-is: `CLAUDE.md`, `figure-style.md`, `check_svg.py`, `get-icon.sh`, `paper.mplstyle`, a `Makefile` template. `agents.md` says figures come from the central pipeline. |
| `review-panel` | no | `review-panel/` package, `config.yaml`, `panels/`, `prompts/`, spending-policy `CLAUDE.md`. Requires the user to supply API keys; `setup.sh` prints that. |
| `wandb` | no | `agents.md` snippet with the W&B tracking rules; `project-files/tools/wandb_init.py` helper. |
| `ideas` | no | `ideas/README.md` backlog format and one example entry with the scoop-pulse fields. |

## 7. Lint

Reads `lint.toml` for thresholds. Defaults: handoff may be at most 1 day
older than the newest commit; dirty-tree warning above 0 files; changelog
required for every commit day in the last 14 days; word caps of 600
(CHARTER.md), 600 (newest handoff), 400 (last `## ` entry of the newest
changelog file), and 1500 (`rharness brief <project>` without its lint
section). Words exclude HTML comments and tokens with no letter or digit.
The caps are provisional: set from the scaffold and this repository's own
changelog, not yet from a dogfood project.

Per project (each subdirectory with `CHARTER.md`):

| Check | Severity |
|---|---|
| Required files present: CHARTER.md, AGENTS.md, README.md, spec/README.md, paper/writing.md, handoff/, changelog/ | error |
| CHARTER.md has a `## Kill Criterion` section with a `Status:` line | error |
| Every `spec/*.md` opens with `Status: proposed|frozen|superseded` and a date | error |
| Git repo exists and has at least one commit | error |
| Working tree clean | warning |
| Newest `handoff/YYYY-MM-DD.md` not older than newest commit by more than threshold | warning |
| `changelog/YYYY-MM-DD.md` exists for each commit day in window | warning |
| `.gitattributes` has LFS rules for `data/*.jsonl`, `papers/*.pdf`, `traces/**` | warning |
| `.env` present and gitignored, or absent | error if present and not ignored |
| No relative-date phrases (`last week`, `yesterday`, `next Thursday`, …) in CHARTER.md, AGENTS.md, spec/, handoff/ | warning |
| `paper/writing.md` generic sections match the template hash | warning |
| `research/PROVENANCE.md` present; every recorded artifact exists with its recorded hash | error |
| Unrecorded files under `traces/` | warning |
| Kill criterion body states a threshold, not only a Status line; core question non-empty | error / warning |
| `spec/scoring.md` has `control` and `ceiling` rows | error |
| Experiment reports (archetype B) exist while `spec/scoring.md` is still `proposed` | warning |
| Source files exist but no component spec besides `scoring.md` | warning |
| Word cap exceeded on CHARTER.md, the newest handoff, the last changelog entry, or the project brief | warning; error over twice the cap; `0` disables |
| Bibliography, for a project with no venue and a `paper/references.bib`: citation keys resolve, duplicate keys, malformed entries (not closed, no key, unreadable fields, no title), the same DOI under two keys, entries never cited (one summary row; none when `\nocite{*}`) | warning |
| Venue checks (section 10.7): generic set from the binary plus the package's `checks.py`; severity as returned when locked, downgraded to warning when targeted | package-defined |
| Venue locked, primary deadline within 14 days, success criterion still `NOT YET` | warning |
| Any venue deadline in the past | warning |
| `paper/main.pdf` missing, or older than any `paper/*.tex`, `*.bib`, `*.sty`, or `*.cls`, when a venue check needs it | warning |

Workspace:

| Check | Severity |
|---|---|
| Root `AGENTS.md` project table rows correspond to existing directories, and every project directory has a row | warning |
| No `.zip`, `.pdf`, or `tmp*` entries at the workspace root | warning |
| Manifest parses and every recorded file exists | error |

Output: one line per finding, `<severity> <project>/<path>: <message>`,
grouped by project, summary counts at the end. `--json` emits a list of
objects with the same fields.

Exit status: 1 when any finding is at or above `fail_on`, else 0; 2 on a
usage or configuration error. `fail_on` is `warning` (the default: any
finding fails) or `error` (warnings print but do not fail). `--fail-on`
overrides the `lint.toml` value.

## 8. Testing

- `tests/test_cli.py`: each subcommand against a `tmp_path` workspace,
  asserting on the file tree, manifest contents, marker regions, and exit
  codes. Update-with-user-edit and remove-with-modified-file are explicit
  cases.
- `tests/test_lint.py`: fixtures that violate each check exactly once.
- `tests/test_install.bats`: runs `install.sh` against a fake `HOME` with a
  local tarball served from a temp dir via `python3 -m http.server`.
- `tests/test_venue.py`: a fixture venue package copied from
  `tests/fixtures/venues/` into a git repository initialised in `tmp_path`
  at `<base>/<owner>/<repo>/venues/<name>/`, reached through the same
  `RHARNESS_GITHUB_BASE` override the plugin-source tests use, with the
  `owner/repo/subdir` form so the subdir survives classification.
  Cases: `add` from the workspace root off a TTY refuses and lists projects;
  `add` inside a project writes the venue block, the charter note, and the
  table row; `change` keeps a modified file and lists it; `lock` and
  `unlock` append charter lines and flip check severity; the refresh TTL
  with a stubbed clock and a stubbed `ls-remote`; project brief and
  workspace table output. TTY behaviour is tested by monkeypatching
  `isatty`.
- `tests/test_paper.py`: `paper build` engine detection and the
  missing-package loop against a stubbed `latexmk` log and stubbed `tlmgr`.
- `tests/test_pdf.py`: pure-Python page count against a committed pdfLaTeX
  output with object streams and against an uncompressed hand-written PDF;
  anonymity scan against a tex fixture with and without `pdftotext`.
- CI: GitHub Actions, macOS and Ubuntu, Python 3.9 and 3.13.
- Acceptance for version one: `rharness adopt ~/Documents/research` exits 0
  and `rharness lint` reports the zero-commit repos, dirty trees, missing
  `.gitattributes`, missing spec directories, and writing.md drift found in
  the 2026-09-09 audit.

## 9. Open decisions deferred past version one

- Plugin sources outside this repo (`add github:user/repo`).
- Network metadata verification of references (Crossref, OpenAlex) and any
  LLM judgment of claim support.
- Two venues on one project. Per-plugin `SKILL.md` rendering.
- Cursor and Gemini adapters.

## 10. Venues

A venue is a submission target attached to one project: a conference or
journal cycle with absolute deadlines, a page limit, an anonymity rule, a
style file, a checklist, and checks that `lint` runs. It is a project-scoped
plugin (section 6) fetched from the main repository on demand. Venue
packages are excluded from the release tarball by `venues/ export-ignore`
in the root `.gitattributes`, because they change through a cycle; the
release carries the mechanism only. In 0.3.0 `venue` requires a workspace;
a bare LaTeX repository is section 9.

### 10.1 Commands

| Command | Behavior |
|---|---|
| `venue` | Status for the project: venue, state, each deadline with days remaining, package commit and age, upstream status when the TTL has elapsed, then the venue check results. |
| `venue add iclr 2027` | Also `add iclr2027` or `add owner/repo/venues/iclr2027[@ref]`. Fetches the package, installs it into the project, sets state `targeted`. |
| `venue change aaai 2027` | Section 10.6. Swaps packages, resets to `targeted`. Confirmed. |
| `venue lock` / `venue unlock` | Section 10.7. `unlock` is confirmed. |
| `venue check [--build]` | Venue checks only, same output as `lint`. `--build` runs `paper build` first. |
| `venue update` | Refreshes the package from upstream regardless of TTL. Backs up the previous package directory to `~/.rharness/backup/<date>/` first, since the cache holds one copy per name. |
| `venue remove` | Removes unmodified venue files, lists modified ones, clears the venue block. Confirmed. |
| `venue list` | Venues in the cached index with cycle and primary deadline, and the index age. |

`--project <slug>` is accepted by every subcommand and suppresses the
picker. Venue tokens normalise: `iclr 2027` and `iclr2027` are the same
name. Names carry the cycle year. There is no unversioned `iclr`; deadlines,
page limits, and style files differ per cycle, and rule 7 (absolute dates)
applies to package names too.

### 10.2 Package format

Directory `venues/<name>/` in the main repository:

```
venues/
  README.md            how to add a venue; sources and license policy
  schema.json          shape of venue.json, validated for every package in CI by a stdlib script
  INDEX.json           generated from the venue.json files by scripts/venues-index.py; never hand-edited
  iclr2027/
    plugin.json        {"name": "iclr2027", "scope": "project", "kind": "venue", ...}
    venue.json         metadata, below
    agents.md          region for the project AGENTS.md: venue, deadlines, Overleaf note, the style line to add
    checks.py          optional; only for rules the generic set cannot express
    project-files/
      research/venue-iclr2027.md    archetype K prefilled with the venue's review form
```

`venue.json`:

```json
{
  "venue": "iclr", "cycle": "2027", "name": "iclr2027",
  "revision": "2026-09-10",
  "deadlines": {"abstract": "2026-09-18T23:59:00-12:00", "full": "2026-09-25T23:59:00-12:00"},
  "primary": "full",
  "page_limit": {"main": 9, "excludes": ["references", "appendix"]},
  "anonymous": true,
  "template": {"repo": "ICLR/Master-Template", "ref": "<commit>",
               "files": ["iclr2027_conference.sty", "iclr2027_conference.bst"]},
  "required_sections": ["abstract", "introduction", "related work", "conclusion"],
  "sources": [
    {"kind": "cfp", "url": "https://iclr.cc/Conferences/2027/CallForPapers", "retrieved": "2026-09-10"},
    {"kind": "reviewer-form", "url": "...", "retrieved": "2026-09-10"}
  ]
}
```

Rules for the file: timestamps are ISO-8601 with seconds and a UTC offset
(AoE is `-12:00`); `primary` names one key of `deadlines` and drives the
base checks and the brief; `revision` is the date the metadata was last
checked against `sources`. The schema enforces all three.

`template` points at the venue's own distribution instead of vendoring it:
a GitHub repository at a pinned commit, or `{"url": ..., "sha256": ...,
"extract": [...]}` for a zip. `venue add` fetches the files into `paper/`,
verifies the pin or checksum, and records them in the project manifest
under owner `venue:<name>`. A copy is vendored under `project-files/` only
when the upstream has no stable URL and its license permits redistribution;
`README.md` in `venues/` records the check per venue.

The generic check set lives in the binary (`lib/rharness/venuecheck.py`)
and is parameterised by `venue.json`: page count, required sections,
citation keys resolve, style loaded, anonymity. A typical package therefore
contains no code. `checks.py`, when present, has one entry point:

```python
def check(project_dir, venue):
    """Return a list of (severity, path, message); severity is "error" or
    "warning". Reads files and runs git inside project_dir; no network I/O,
    no writes."""
```

It takes a bare directory, not a Workspace or Project object, so the same
code runs on a LaTeX repository with no other rharness files (section
10.11). `lint` loads it with `importlib` from the cached package.

The review-form text for archetype K already exists for two venues in the
review-panel plugin (`panels/`, `prompts/`); venue packages reference or
move those, never duplicate them.

Staleness on the maintainer side: a scheduled GitHub Action fetches every
`sources[].url`, hashes the page text, and opens an issue when a hash
changes. It parses nothing. A wrong automatic deadline is worse than an
issue a maintainer reads.

### 10.3 Resolution, fetch, and trust

A bare name resolves to `<venue_index>/<name>`. `venue_index` is a key in
`lint.toml` with default `Vein05/rharness/venues` added to
`lintcfg.DEFAULTS`; the `venue` commands load the same file. A fork or a
lab points it at its own tree. A full `owner/repo/subdir[@ref]` form
bypasses the index. Fetching uses the existing GitHub path from section 6
and the existing cache under `~/.rharness/plugins/<name>/`. From 0.3.0 the
cache's `fetched` field is an ISO-8601 timestamp, not a date.

The confirmation gate is skipped when the resolved source string starts
with the configured `venue_index` and no `@ref` was given. Every other
source gets the existing capability summary and confirm-or-`--yes` gate,
because `checks.py` is code that runs in-process. Note that the shipped
`install_plugin` prompts for every non-builtin source; the index allowlist
is new.

`INDEX.json` is fetched to `~/.rharness/venues/INDEX.json` under the same
TTL as packages; `venue list` prints the cached copy with its age when
offline.

### 10.4 Project-side state

`.rharness/project.json` gains one block:

```json
"venue": {"name": "iclr2027", "source": "Vein05/rharness/venues/iclr2027",
          "ref": null, "commit": "abc123", "fetched": "2026-09-10T14:02:11-05:00",
          "state": "targeted", "locked_on": null}
```

One project holds at most one venue. A non-null `ref` means pinned: it
never auto-refreshes and `venue update` re-resolves the same ref. Installed
files (template files, `project-files/`) are recorded in the project
manifest under owner `venue:<name>`, so `update`, `change`, and `remove`
distinguish modified from unmodified by hash, as in section 5. Every
transition (`add`, `change`, `lock`, `unlock`, `remove`) appends one dated
line to the `## Revision notes` section of `CHARTER.md` and re-records the
`CHARTER.md` hash in the project manifest so `update` does not treat the
file as user-modified. The project's row in the workspace `AGENTS.md`
table has its existing `venue target` cell rewritten, for example
`iclr2027 (locked, 8d)`; the table header is outside the managed region and
is never touched.

`paper/main.tex` is never written by a venue package. The scaffold's
`main.tex` gains one marked line in the preamble, `% rharness:venue-style`,
which the venue's `agents.md` names as the place to load the style. A check
confirms the style is loaded. Immediately after `venue add`, the style,
required-sections, and missing-PDF findings are expected to be open until
the agent acts; `venue add` says so.

### 10.5 Where it runs, who runs it

Inside a project, every `venue` subcommand acts on that project. At the
workspace root or outside any project: on a TTY, a numbered picker over the
projects; off a TTY, exit 2 with the project list and `--project <slug>`.

`change`, `unlock`, and `remove` are confirmed. On a TTY, a y/n prompt. Off
a TTY, exit 1 with a printed list of what would change and the sentence:
"If you are an agent, confirm with the user before re-running as
`rharness --yes venue <subcommand> ...`: this swaps the paper style, the
check set, and the deadline agents see." `--yes` is a global flag and goes
before the subcommand, as for `add`. Detection is `sys.stdin.isatty()`, the
same test `session-check` uses. No harness-specific environment sniffing.

### 10.6 change

`venue change <name>`: remove the old package's files that are unmodified,
keep and list the modified ones, install the new package, set state
`targeted`, append one charter line naming both venues. Changing a locked
venue prints the lock date in the confirmation. The old package stays
cached because names carry the cycle year, so `change` back reinstalls it
and the charter history shows both moves.

### 10.7 Lock and lint

Two states. `targeted` (after `add` or `change`): venue checks run and every
finding is downgraded to warning; deadlines show in `brief`. `locked`
(after `lock`): findings keep the severity returned. Under the default
`fail_on = "warning"` both states exit 1 on any finding; under
`fail_on = "error"` a targeted venue never fails lint and a locked one
fails on its errors (section 7).

`lock` prints a warning, not a refusal, when the charter's success criterion
is still `NOT YET` or `spec/scoring.md` is still `proposed`. The base checks
in section 7 (primary deadline near while success criterion is `NOT YET`,
deadline passed, PDF missing or stale) apply to every project with a venue
block regardless of package. `lint` runs venue checks for any project with a
venue block; there is nothing new to remember.

### 10.8 Refresh

The `venue`, `venue check`, and `lint` commands refresh when the cached
`fetched` timestamp is older than 24 hours and the venue is not pinned. The
refresh does `git ls-remote` with a 5 second timeout; if the tip differs
from the cached commit it re-fetches and compares the package subtree hash.
An unchanged subtree only bumps `fetched`, since the repository tip moves
on every unrelated commit. Offline or timed out, it does nothing, silently.

When the subtree changed and the venue is `targeted`: for a package from
the configured index, `venue.json`, `checks.py`, and unmodified managed
files are applied, with the same trust the index had at `add`; for any
other source, only `venue.json` is applied and a changed `checks.py` is
reported and waits for `venue update`, which re-shows the confirmation.
When the venue is `locked`, any update is reported and applied only by
`venue update`. File replacement goes through the project manifest's
replace-if-unmodified path, not through the `project-files/` copy, which
never overwrites.

The refresh lives in the CLI layer, not in `lint_project`, because `brief`
calls `lint_project` directly and must stay offline. `brief` prints the
package age and a nudge past 7 days.

### 10.9 Brief

The project brief gains a venue line: name, state, days to each deadline,
package age. The workspace-root brief table (generated text, not the
`AGENTS.md` table) gains a venue column showing name, state, and days to
the primary deadline, read from the venue block only. Venue checks run in
the project brief, not in the workspace table: the SessionStart hook has a
30 second budget and a per-project PDF scan does not fit it. That table is
the decision surface for which project goes to a given deadline. The
harness does not decide that.

### 10.10 The generic check set, and iclr2027

Generic checks, all local, parameterised by `venue.json`:

- Page count of `paper/main.pdf` against `page_limit.main`. When
  `page_limit.excludes` is set and `pdftotext` is present, the main body
  ends on the page where the first excluded heading appears; without
  `pdftotext` the check reports the total page count as a warning that says
  the limit applies to the main body and cannot be located. Error when
  locked and the located body is over. Without a PDF, the section 7 warning
  and skip.
- Required sections present in the tex sources.
- Every `\cite` key resolves in `references.bib`; duplicate keys reported
  (error and warning). Malformed entries, the same DOI under two keys, and
  entries never cited are warnings. `\cite` covers the natbib and biblatex
  variants (`\citet`, `\parencite`, `\nocite`, ...).
- `main.tex` loads the template's style or class file.
- Anonymity when `anonymous` is true: author names from `git log`, the
  `git remote` URL, the `\author` block, `\thanks`, and an acknowledgements
  section. Scanned in the PDF text when `pdftotext` is present, in the tex
  sources otherwise. Every finding names the source string it matched so a
  false positive is one line to read. Precision over coverage: a check
  that cannot be made precise is left out.

`iclr2027` is metadata only: the `venue.json` above, the review form, and
no `checks.py`.

### 10.11 `lint --venue` on a bare LaTeX directory

`rharness lint --venue <name> [dir] [--main FILE]` runs the generic set and
the package's `checks.py` on `dir` (default: the current directory) and
nothing else: no project checks, no workspace checks, no venue block. The
name resolves as in section 10.3, against the `venue_index` of the
enclosing workspace's `lint.toml` when there is one, else the default; a
source outside the index needs `--yes`. A cached package older than the TTL
is re-fetched, and the cached copy is used when that fails.

Layout, all relative to `dir`:

- Main file: `--main`, else `main.tex` when it has `\documentclass`, else
  the one `.tex` file that does. Several candidates and no `main.tex` is a
  usage error (exit 2) that lists them.
- Tex sources: the main file and every file reached from it through
  `\input`, `\include`, or `\subfile`, resolved against the main file's
  directory and never outside `dir`. Other `.tex` files are not read, so a
  second paper in the same repository cannot produce findings.
- Bib files: every name in `\bibliography{...}` and `\addbibresource{...}`
  in those sources. None named is a warning; a named file missing is a
  warning and skips the key check, since its keys are unknown.
- PDF: the main file's path with `.pdf`.

Findings keep the severity returned, as when locked, and paths are relative
to `dir`. Deadline-passed rows apply; the near-deadline `NOT YET` row does
not, since there is no charter. Inside a project, `paper/` keeps its fixed
names (`main.tex`, `references.bib`, `main.pdf`).

## 11. Paper build

rharness does not bundle a TeX engine. `paper build` runs inside a project
(the section 10.5 picker applies) and uses `make` in `paper/` when a
Makefile is present, otherwise `latexmk -pdf -interaction=nonstopmode
main.tex` directly. Exit 0 on a PDF, 1 on a build failure with the last 40
log lines, 2 when there is no `paper/` directory or no engine.

`doctor` checks for `latexmk` and `pdflatex` as optional notes. When both
are missing, `doctor` and `venue add` print the TinyTeX one-line installer
and say a page check needs either a local build or a PDF from Overleaf.
Nothing is installed without the user running that line. TinyTeX is a
trimmed TeX Live (roughly 100 to 150 MB depending on scheme) with
pdfLaTeX and `tlmgr`; whether `latexmk` is in its default set is
unverified, so when `tlmgr` is present and `latexmk` is not, `paper build`
offers `tlmgr install latexmk`. TinyTeX is preferred over Tectonic because
venue style files target pdfLaTeX and page breaks must match the venue's
own pipeline.

On a missing-file failure, `paper build` parses the `.sty` or `.cls` name
from the log, resolves it with `tlmgr search --file --global /<name>`,
installs it, and retries, bounded to five rounds. `tlmgr` needs the
network; offline, the loop reports the missing file and stops. It runs
`tlmgr` only for a file name it read from the log. Any other failure exits
1 with the log tail.

`lint` never compiles. Venue checks read `paper/main.pdf` and report the
section 7 warning when it is missing or stale. `venue check --build`
compiles first for anyone who wants a single command.

Scaffold changes: the Makefile's prerequisites gain `$(wildcard *.sty)
$(wildcard *.cls)` so a newly installed style rebuilds; `paper/main.pdf`
is added to the project `.gitignore` template. A committed PDF is the
stale-artifact problem the provenance ledger (section 4, `hash`) exists to
catch.

## 12. Reading the PDF, and Overleaf

Reading a PDF needs no TeX. Page count uses `pdfinfo` when present.
Otherwise a pure-Python reader: inflate every FlateDecode stream with
`zlib` so objects inside object streams become visible (pdfTeX writes
object streams by default), then count `/Type /Page` objects excluding
`/Pages`, falling back to the page tree root's `/Count`. Text for the
anonymity scan comes from `pdftotext` when present and from the tex sources
otherwise. `pdfinfo` and `pdftotext` are poppler tools and absent on a
stock macOS, so the fallbacks are the common path, not the edge. `doctor`
lists both as optional notes with one line on what improves when they are
installed.

Overleaf users are a first-class path, not a degraded mode. They download the
compiled PDF into `paper/main.pdf`; every venue check then runs unchanged.
The venue's `agents.md` region says so, and the stale-PDF warning in
section 7 names the file to refresh. For them the build engine is never
needed, and `doctor` says so instead of insisting on TinyTeX.

## Revision notes

- 2026-09-09: `bin/rharness` is a thin entrypoint; logic lives in
  `lib/rharness/` modules (still Python stdlib only, shipped in the same
  tarball). Reason: testability and file size. Layout in section 2 updated
  by this note.
- 2026-09-09: `lint.toml` is a flat `key = value` file parsed by a minimal
  reader so Python 3.9 (no `tomllib`) stays supported.
- 2026-09-09: plugin sources moved from "deferred" into version one.
  `rharness add` accepts a built-in name, a local path, a git URL, or
  `owner/repo[/subdir]` on GitHub; external plugins are cached under
  `~/.rharness/plugins/<name>/` and their source recorded in the manifest
  (`plugin_sources`). `rharness plugin new` scaffolds a plugin.
  `plugin.json` gains `requires.env`, reported after install. Documented in
  `docs/plugins.md`.
- 2026-09-10: section 2 and section 4 rewritten to match the shipped layout
  (entrypoint plus package) and the added commands `brief`, `session-check`,
  and `plugin new`. Project templates gained `CLAUDE.md` and a managed
  `base` region in `AGENTS.md` (session protocol and workspace rules).
  `base/claude/hooks.json` ships SessionStart and Stop hooks that `init` and
  `adopt` merge for Claude Code workspaces.
- 2026-09-10: sections 10 to 12 added for 0.3.0: venues as project-scoped
  plugins fetched from `venues/` in the main repository, a two-state lock,
  TTL refresh, `paper build` with TinyTeX as the optional engine, and
  PDF reading without poppler. `plugin.json` gains `scope` and `kind`.
  Section 7 gains the venue rows, section 8 the venue tests, section 9
  loses the `rharness paper` line and gains standalone `lint --venue`.
  The CLI name stays `rharness`; no `rh` alias.
- 2026-09-10: independent review of sections 10 to 12 applied. Generic
  venue checks move into the binary and packages become metadata only;
  templates are pinned pointers to the venue's own distribution with a
  `sources` block for provenance; `primary` deadline key; `fetched` becomes
  a timestamp; refresh compares the package subtree, not the repository
  tip; auto-refresh of code limited to the configured index; `doctor`
  gains an optional-note state; `main.tex` gains a `% rharness:venue-style`
  marker; Makefile prerequisites include style files; `venues/` is
  `export-ignore`; `INDEX.json` is cached; section 4 gains `hash` and
  section 7 the provenance, scoring, and spec-before-code rows that shipped
  in 0.2.0 but were missing here; `apply` renamed to `update --no-fetch`.
- 2026-09-10: implementation plan `docs/superpowers/plans/2026-09-10-venues.md`
  executes sections 10 to 12. Deviation recorded during implementation:
  `--project` is accepted before or after the subcommand
  (`rharness venue --project seam lock` and `rharness venue lock --project seam`).
- 2026-09-10: section 10.9 says the workspace brief table reads "from the venue
  block only"; the block holds no deadlines, so the table reads deadlines from
  the cached venue.json and never scans a PDF or touches the network, which is
  the sentence's intent.
- 2026-10-07: severity-aware `lint` exit moved out of section 9. `lint.toml`
  gains `fail_on` (`warning` default, or `error`) and `lint` gains
  `--fail-on`; section 7 states the exit status and section 10.7 how the two
  venue states differ under each setting. The default is unchanged.
- 2026-10-07: standalone `lint --venue` moved out of section 9 into the new
  section 10.11. The generic checks take a layout (main file, tex sources,
  bib files, PDF) instead of fixed `paper/` names; projects keep the fixed
  names and their messages are unchanged.
- 2026-10-07: bibliography checks (`lib/rharness/bibcheck.py`): a small
  BibTeX parser, malformed entries, duplicate DOIs, and uncited entries,
  added to the venue generic set and, as warnings, to every project with no
  venue. Projects with a venue get them once, through the venue checks.
- 2026-10-07: word caps on orientation files (after viberesearch's
  per-file caps): `charter_max_words`,
  `handoff_max_words`, `changelog_entry_max_words`, `brief_max_words` in
  `lint.toml`, warning over the cap and error over twice it. This measures
  the context cost the eleven archetypes may impose; the defaults are to be
  revisited after a dogfood project.
