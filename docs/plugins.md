# Plugins: using, writing, and publishing

A plugin is a directory of markdown and files that rharness copies into a
workspace, plus a section it inserts into the workspace `AGENTS.md`. Some
plugins also carry Claude Code skills or hooks. Nothing runs at install time
except an optional `setup.sh`.

## Install one

```sh
rharness add figures                          # built into the release
rharness add alice/research-plugins/plugins/x # GitHub: owner/repo[/subdir]
rharness add https://git.example.org/x.git    # any git URL, plugin at repo root
rharness add ~/code/my-plugin                 # local directory
rharness add alice/x --refresh                # re-fetch after the author pushes
rharness remove x
rharness list
```

External plugins are fetched once into `~/.rharness/plugins/<name>/` and
reused from there. Pin a source with `@ref`: `alice/x@v1.2`,
`alice/x/plugins/y@main`, or `https://host/x.git@<commit>`. The fetched
commit is recorded beside the plugin and shown by `rharness list`.

## Trust

A plugin from outside the release can add rules the agent will follow,
register Claude Code hooks that run shell commands, copy files into every
project, and run `setup.sh` on your machine. Before installing one,
`rharness add` prints a capability summary:

```
Plugin x from /Users/you/.rharness/plugins/x (commit 3b1f9c2e7a4d)
  3 file(s) into the workspace root; 1 file(s) into every project
  AGENTS.md section: yes, 12 lines (the agent will follow it)
  Claude Code skills: 1
  hook PreToolUse: runs `"$CLAUDE_PROJECT_DIR/.rharness/hooks/x.sh"`
  setup.sh: yes, a shell script will run on this machine
  requires: env OPENROUTER_API_KEY; binaries pdftotext
Install this plugin? [y/N]
```

It proceeds only on `y`, or with the global `--yes` flag
(`rharness --yes add ...`) for scripts. Without a terminal and without
`--yes` it refuses. Built-in plugins ship with the verified release and do
not prompt. Read the plugin directory before saying yes to anything that
registers a hook or ships a setup script.

`rharness list` shows each plugin's origin (`builtin` or `user`), whether it
is installed in the current workspace, and the source and commit it came from.

After install, `add` prints any environment variable or binary the plugin
declares in `requires` that is missing in your shell. For example the
`review-panel` plugin needs `OPENROUTER_API_KEY` and `pdftotext`.

## What install does

1. Copies `files/` into the workspace root, paths preserved, rendering
   `{{slug}}`, `{{title}}`, `{{date}}`, `{{workspace}}` in text files.
   Existing files are never overwritten.
2. Inserts `agents.md` into the workspace `AGENTS.md` between
   `<!-- rharness:begin plugin:<name> -->` and `<!-- rharness:end plugin:<name> -->`.
   Re-installing replaces only that region.
3. Copies `project-files/` into every existing project, and into every
   project created later with `rharness new` or `rharness adopt`.
4. If the workspace targets Claude Code and the plugin lists `claude` in its
   `harness`: copies `claude/skills/*` into `.claude/skills/` and merges
   `claude/hooks.json` into `.claude/settings.json` without touching other
   keys. Codex workspaces skip this step.
5. Records every written file with a hash in `.rharness/manifest.json`, so
   `rharness update` can refresh unmodified files and `rharness remove` can
   delete them while keeping anything you edited.
6. Runs `setup.sh` if present, with `RHARNESS_WORKSPACE` set. Set
   `RHARNESS_SKIP_SETUP=1` to skip it.

## Write one

```sh
rharness plugin new my-plugin --dir ~/code
```

This creates:

```
my-plugin/
  plugin.json          name, description, version, harness, requires
  agents.md            the rules an agent follows when this plugin is installed
  files/my-plugin/     copied into the workspace root
  project-files/       copied into every project (delete if unused)
  claude/skills/my-plugin/SKILL.md   Claude Code skill (delete if unused)
  README.md            what it adds and how to install it
```

`plugin.json` fields:

| field | meaning |
|---|---|
| `name` | lowercase letters, digits, hyphens; must equal the directory name |
| `description` | one line, shown by `rharness list` |
| `version` | your own versioning; rharness does not compare versions |
| `harness` | subset of `["claude", "codex"]`; controls whether `claude/` extras apply |
| `requires.binaries` | commands that must be on PATH; reported after install and by `doctor` for `rtk` |
| `requires.env` | environment variable names the plugin needs; reported after install, values never read |
| `requires.python` | informational |

Optional files:

- `claude/hooks.json`: `{"PreToolUse": [{"matcher": "Bash", "hooks": [...]}]}`,
  the same shape as Claude Code's settings. Use `$CLAUDE_PROJECT_DIR` for
  paths inside the workspace.
- `setup.sh`: POSIX shell, must exit 0, should print what it did or what the
  user still has to do. Do not install anything without saying so.

Rules a plugin must respect:

- Never write outside `files/`, `project-files/`, and `claude/`. Anything
  else in the plugin directory is documentation.
- Never put secrets, personal names, hostnames, or deadlines in shipped
  files. Reference environment variables by name only.
- Keep `agents.md` short. It is prepended to every agent session in that
  workspace.
- Do not depend on another plugin being installed.

Try it locally before publishing:

```sh
rharness add ~/code/my-plugin
rharness lint
rharness remove my-plugin
```

## Publish one

Push the directory to GitHub. Users install it with `rharness add
owner/repo`, or `owner/repo/path/to/plugin` when the plugin is not at the
repository root. A single repository can hold many plugins under
subdirectories. When you push a change, users pick it up with
`rharness add owner/repo --refresh`.

To propose a plugin for the built-in set, open a pull request adding it
under `plugins/` in this repository with a test in `tests/test_plugin.py`.
