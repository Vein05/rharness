"""Venue state on a project: the venue block, charter notes, package install and removal."""
import hashlib
import io
import json
import re
import shutil
import tempfile
import urllib.request
import zipfile
from pathlib import Path

from .manifest import Manifest, today
from .plugin import Plugin, clone_at, remote_url, source_info, tree_hash, user_plugins_dir
from .regions import remove_region, upsert_region
from .templates import copy_tree
from .venuemeta import validate
from .workspace import PROJECT_MANIFEST_REL


class VenueError(Exception):
    pass


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


def fetch_templates(pdir: Path, venue: dict, pm: Manifest, name: str) -> list:
    tpl = venue.get("template")
    if not tpl:
        return []
    for item in (tpl.get("files") if "repo" in tpl else tpl.get("extract")) or []:
        if Path(item).name == "main.tex":
            raise VenueError("template must not ship main.tex")
    paper = Path(pdir) / "paper"
    paper.mkdir(exist_ok=True)
    written = []
    if "repo" in tpl:
        remote = remote_url(tpl["repo"])
        if remote is None:
            raise VenueError(f"template.repo {tpl['repo']!r} is not a git source")
        url, _, subdir = remote
        tmp = Path(tempfile.mkdtemp(prefix="rharness-template-"))
        try:
            clone_at(url, tpl["ref"], tmp / "repo")
            base = tmp / "repo" / subdir if subdir else tmp / "repo"
            for rel in tpl["files"]:
                src = base / rel
                if not src.is_file():
                    raise VenueError(f"template file {rel} not found in {tpl['repo']}@{tpl['ref']}")
                dest = paper / Path(rel).name
                if _keep_existing(pm, name, f"paper/{dest.name}"):
                    print(f"  kept existing paper/{dest.name} (not owned by venue {name}; not overwritten)")
                    continue
                shutil.copy2(src, dest)
                written.append(f"paper/{dest.name}")
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
    else:
        try:
            with urllib.request.urlopen(tpl["url"], timeout=60) as r:
                data = r.read()
        except Exception as e:
            raise VenueError(f"template download failed: {e}")
        digest = hashlib.sha256(data).hexdigest()
        if digest != tpl["sha256"]:
            raise VenueError(f"template checksum mismatch: expected {tpl['sha256'][:12]}…, got {digest[:12]}…")
        try:
            z = zipfile.ZipFile(io.BytesIO(data))
        except zipfile.BadZipFile:
            raise VenueError("template is not a zip file")
        names = set(z.namelist())
        for member in tpl["extract"]:
            if member not in names:
                raise VenueError(f"template zip has no member {member}")
            dest = paper / Path(member).name
            if _keep_existing(pm, name, f"paper/{dest.name}"):
                print(f"  kept existing paper/{dest.name} (not owned by venue {name}; not overwritten)")
                continue
            dest.write_bytes(z.read(member))
            written.append(f"paper/{dest.name}")
    for rel in written:
        _record_paper_file(pm, pdir, name, rel)
    return written


def _project_ctx(ws, pdir: Path, pm: Manifest) -> dict:
    ctx = dict(pm.ctx)
    ctx.setdefault("slug", pdir.name)
    ctx.setdefault("title", pdir.name)
    ctx.update({"workspace": str(ws.root), "date": today()})
    return ctx


def _upsert_agents(pdir: Path, pm: Manifest, plugin: Plugin):
    snippet = plugin.agents_snippet()
    agents = pdir / "AGENTS.md"
    if not snippet or not agents.exists():
        return
    agents.write_text(upsert_region(agents.read_text(), f"plugin:{plugin.name}", snippet))
    prev = pm.entry("AGENTS.md") or {}
    pm.record("AGENTS.md", prev.get("owner", "base"), source=prev.get("source", "base/project/AGENTS.md"), region=True)


def install_package(ws, pdir: Path, plugin: Plugin, venue: dict, source: str, ref) -> list:
    pdir = Path(pdir)
    name = plugin.name
    pm = load_pm(pdir)
    written = fetch_templates(pdir, venue, pm, name)
    if plugin.project_files_dir.exists():
        w, _ = copy_tree(plugin.project_files_dir, pdir, _project_ctx(ws, pdir, pm))
        for rel in w:
            pm.record(rel, owner(name), source=f"plugins/{name}/project-files/{rel}")
        written += w
    _upsert_agents(pdir, pm, plugin)
    info = source_info(plugin.dir)
    pm.data["venue"] = venue_block(name, source, ref, info.get("commit", ""), info.get("fetched", ""),
                                   tree_hash(plugin.dir))
    charter_note(pdir, pm, f"venue target set to {name}")
    pm.save()
    set_table_cell(ws, pdir.name, f"{name} (targeted)")
    return written


def remove_package(ws, pdir: Path, name: str, note: str):
    pdir = Path(pdir)
    pm = load_pm(pdir)
    removed, kept = [], []
    for rel in pm.files_owned_by(owner(name)):
        p = pdir / rel
        if not p.exists():
            pm.forget(rel)
            continue
        if pm.is_unmodified(rel):
            p.unlink()
            removed.append(rel)
            parent = p.parent
            while parent != pdir and parent.exists() and not any(parent.iterdir()):
                parent.rmdir()
                parent = parent.parent
        else:
            kept.append(rel)
        pm.forget(rel)
    agents = pdir / "AGENTS.md"
    if agents.exists():
        agents.write_text(remove_region(agents.read_text(), f"plugin:{name}"))
        prev = pm.entry("AGENTS.md") or {}
        pm.record("AGENTS.md", prev.get("owner", "base"), source=prev.get("source", "base/project/AGENTS.md"), region=True)
    pm.data.pop("venue", None)
    charter_note(pdir, pm, note)
    pm.save()
    set_table_cell(ws, pdir.name, "-")
    return removed, kept
