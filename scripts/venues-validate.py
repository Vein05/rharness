#!/usr/bin/env python3
"""Validate every venues/<name>/ package. Exit 1 on any problem."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lib"))
from rharness.venuemeta import validate  # noqa: E402

problems = []
for d in sorted(p for p in (ROOT / "venues").iterdir() if p.is_dir()):
    vj, pj = d / "venue.json", d / "plugin.json"
    if not vj.exists():
        problems.append(f"{d.name}: venue.json missing"); continue
    try:
        v = json.loads(vj.read_text())
    except json.JSONDecodeError as e:
        problems.append(f"{d.name}: venue.json invalid JSON: {e}"); continue
    problems += [f"{d.name}: {e}" for e in validate(v)]
    if v.get("name") != d.name:
        problems.append(f"{d.name}: name {v.get('name')!r} does not match the directory")
    if not pj.exists():
        problems.append(f"{d.name}: plugin.json missing"); continue
    p = json.loads(pj.read_text())
    if p.get("name") != d.name or p.get("scope") != "project" or p.get("kind") != "venue":
        problems.append(f"{d.name}: plugin.json needs name={d.name}, scope=project, kind=venue")
    if not (d / "agents.md").exists():
        problems.append(f"{d.name}: agents.md missing")
for p in problems:
    print(p)
print(f"{len(problems)} problem(s)")
sys.exit(1 if problems else 0)
