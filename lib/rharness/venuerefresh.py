"""Venue refresh: TTL staleness, upstream comparison, applying a new package to a project."""
import json
import shutil
import subprocess
import tempfile
from pathlib import Path

from .manifest import now_iso, today
from .paths import rharness_home
from .plugin import Plugin, PluginNotFound, fetch_plugin, remote_url, source_info, tree_hash
from .venuepkg import _project_ctx, _under_index, _upsert_agents, fetch_templates, template_blobs
from .venuestate import LS_REMOTE_TIMEOUT, _stale, load_pm, load_venue, owner, package_dir, read_block, write_block


def is_from_index(block, cfg) -> bool:
    return _under_index(block.get("source", ""), cfg) and not block.get("ref")


def _ls_remote_sha(spec: str):
    remote = remote_url(spec)
    if remote is None:
        return None
    url, ref, _ = remote
    try:
        r = subprocess.run(["git", "ls-remote", url, ref or "HEAD"], capture_output=True, text=True,
                           timeout=LS_REMOTE_TIMEOUT)
    except (OSError, subprocess.TimeoutExpired):
        return None
    if r.returncode != 0 or not r.stdout.strip():
        return None
    return r.stdout.split()[0]


def _stamp(pdir, block, **fields):
    block.update(fields)
    write_block(pdir, block)
    cache = package_dir(block["name"])
    info = source_info(cache)
    info.update({k: v for k, v in fields.items() if k in ("commit", "fetched")})
    (cache / ".rharness-source.json").write_text(json.dumps(info, indent=2) + "\n")


def apply_upstream(ws, pdir, block, new_dir: Path, cfg, allow_code: bool) -> list:
    """Swap the cached package for new_dir, keeping modified project files as they are."""
    name = block["name"]
    cache = package_dir(name)
    held = False
    old_checks = (cache / "checks.py").read_text() if (cache / "checks.py").exists() else None
    new_checks = (new_dir / "checks.py").read_text() if (new_dir / "checks.py").exists() else None
    new_venue = load_venue(new_dir)
    old_tpl = block.get("template")
    # fetch the new template first: a failure here must leave both the cache and the
    # project files on the old venue, so the next refresh retries from a consistent state
    blobs = template_blobs(new_venue.get("template")) if new_venue.get("template") != old_tpl else None
    if cache.exists():
        bdir = rharness_home() / "backup" / today() / name
        if bdir.exists():
            shutil.rmtree(bdir)
        bdir.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(cache, bdir)
        shutil.rmtree(cache)
    shutil.copytree(new_dir, cache)
    if not allow_code and old_checks != new_checks:
        held = True
        if old_checks is None:
            (cache / "checks.py").unlink()
        else:
            (cache / "checks.py").write_text(old_checks)
    plugin = Plugin(name, cache)
    venue = load_venue(cache)
    pm = load_pm(pdir)
    replaced = []
    ctx = _project_ctx(ws, pdir, pm)
    from .templates import render
    for rel in pm.files_owned_by(owner(name)):
        e = pm.entry(rel)
        if not e.get("source"):
            continue
        src = plugin.project_files_dir / e["source"].split("/project-files/", 1)[1]
        if src.exists() and pm.is_unmodified(rel):
            (pdir / rel).write_text(render(src.read_text(), ctx))
            pm.record(rel, owner(name), source=e["source"])
            replaced.append(rel)
    if venue.get("template") != old_tpl:
        for rel in [r for r in pm.files_owned_by(owner(name)) if not pm.entry(r).get("source")]:
            if pm.is_unmodified(rel):
                (pdir / rel).unlink(missing_ok=True)
                pm.forget(rel)
        replaced += fetch_templates(pdir, venue, pm, name, blobs=blobs)
    _upsert_agents(pdir, pm, plugin)
    pm.save()
    info = source_info(cache)
    _stamp(pdir, read_block(pdir), commit=info.get("commit", block.get("commit", "")),
           fetched=info.get("fetched", now_iso()), tree=tree_hash(cache), template=venue.get("template"),
           held=held)
    block["held"] = held
    return replaced


def refresh_if_stale(ws, pdir, cfg, force=False, now=None, prefetched=None) -> dict:
    """Bring the cached venue package up to date when the TTL has passed. Never raises for network trouble.

    `prefetched` is a directory holding an already fetched package; when given, neither
    ls-remote nor a fetch runs and that directory is applied as-is.
    """
    block = read_block(pdir)
    if not block:
        return {"status": "none", "detail": "no venue"}
    if block.get("ref") and not force:
        return {"status": "pinned", "detail": f"pinned to {block['ref']}; `rharness venue update` re-fetches that ref"}
    if not force and not _stale(block, now=now):
        return {"status": "fresh", "detail": "fetched within 24h"}
    spec = block["source"]
    if not force and prefetched is None:
        tip = _ls_remote_sha(spec)
        if tip is None:
            return {"status": "offline", "detail": "upstream not reachable"}
        if tip == block.get("commit"):
            _stamp(pdir, block, fetched=now_iso())
            return {"status": "unchanged", "detail": "upstream tip equals the cached commit"}
    tmp = Path(tempfile.mkdtemp(prefix="rharness-venue-"))
    try:
        if prefetched is not None:
            new_dir = Path(prefetched)
        else:
            try:
                new_dir = fetch_plugin(spec, dest_root=tmp)
            except (PluginNotFound, OSError, subprocess.SubprocessError):
                return {"status": "offline", "detail": "upstream not reachable"}
        new_tree = tree_hash(new_dir)
        new_info = source_info(new_dir)
        if new_tree == block.get("tree"):
            _stamp(pdir, block, fetched=now_iso(), commit=new_info.get("commit", block.get("commit", "")))
            return {"status": "unchanged", "detail": "package content unchanged"}
        locked = block.get("state") == "locked"
        from_index = is_from_index(block, cfg)
        if locked and not force:
            return {"status": "available", "detail": "update available; locked venues update only with `rharness venue update`"}
        replaced = apply_upstream(ws, pdir, block, new_dir, cfg, allow_code=(from_index or force))
        if block.get("held"):
            return {"status": "code-held",
                    "detail": "metadata updated; checks.py changed upstream and waits for `rharness venue update`",
                    "replaced": replaced}
        return {"status": "updated", "detail": f"package updated to {new_info.get('commit', '')[:12]}",
                "replaced": replaced}
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
