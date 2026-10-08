"""Venue state on a project: the venue block, charter notes, the AGENTS.md table cell."""
import datetime as _dt
import json
import re
from pathlib import Path

from .manifest import Manifest, today
from .plugin import user_plugins_dir
from .venuemeta import validate
from .workspace import PROJECT_MANIFEST_REL


class VenueError(Exception):
    pass


TTL_HOURS = 24
LS_REMOTE_TIMEOUT = 5


def owner(name: str) -> str:
    return f"venue:{name}"


def package_dir(name: str) -> Path:
    return user_plugins_dir() / name


def load_pm(pdir: Path) -> Manifest:
    path = Path(pdir) / PROJECT_MANIFEST_REL
    if not path.exists():
        raise VenueError(f"{pdir} has no .rharness/project.json; run `rharness adopt {pdir}` first")
    return Manifest.load(path)


def read_block(pdir: Path):
    path = Path(pdir) / PROJECT_MANIFEST_REL
    if not path.exists():
        return None
    return Manifest.load(path).data.get("venue")


def write_block(pdir: Path, block):
    pm = load_pm(pdir)
    if block is None:
        pm.data.pop("venue", None)
    else:
        pm.data["venue"] = block
    pm.save()


def venue_block(name, source, ref, commit, fetched, tree) -> dict:
    return {"name": name, "source": source, "ref": ref, "commit": commit, "fetched": fetched,
            "tree": tree, "state": "targeted", "locked_on": None}


def charter_note(pdir: Path, pm: Manifest, text: str):
    ch = Path(pdir) / "CHARTER.md"
    line = f"- {today()}: {text}"
    if not ch.exists():
        ch.write_text(f"# Project Charter\n\n## Revision notes\n\n{line}\n")
    else:
        t = ch.read_text()
        m = re.search(r"^## Revision notes\s*$", t, re.M)
        if not m:
            t = t.rstrip("\n") + f"\n\n## Revision notes\n\n{line}\n"
        else:
            nxt = re.search(r"^## ", t[m.end():], re.M)
            end = m.end() + nxt.start() if nxt else len(t)
            section = t[m.end():end].rstrip("\n")
            t = t[:m.end()] + section + f"\n{line}\n" + ("\n" if nxt else "") + t[end:]
        ch.write_text(t)
    pm.rehash("CHARTER.md")


def set_table_cell(ws, slug: str, cell: str):
    path = ws.agents_path
    if not path.exists():
        return
    lines = path.read_text().split("\n")
    prefix = f"| `{slug}/` |"
    for i, line in enumerate(lines):
        if line.startswith(prefix):
            cells = line.split("|")
            if len(cells) >= 5:
                cells[3] = f" {cell} "
                lines[i] = "|".join(cells)
            break
    else:
        return
    path.write_text("\n".join(lines))
    prev = ws.manifest.entry("AGENTS.md") or {}
    ws.manifest.record("AGENTS.md", prev.get("owner", "base"), source="base/workspace/AGENTS.md", region=True)
    ws.manifest.save()


def load_venue(pkg_dir: Path) -> dict:
    f = Path(pkg_dir) / "venue.json"
    if not f.exists():
        raise VenueError(f"{pkg_dir} has no venue.json")
    try:
        data = json.loads(f.read_text())
    except json.JSONDecodeError as e:
        raise VenueError(f"venue.json: invalid JSON ({e})")
    errs = validate(data)
    if errs:
        raise VenueError("venue.json: " + "; ".join(errs))
    return data


def _record_paper_file(pm: Manifest, pdir: Path, name: str, rel: str):
    pm.record(rel, owner(name))


def _keep_existing(pm: Manifest, name: str, rel: str) -> bool:
    """True when rel exists on disk and is not this venue's to overwrite.

    That covers a user's own file (no manifest entry) and anything owned by someone
    else: the base scaffold, a plugin, or another venue.
    """
    if not (pm.root / rel).exists():
        return False
    entry = pm.entry(rel)
    return entry is None or entry.get("owner") != owner(name)


AGENT_SENTENCE = ("If you are an agent, confirm with the user before re-running as "
                  "`rharness --yes venue {sub} ...`: this swaps the paper style, the check set, "
                  "and the deadline agents see.")
TINYTEX = 'wget -qO- "https://yihui.org/tinytex/install-bin-unix.sh" | sh'


def _stale(block, now=None) -> bool:
    try:
        t = _dt.datetime.fromisoformat(block.get("fetched", ""))
    except (TypeError, ValueError):
        return True
    now = now or _dt.datetime.now(tz=t.tzinfo)
    return (now - t) >= _dt.timedelta(hours=TTL_HOURS)
