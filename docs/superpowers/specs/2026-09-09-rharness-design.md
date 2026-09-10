# rharness — design

Status: approved in chat 2026-09-09. Authority for version one.

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
  bin/rharness                Python 3.9+ stdlib, single file, no pip dependencies
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

`bin/rharness` is a single Python file. Subcommands:

| Command | Behavior |
|---|---|
| `init [dir]` | Creates a workspace in `dir` (default `.`). Writes `base/workspace/*`, `.rharness/manifest.json`, then runs `add rtk`. Refuses if a manifest already exists; suggests `adopt`. |
| `new <slug> [--title T]` | Inside a workspace. Creates `dir/<slug>/` from `base/project/`, substitutes placeholders, `git init`, `git lfs install --local`, writes `handoff/<date>.md` stub, appends a row to the root `AGENTS.md` project table, records files in the manifest. |
| `adopt [dir]` | Detects whether `dir` is a workspace (has a root `AGENTS.md` and subdirectories with `CHARTER.md`) or a project. Adds every missing managed file, never overwrites an existing one, writes the manifest, prints what was added and what was skipped. |
| `add <plugin>` | Copies `plugins/<name>/files/` into the workspace, inserts the plugin's `agents.md` snippet as a marked region in the root `AGENTS.md`, applies harness extras (section 6), runs the plugin's `setup` script if present, records the plugin in the manifest. |
| `remove <plugin>` | Deletes the files the manifest attributes to the plugin if unmodified, removes its marked region, unregisters harness extras. Modified files are left and listed. |
| `lint [dir]` | Section 7. Exit 0 clean, 1 findings, 2 error. `--json` for machine output. |
| `doctor` | Machine checks: python version, git, git-lfs, rtk binary on PATH, RTK hook present in the effective Claude Code settings, workspace manifest readable. Exit 1 on any failure. |
| `update` | Section 3, then `apply` on the current workspace. |
| `list` | Installed plugins, available plugins, versions. |
| `version` | Prints the store version. |

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

- On `update` or `apply`, for each managed file: if the on-disk hash equals
  the recorded hash, replace with the new template and record the new hash.
  If it differs, leave it, print a unified diff to the new template, and
  keep the old hash. `--force` overwrites after backing up to
  `.rharness/backup/<date>/`.
- Region files (`AGENTS.md`, `CLAUDE.md`) are never replaced whole. rharness
  owns text between `<!-- rharness:begin base -->` and
  `<!-- rharness:end base -->`, and each plugin owns
  `<!-- rharness:begin plugin:<name> -->` … `<!-- rharness:end plugin:<name> -->`.
  Update rewrites only inside markers. Text outside markers is the user's.
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
required for every commit day in the last 14 days.

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

Workspace:

| Check | Severity |
|---|---|
| Root `AGENTS.md` project table rows correspond to existing directories, and every project directory has a row | warning |
| No `.zip`, `.pdf`, or `tmp*` entries at the workspace root | warning |
| Manifest parses and every recorded file exists | error |

Output: one line per finding, `<severity> <project>/<path>: <message>`,
grouped by project, summary counts at the end. `--json` emits a list of
objects with the same fields.

## 8. Testing

- `tests/test_cli.py`: each subcommand against a `tmp_path` workspace,
  asserting on the file tree, manifest contents, marker regions, and exit
  codes. Update-with-user-edit and remove-with-modified-file are explicit
  cases.
- `tests/test_lint.py`: fixtures that violate each check exactly once.
- `tests/test_install.bats`: runs `install.sh` against a fake `HOME` with a
  local tarball served from a temp dir via `python3 -m http.server`.
- CI: GitHub Actions, macOS and Ubuntu, Python 3.9 and 3.13.
- Acceptance for version one: `rharness adopt ~/Documents/research` exits 0
  and `rharness lint` reports the zero-commit repos, dirty trees, missing
  `.gitattributes`, missing spec directories, and writing.md drift found in
  the 2026-09-09 audit.

## 9. Open decisions deferred past version one

- Plugin sources outside this repo (`add github:user/repo`).
- A `rharness paper` command wrapping the LaTeX build.
- Cursor and Gemini adapters.

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
