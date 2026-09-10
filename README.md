<p align="center"><img src="assets/cover.svg" alt="rharness" width="100%"></p>

# rharness

A one-command setup for ML and NLP researchers who work with coding agents
(Claude Code, Codex). It writes the markdown contracts and scripts that keep
an agent-driven research workspace disciplined: a charter with a kill
criterion per paper, an agent orientation file, daily handoffs and
changelogs, specs before code, dated experiment reports, and a lint that
reports drift. It is markdown and scripts, not an app.

## Install

```sh
curl -fsSL https://raw.githubusercontent.com/Vein05/rharness/main/install.sh | sh
```

Requires `python3` 3.9 or newer, `git`, and `tar`. `git-lfs` is recommended.
The installer puts a release under `~/.rharness/store/` and adds
`~/.rharness/bin` to your PATH.

## Commands

| Command | What it does |
|---|---|
| `rharness init [dir]` | Create a workspace: root `AGENTS.md`, `CLAUDE.md`, `lint.toml`, and the default `rtk` plugin |
| `rharness new <slug>` | Scaffold a paper project inside the workspace: charter, orientation, specs, paper skeleton, git and LFS, first handoff |
| `rharness adopt [dir]` | Retrofit an existing workspace or project. Adds missing files, never overwrites |
| `rharness add <plugin>` | Install a plugin (files, an `AGENTS.md` section, and Claude Code skills or hooks if any) |
| `rharness remove <plugin>` | Uninstall a plugin. Modified files are kept and listed |
| `rharness lint` | Check every project against the rules. Exit 1 on findings, `--json` for machine output |
| `rharness doctor` | Check the machine: python, git, git-lfs, rtk, and that the rtk hook is still registered |
| `rharness update` | Fetch the latest release and re-apply managed files |
| `rharness list` | Installed and available plugins |

Global flags: `--workspace <dir>`, `--dry-run`.

## What a workspace looks like

```
research/
  AGENTS.md            orientation, project table, cross-cutting rules
  CLAUDE.md            @AGENTS.md
  lint.toml            lint thresholds
  .rharness/           manifest, archetypes, hook scripts
  .claude/             settings.json with hooks, skills (Claude Code only)
  seam/                one paper project
    CHARTER.md         core question, success criterion, kill criterion
    AGENTS.md          repo map, known traps, standing rules
    spec/              scoring.md first, then one file per component
    research/          the living knowledge base, one archetype per doc
    paper/             LaTeX skeleton and writing.md
    handoff/  changelog/  data/  papers/  tests/  tools/
```

## Plugins

| Plugin | Default | What it adds |
|---|---|---|
| `rtk` | yes | Token-saving command rewriter hook for Claude Code |
| `figures` | no | SVG-first figure pipeline with an automated geometry checker |
| `review-panel` | no | Simulated LLM reviewer panel with tiers, a holdout canary, and a spend ceiling |
| `wandb` | no | Weights & Biases tracking rules and a run-init helper per project |
| `ideas` | no | Ranked ideas backlog with scoop-scan dates and a dead-cells list |

### Writing a plugin

A plugin is a directory under `plugins/`:

```
plugins/<name>/
  plugin.json        name, description, version, harness: ["claude","codex"], requires
  agents.md          section inserted into the workspace AGENTS.md
  files/             copied into the workspace root
  project-files/     copied into every project (existing and future)
  claude/skills/     Claude Code skills (Claude only)
  claude/hooks.json  hook entries merged into .claude/settings.json (Claude only)
  setup.sh           optional; runs after install, may install binaries
```

Text files may use `{{slug}}`, `{{title}}`, `{{date}}`, and `{{workspace}}`.

## Managed files

Every file rharness writes is recorded with a hash. On `update`, a file is
replaced only if it still matches its recorded hash; otherwise it is kept and
a diff is printed. In `AGENTS.md` and `paper/writing.md`, rharness owns only
the text between `<!-- rharness:begin ... -->` and `<!-- rharness:end ... -->`
markers; everything outside is yours.

## Cover art

`assets/cover/build.py` generates `assets/cover.svg` from the inlined brand marks in
`assets/cover/icons/`; `assets/cover-social.png` is the 1280x640 GitHub social preview.
Brand marks belong to their owners and are used unmodified.

## Development

```sh
python3 -m pytest -q
```

Design: `docs/superpowers/specs/2026-09-09-rharness-design.md`.
