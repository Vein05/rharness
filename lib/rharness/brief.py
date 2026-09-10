"""The orientation bundle a fresh agent session reads first."""
import re
from pathlib import Path

from . import gitutil
from .lint import format_findings, lint_project, writing_template_region
from .manifest import Manifest, today
from .workspace import PROJECT_MANIFEST_REL

DATE_MD = re.compile(r"^(\d{4}-\d{2}-\d{2})(?:[-_].*)?\.md$")


def _read(path: Path) -> str:
    return path.read_text(errors="replace")


def _strip_comments(text: str) -> str:
    return re.sub(r"<!--.*?-->", "", text, flags=re.S).strip()


def _section(text: str, heading: str) -> str:
    m = re.search(r"^## " + re.escape(heading) + r"\s*$(.*?)(?=^## |\Z)", text, re.M | re.S)
    return _strip_comments(m.group(1)) if m else ""


def _status_line(block: str) -> str:
    m = re.search(r"\*\*Status:\*\*\s*(.+)", block)
    return m.group(1).strip() if m else "(no Status line)"


def newest_dated(dirpath: Path):
    if not dirpath.is_dir():
        return None
    files = [(m.group(1), f) for f in dirpath.iterdir() if (m := DATE_MD.match(f.name))]
    return max(files)[1] if files else None


def _cap(text: str, lines: int, tail=False) -> str:
    rows = text.rstrip("\n").split("\n")
    if len(rows) <= lines:
        return "\n".join(rows)
    kept = rows[-lines:] if tail else rows[:lines]
    note = f"[... {len(rows) - lines} more lines]"
    return "\n".join([note] + kept if tail else kept + [note])


def charter_summary(pdir: Path) -> dict:
    charter = pdir / "CHARTER.md"
    if not charter.exists():
        return {"core": "(no CHARTER.md)", "success": "?", "kill": "?"}
    t = _read(charter)
    core = _section(t, "Core Question") or "(empty; fill in CHARTER.md)"
    return {"core": " ".join(core.split()),
            "success": _status_line(_section(t, "Primary Success Criterion")),
            "kill": _status_line(_section(t, "Kill Criterion"))}


def authoritative_docs(pdir: Path):
    agents = pdir / "AGENTS.md"
    if not agents.exists():
        return []
    t = _read(agents)
    m = re.search(r"\*\*Authoritative.*?\*\*(.*?)(?=\*\*Historical|\n## |\Z)", t, re.S)
    if not m:
        return []
    rows = []
    for line in m.group(1).splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) >= 2 and cells[0] and not set(cells[0]) <= set("-") and cells[0] != "doc":
            rows.append(f"{cells[0]}: {cells[1]}")
    return rows


def project_brief(pdir: Path, cfg: dict, lines: int = 80) -> str:
    slug = pdir.name
    pm_path = pdir / PROJECT_MANIFEST_REL
    title = Manifest.load(pm_path).ctx.get("title", slug) if pm_path.exists() else slug
    out = [f"# Brief: {slug}" + (f" ({title})" if title != slug else "") + f" — {today()}", ""]
    ch = charter_summary(pdir)
    out += ["## Charter", f"Core question: {ch['core']}", f"Success criterion: {ch['success']}",
            f"Kill criterion: {ch['kill']}", ""]
    if gitutil.is_repo(pdir):
        newest = gitutil.newest_commit_date(pdir) or "none"
        out += ["## Git", f"Newest commit: {newest}; uncommitted changes: {gitutil.dirty_count(pdir)}", ""]
    h = newest_dated(pdir / "handoff")
    if h:
        out += [f"## Newest handoff: handoff/{h.name}", _cap(_read(h), lines), ""]
    else:
        out += ["## Newest handoff", "None yet. Write handoff/YYYY-MM-DD.md at session end.", ""]
    c = newest_dated(pdir / "changelog")
    if c:
        out += [f"## Last changelog: changelog/{c.name}", _cap(_read(c), lines // 2, tail=True), ""]
    else:
        out += ["## Last changelog", "None yet. Append to changelog/YYYY-MM-DD.md as you work.", ""]
    docs = authoritative_docs(pdir)
    if docs:
        out += ["## Authoritative docs (trust these; dated records are historical)"]
        out += [f"- {d}" for d in docs] + [""]
    findings = lint_project(pdir, cfg, writing_template_region())
    errors = sum(1 for f in findings if f.severity == "error")
    out += [f"## Lint: {errors} errors, {len(findings) - errors} warnings"]
    if findings:
        out += [format_findings(findings).rsplit("\n", 1)[0]]
    out += ["", "Rules: this project's AGENTS.md (Session protocol, Workspace rules), then CHARTER.md."]
    return "\n".join(out)


def workspace_brief(ws, cfg: dict) -> str:
    out = [f"# Brief: workspace {ws.root} — {today()}", "",
           "| project | kill criterion | newest commit | dirty | newest handoff | lint |", "|---|---|---|---:|---|---|"]
    for pdir in ws.projects():
        ch = charter_summary(pdir)
        h = newest_dated(pdir / "handoff")
        findings = lint_project(pdir, cfg, writing_template_region())
        errors = sum(1 for f in findings if f.severity == "error")
        out.append(f"| {pdir.name} | {ch['kill']} | {gitutil.newest_commit_date(pdir) or 'none'} | "
                   f"{gitutil.dirty_count(pdir)} | {DATE_MD.match(h.name).group(1) if h else 'none'} | "
                   f"{errors}E/{len(findings) - errors}W |")
    out += ["", "Run `rharness brief <project>` for one project. Rules: AGENTS.md at the workspace root."]
    return "\n".join(out)


def find_project(ws, start: Path):
    """The project directory containing start, or None."""
    try:
        rel = Path(start).resolve().relative_to(ws.root)
    except ValueError:
        return None
    if not rel.parts:
        return None
    cand = ws.root / rel.parts[0]
    return cand if cand in ws.projects() else None
