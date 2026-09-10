"""Flat key = value config reader (Python 3.9 has no tomllib)."""
import re
from pathlib import Path

DEFAULTS = {
    "handoff_max_days_behind_commit": 1,
    "changelog_window_days": 14,
    "dirty_tree_warn_above": 0,
}
_LINE = re.compile(r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.+?)\s*$")


def _coerce(raw: str):
    if raw in ("true", "false"):
        return raw == "true"
    if re.fullmatch(r"-?\d+", raw):
        return int(raw)
    if len(raw) >= 2 and raw[0] == raw[-1] and raw[0] in "\"'":
        return raw[1:-1]
    return raw


def load_lint_config(path):
    cfg = dict(DEFAULTS)
    if path and Path(path).exists():
        for line in Path(path).read_text().splitlines():
            line = line.split("#", 1)[0]
            m = _LINE.match(line)
            if m:
                cfg[m.group(1)] = _coerce(m.group(2))
    return cfg
