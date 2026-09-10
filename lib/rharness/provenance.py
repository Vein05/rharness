"""research/PROVENANCE.md: the ledger of frozen artifacts and their hashes."""
import re
from pathlib import Path

from . import gitutil
from .manifest import sha256_file, today

LEDGER_REL = Path("research") / "PROVENANCE.md"
HEADER = "| path | sha16 | bytes | recorded | code commit | note |"
DIVIDER = "|---|---|---:|---|---|---|"
ARTIFACT_DIRS = ("traces", "runs")


def sha16(path: Path) -> str:
    return sha256_file(path)[:16]


def code_commit(pdir: Path) -> str:
    if not gitutil.is_repo(pdir):
        return "no-git"
    r = gitutil.git(["rev-parse", "--short", "HEAD"], pdir)
    sha = r.stdout.strip() if r.returncode == 0 and r.stdout.strip() else "no-commit"
    return sha + ("+dirty" if gitutil.dirty_count(pdir) else "")


def parse_ledger(text: str):
    rows = []
    for line in text.splitlines():
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) < 5 or cells[0] in ("path", "") or set(cells[0]) <= set("-:"):
            continue
        rows.append({"path": cells[0].strip("`"), "sha16": cells[1], "bytes": cells[2],
                     "recorded": cells[3], "commit": cells[4], "note": cells[5] if len(cells) > 5 else ""})
    return rows


def _row_line(row: dict) -> str:
    return (f"| `{row['path']}` | {row['sha16']} | {row['bytes']} | {row['recorded']} | "
            f"{row['commit']} | {row['note']} |")


def upsert_rows(text: str, rows):
    """Replace rows with the same path, append new ones; creates the table if absent."""
    lines = text.splitlines()
    if HEADER not in lines:
        lines += ["", HEADER, DIVIDER]
    by_path = {r["path"]: r for r in rows}
    out, seen = [], set()
    for line in lines:
        if line.startswith("| `"):
            path = line.split("`")[1]
            if path in by_path:
                out.append(_row_line(by_path[path]))
                seen.add(path)
                continue
        out.append(line)
    for r in rows:
        if r["path"] not in seen:
            out.append(_row_line(r))
    return "\n".join(out).rstrip("\n") + "\n"


def record(pdir: Path, paths, note: str = ""):
    """Hash paths (relative to pdir or absolute) into the ledger. Returns the rows written."""
    ledger = pdir / LEDGER_REL
    commit = code_commit(pdir)
    rows = []
    for p in paths:
        f = Path(p)
        f = f if f.is_absolute() else (Path.cwd() / f)
        f = f.resolve()
        rel = f.relative_to(pdir.resolve()).as_posix()
        rows.append({"path": rel, "sha16": sha16(f), "bytes": str(f.stat().st_size),
                     "recorded": today(), "commit": commit, "note": note})
    ledger.parent.mkdir(parents=True, exist_ok=True)
    text = ledger.read_text() if ledger.exists() else "# Provenance ledger\n"
    ledger.write_text(upsert_rows(text, rows))
    return rows


def check(pdir: Path):
    """(severity, path, message) for every ledger problem and unrecorded artifact."""
    out = []
    ledger = pdir / LEDGER_REL
    recorded = set()
    if ledger.exists():
        for row in parse_ledger(ledger.read_text()):
            recorded.add(row["path"])
            f = pdir / row["path"]
            if not f.exists():
                out.append(("error", str(LEDGER_REL), f"recorded artifact {row['path']} is missing"))
            elif sha16(f) != row["sha16"]:
                out.append(("error", row["path"],
                            f"{row['path']} changed since it was recorded ({row['recorded']}, {row['sha16']}); "
                            f"re-run `rharness hash` and re-check every number that cites it"))
    for d in ARTIFACT_DIRS:
        base = pdir / d
        if not base.is_dir():
            continue
        for f in sorted(base.rglob("*")):
            if f.is_file() and not f.name.startswith(".") and f.name != "README.md":
                rel = f.relative_to(pdir).as_posix()
                if rel not in recorded:
                    out.append(("warning", rel, f"{rel} is not in research/PROVENANCE.md; record it with `rharness hash {rel}`"))
    return out
