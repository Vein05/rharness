"""Venue packages: source resolution, fetch, template files, install and removal, the index."""
import hashlib
import io
import json
import re
import shutil
import subprocess
import tempfile
import urllib.request
import zipfile
from pathlib import Path

from .manifest import Manifest, now_iso, today
from .paths import rharness_home
from .plugin import Plugin, PluginNotFound, clone_at, fetch_plugin, remote_url, source_info, tree_hash
from .regions import remove_region, upsert_region
from .templates import copy_tree
from .venuemeta import is_source_spec, normalize_name, split_pin
from .venuestate import (VenueError, _keep_existing, _record_paper_file, _stale, charter_note, load_pm, owner,
                         package_dir, set_table_cell, venue_block)


def template_blobs(tpl: dict) -> dict:
    """{basename: bytes} for a venue's template files, fetched but not yet written to the project."""
    if not tpl:
        return {}
    for item in (tpl.get("files") if "repo" in tpl else tpl.get("extract")) or []:
        if Path(item).name == "main.tex":
            raise VenueError("template must not ship main.tex")
    blobs = {}
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
                blobs[Path(rel).name] = src.read_bytes()
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
    else:
        if not str(tpl.get("url", "")).startswith(("https://", "file://")):
            raise VenueError(f"template.url must use https:// or file:// (got {tpl.get('url')!r})")
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
            blobs[Path(member).name] = z.read(member)
    return blobs


def fetch_templates(pdir: Path, venue: dict, pm: Manifest, name: str, blobs=None) -> list:
    """Write the venue's template files into paper/. `blobs` reuses an earlier template_blobs()."""
    tpl = venue.get("template")
    if not tpl:
        return []
    if blobs is None:
        blobs = template_blobs(tpl)
    paper = Path(pdir) / "paper"
    paper.mkdir(exist_ok=True)
    written = []
    for base, data in blobs.items():
        if _keep_existing(pm, name, f"paper/{base}"):
            print(f"  kept existing paper/{base} (not owned by venue {name}; not overwritten)")
            continue
        (paper / base).write_bytes(data)
        written.append(f"paper/{base}")
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


def install_package(ws, pdir: Path, plugin: Plugin, venue: dict, source: str, ref, note=None) -> list:
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
    pm.data["venue"]["template"] = venue.get("template")
    charter_note(pdir, pm, note or f"venue target set to {name}")
    pm.save()
    set_table_cell(ws, pdir.name, f"{name} (targeted)")
    return written


def remove_package(ws, pdir: Path, name: str, note=None):
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
    if note:
        charter_note(pdir, pm, note)
    pm.save()
    set_table_cell(ws, pdir.name, "-")
    return removed, kept


INDEX_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")


def _under_index(base: str, cfg) -> bool:
    """True when base is exactly <venue_index>/<one plain name>.

    A prefix match alone is not enough: `<index>/../evil` also starts with the index
    and would otherwise be treated as index-trusted, so its checks.py would run
    without the confirmation a foreign source needs.
    """
    prefix = cfg["venue_index"].rstrip("/") + "/"
    if not base.startswith(prefix):
        return False
    return INDEX_NAME_RE.match(base[len(prefix):].rstrip("/")) is not None


def resolve_source(tokens, cfg):
    """(spec, name_hint, from_index, ref). Bare names resolve against cfg['venue_index']."""
    if len(tokens) == 1 and is_source_spec(tokens[0]):
        base, ref = split_pin(tokens[0])
        from_index = _under_index(base, cfg) and ref is None
        return tokens[0], base.rstrip("/").rsplit("/", 1)[-1], from_index, ref
    name = normalize_name(tokens)
    if not name:
        raise VenueError(f"cannot make a venue name from {' '.join(tokens)!r}")
    return f"{cfg['venue_index']}/{name}", name, True, None


def _validate_package(plugin: Plugin, spec: str, name_hint: str):
    if plugin.scope != "project" or plugin.kind != "venue":
        raise VenueError(f"{plugin.name} is not a venue package (plugin.json needs scope=project and kind=venue)")
    if plugin.name != name_hint:
        # the cache is keyed by the name the package declares, so a package claiming
        # someone else's name would otherwise be installed as, and trusted as, that venue
        raise VenueError(f"{spec} declares name {plugin.name!r}, not {name_hint!r}")


def fetch_package(spec: str, name_hint: str, refresh: bool = False) -> Plugin:
    """The venue package for `spec`, cached at package_dir(name_hint).

    A fetch is staged in a temporary root and validated there; nothing under
    ~/.rharness/plugins/ is touched until the package has passed, so a package that
    declares another venue's name cannot overwrite that venue's cache.
    """
    cache = package_dir(name_hint)
    if not refresh and (cache / "plugin.json").exists() and source_info(cache).get("spec") == spec:
        plugin = Plugin(name_hint, cache)
        _validate_package(plugin, spec, name_hint)
        return plugin
    tmp = Path(tempfile.mkdtemp(prefix="rharness-venue-fetch-"))
    try:
        try:
            d = fetch_plugin(spec, dest_root=tmp)
        except PluginNotFound as e:
            raise VenueError(f"no venue package at {spec}: {e}")
        _validate_package(Plugin(d.name, d), spec, name_hint)
        if cache.exists():
            shutil.rmtree(cache)
        cache.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(d), str(cache))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return Plugin(name_hint, cache)


def _cached_index(idx: Path, fetched):
    try:
        return json.loads(idx.read_text()), fetched, True
    except (OSError, json.JSONDecodeError):
        return [], None, True


def fetch_index(cfg, force=False):
    """(entries, fetched_iso, cached) for the configured venue index, cached under rharness_home().

    `cached` is True when the entries come from the cache because upstream was not fetched in
    this call: either the cache is still inside the TTL, or the fetch failed.
    """
    cache_dir = rharness_home() / "venues"
    cache_dir.mkdir(parents=True, exist_ok=True)
    idx, meta = cache_dir / "INDEX.json", cache_dir / "INDEX.meta.json"
    fetched = None
    if meta.exists():
        try:
            fetched = json.loads(meta.read_text()).get("fetched")
        except json.JSONDecodeError:
            fetched = None
    fresh = fetched is not None and not _stale({"fetched": fetched})
    if idx.exists() and fresh and not force:
        return _cached_index(idx, fetched)
    remote = remote_url(cfg["venue_index"])
    if remote is not None:
        url, ref, subdir = remote
        tmp = Path(tempfile.mkdtemp(prefix="rharness-index-"))
        try:
            try:
                clone_at(url, ref, tmp / "repo")
                src = (tmp / "repo" / subdir if subdir else tmp / "repo") / "INDEX.json"
                if src.exists():
                    text = src.read_text()
                    entries = json.loads(text)  # parse before caching: malformed upstream keeps the old cache
                    idx.write_text(text)
                    fetched = now_iso()
                    meta.write_text(json.dumps({"fetched": fetched}) + "\n")
                    return entries, fetched, False
            except (PluginNotFound, OSError, subprocess.SubprocessError, json.JSONDecodeError):
                pass
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
    if idx.exists():
        return _cached_index(idx, fetched)
    return [], None, True
