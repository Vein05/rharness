## RTK — token-saving command proxy (Claude Code)

`rtk` rewrites common shell commands (git, ls, grep, cat, test runners) to
compact-output equivalents. In Claude Code a PreToolUse hook rewrites Bash
commands automatically; nothing changes in how you write commands.

- `rtk gain` shows cumulative savings; `rtk proxy <cmd>` runs a command raw.
- If `rharness doctor` reports the hook missing, run `rharness add rtk` again.
