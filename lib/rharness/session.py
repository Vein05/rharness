"""Session-end check behind the Claude Code Stop hook: today's work needs today's handoff."""
import datetime as _dt
import json
import os
from pathlib import Path

from . import gitutil
from .manifest import today


def _touched_today(pdir: Path) -> bool:
    if today() in gitutil.commit_days(pdir, 1):
        return True
    r = gitutil.git(["status", "--porcelain"], pdir)
    if r.returncode != 0:
        return False
    for line in r.stdout.splitlines():
        rel = line[3:].split(" -> ")[-1].strip().strip('"')
        p = pdir / rel
        if p.exists() and _dt.date.fromtimestamp(p.stat().st_mtime).isoformat() == today():
            return True
    return False


def missing_records(pdir: Path):
    """Names of today's records that are missing, given the project was worked on today."""
    if not gitutil.is_repo(pdir) or not _touched_today(pdir):
        return []
    missing = []
    for kind in ("handoff", "changelog"):
        if not (pdir / kind / f"{today()}.md").exists():
            missing.append(f"{kind}/{today()}.md")
    return missing


def session_check(projects, stdin_text: str = "") -> dict:
    """Return the hook decision for the Stop event. Empty dict means nothing to say."""
    try:
        payload = json.loads(stdin_text) if stdin_text.strip() else {}
    except json.JSONDecodeError:
        payload = {}
    if payload.get("stop_hook_active"):
        return {}
    problems = []
    for pdir in projects:
        missing = missing_records(pdir)
        if missing:
            problems.append(f"{pdir.name}: write " + " and ".join(missing))
    if not problems:
        return {}
    reason = ("This project was worked on today but today's session records are missing. "
              "Before finishing: " + "; ".join(problems) +
              ". Handoff: what happened, canonical artifacts, results so far, next up, deadlines. "
              "Changelog: a timestamped checkpoint of what changed. Then run `rharness lint`.")
    return {"decision": "block", "reason": reason}
