"""Lint checks for projects and workspaces."""
import datetime as _dt
import json
import re
from dataclasses import dataclass, asdict
from pathlib import Path

from . import gitutil
from .paths import BASE_DIR
from .regions import get_region

REQUIRED_FILES = ["CHARTER.md", "AGENTS.md", "README.md", "spec/README.md", "paper/writing.md"]
REQUIRED_DIRS = ["handoff", "changelog"]
LFS_RULES = ["data/*.jsonl", "papers/*.pdf", "traces/**"]
DATE_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})")
STATUS_RE = re.compile(r"^Status: (proposed|frozen|superseded)\b.*\d{4}-\d{2}-\d{2}", re.M)
RELATIVE_DATE_RE = re.compile(
    r"\b(yesterday|tomorrow|(last|next|this) (week|month|year|monday|tuesday|wednesday|thursday|"
    r"friday|saturday|sunday)|a few days ago|\d+ (days|weeks) ago)\b", re.I)
RELATIVE_DATE_SCOPE = ["CHARTER.md", "AGENTS.md", "spec", "handoff"]
ROW_RE = re.compile(r"^\| `([^`/]+)/` \|", re.M)
CLUTTER_RE = re.compile(r"(\.zip|\.pdf)$|^tmp", re.I)


@dataclass
class Finding:
    severity: str
    project: str
    path: str
    message: str

    def as_dict(self):
        return asdict(self)


def _newest_dated(dirpath: Path):
    dates = []
    if dirpath.is_dir():
        for f in dirpath.iterdir():
            m = DATE_RE.match(f.name)
            if m and f.suffix == ".md":
                dates.append(m.group(1))
    return max(dates) if dates else None


def _read(path: Path) -> str:
    try:
        return path.read_text()
    except UnicodeDecodeError:
        return path.read_text(errors="replace")


def writing_template_region():
    return get_region((BASE_DIR / "project" / "paper" / "writing.md").read_text(), "base")


def lint_project(pdir: Path, cfg: dict, template_region=None):
    out = []
    name = pdir.name

    def E(path, msg):
        out.append(Finding("error", name, path, msg))

    def W(path, msg):
        out.append(Finding("warning", name, path, msg))

    for rel in REQUIRED_FILES:
        if not (pdir / rel).exists():
            E(rel, f"{rel} missing")
    for rel in REQUIRED_DIRS:
        if not (pdir / rel).is_dir():
            E(rel + "/", f"{rel}/ missing")

    charter = pdir / "CHARTER.md"
    if charter.exists():
        t = _read(charter)
        sec = re.search(r"^## Kill Criterion\s*$(.*?)(?=^## |\Z)", t, re.M | re.S)
        if not sec or "Status:" not in sec.group(1):
            E("CHARTER.md", "CHARTER.md needs a `## Kill Criterion` section with a `Status:` line")

    spec = pdir / "spec"
    if spec.is_dir():
        for f in sorted(spec.glob("*.md")):
            if not STATUS_RE.search(_read(f)):
                E(f"spec/{f.name}",
                  f"spec/{f.name} must open with `Status: proposed|frozen|superseded, YYYY-MM-DD`")

    if not gitutil.is_repo(pdir):
        E("", "not a git repository")
    elif gitutil.commit_count(pdir) == 0:
        E("", "no commits")
    else:
        dirty = gitutil.dirty_count(pdir)
        if dirty > cfg["dirty_tree_warn_above"]:
            W("", f"{dirty} uncommitted changes")
        newest_commit = gitutil.newest_commit_date(pdir)
        newest_handoff = _newest_dated(pdir / "handoff")
        if newest_commit and newest_handoff:
            delta = (_dt.date.fromisoformat(newest_commit) - _dt.date.fromisoformat(newest_handoff)).days
            if delta > cfg["handoff_max_days_behind_commit"]:
                W("handoff/", f"newest handoff {newest_handoff} is {delta} days older than newest commit {newest_commit}")
        elif newest_commit and not newest_handoff:
            W("handoff/", "no dated handoff file")
        for d in sorted(gitutil.commit_days(pdir, cfg["changelog_window_days"])):
            if not (pdir / "changelog" / f"{d}.md").exists():
                W("changelog/", f"no changelog for commit day {d}")

    ga = pdir / ".gitattributes"
    text = _read(ga) if ga.exists() else ""
    missing = [r for r in LFS_RULES if not re.search(re.escape(r) + r"\s+filter=lfs", text)]
    if missing:
        W(".gitattributes", f"LFS rules missing: {', '.join(missing)}")

    if (pdir / ".env").exists() and gitutil.is_repo(pdir) and not gitutil.is_ignored(pdir, ".env"):
        E(".env", ".env exists and is not gitignored")

    for scope in RELATIVE_DATE_SCOPE:
        p = pdir / scope
        files = [p] if p.is_file() else (sorted(p.glob("*.md")) if p.is_dir() else [])
        for f in files:
            m = RELATIVE_DATE_RE.search(_read(f))
            if m:
                W(f.relative_to(pdir).as_posix(), f"relative date phrase \"{m.group(0)}\" (use YYYY-MM-DD)")

    w = pdir / "paper" / "writing.md"
    if w.exists() and template_region is not None:
        region = get_region(_read(w), "base")
        if region is None:
            W("paper/writing.md", "paper/writing.md has no rharness base region; generic sections cannot be checked")
        elif region != template_region:
            W("paper/writing.md", "paper/writing.md generic section differs from the template")
    return out


def lint_workspace(ws, cfg):
    out = []

    def E(path, msg):
        out.append(Finding("error", ".", path, msg))

    def W(path, msg):
        out.append(Finding("warning", ".", path, msg))

    dirs = {p.name for p in ws.projects()}
    if ws.agents_path.exists():
        rows = set(ROW_RE.findall(_read(ws.agents_path)))
        for r in sorted(rows - dirs):
            W("AGENTS.md", f"table row `{r}/` has no directory")
        for d in sorted(dirs - rows):
            W("AGENTS.md", f"project {d} has no row in the AGENTS.md table")
    else:
        E("AGENTS.md", "AGENTS.md missing")
    for entry in sorted(ws.root.iterdir()):
        if CLUTTER_RE.search(entry.name):
            W(entry.name, f"{entry.name} at workspace root; archive or delete")
    for rel in sorted(ws.manifest.files):
        if not (ws.root / rel).exists():
            E(rel, f"{rel} is in the manifest but missing on disk")
    return out


def format_findings(findings):
    lines = []
    for f in findings:
        where = f"{f.project}/{f.path}" if f.path else f"{f.project}/"
        lines.append(f"{f.severity} {where}: {f.message}")
    errors = sum(1 for f in findings if f.severity == "error")
    lines.append(f"Summary: {errors} errors, {len(findings) - errors} warnings")
    return "\n".join(lines)


def format_json(findings):
    return "\n".join(json.dumps(f.as_dict()) for f in findings)
