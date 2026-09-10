"""Release fetching and managed-file application."""
import difflib
import io
import json
import os
import shutil
import tarfile
import urllib.error
import urllib.request
from pathlib import Path

from .manifest import Manifest, today
from .plugin import template_path
from .regions import get_region, upsert_region
from .templates import render
from .workspace import PROJECT_MANIFEST_REL

REPO = "Vein05/rharness"


def resolve_version(env=None) -> str:
    env = env or os.environ
    if env.get("RHARNESS_VERSION"):
        return env["RHARNESS_VERSION"]
    with urllib.request.urlopen(f"https://api.github.com/repos/{REPO}/releases/latest", timeout=20) as r:
        return json.loads(r.read().decode())["tag_name"]


def release_url(version, env=None) -> str:
    env = env or os.environ
    plain = version[1:] if version.startswith("v") else version
    tpl = (env.get("RHARNESS_RELEASE_URL")
           or f"https://github.com/{REPO}/releases/download/{{version}}/rharness-{{plain}}.tar.gz")
    return tpl.format(version=version, plain=plain)


def sums_url(version, env=None) -> str:
    env = env or os.environ
    plain = version[1:] if version.startswith("v") else version
    tpl = env.get("RHARNESS_SUMS_URL") or f"https://github.com/{REPO}/releases/download/{{version}}/SHA256SUMS"
    return tpl.format(version=version, plain=plain)


class ChecksumError(Exception):
    pass


def _download(url: str) -> bytes:
    with urllib.request.urlopen(url, timeout=60) as r:
        return r.read()


def verify_tarball(data: bytes, asset_name: str, sums_text: str):
    """Raise ChecksumError unless SHA256SUMS lists asset_name with the digest of data."""
    import hashlib
    expected = None
    for line in sums_text.splitlines():
        parts = line.split()
        if len(parts) >= 2 and parts[-1].lstrip("*") == asset_name:
            expected = parts[0]
    actual = hashlib.sha256(data).hexdigest()
    if expected is None:
        raise ChecksumError(f"{asset_name} is not listed in SHA256SUMS")
    if expected != actual:
        raise ChecksumError(f"checksum mismatch for {asset_name}: expected {expected}, got {actual}")
    return actual


def fetch_release(version, home: Path, env=None) -> Path:
    env = env or os.environ
    url = release_url(version, env)
    dest = home / "store" / version
    if dest.exists():
        return dest
    data = _download(url)
    asset_name = url.rsplit("/", 1)[-1]
    try:
        sums = _download(sums_url(version, env)).decode("utf-8", "replace")
    except (urllib.error.URLError, OSError):
        sums = None
    if sums is None:
        if env.get("RHARNESS_INSECURE") != "1":
            raise ChecksumError(f"no SHA256SUMS available for {version}; refusing unverified download "
                                f"(set RHARNESS_INSECURE=1 to override)")
    else:
        verify_tarball(data, asset_name, sums)
    tmp = home / "store" / f".tmp-{version}"
    if tmp.exists():
        shutil.rmtree(tmp)
    tmp.mkdir(parents=True)
    with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as tf:
        for m in tf.getmembers():
            parts = m.name.split("/", 1)
            if len(parts) < 2 or not parts[1]:
                continue
            m.name = parts[1]
            if m.name.startswith("..") or m.name.startswith("/") or "/../" in m.name:
                continue
            if hasattr(tarfile, "data_filter"):
                tf.extract(m, tmp, filter="data")
            else:
                tf.extract(m, tmp)
    tmp.rename(dest)
    return dest


def relink(home: Path, version: str):
    cur = home / "store" / "current"
    if cur.is_symlink() or cur.exists():
        cur.unlink()
    cur.symlink_to(home / "store" / version, target_is_directory=True)


def _diff(old: str, new: str, name: str) -> str:
    return "".join(difflib.unified_diff(old.splitlines(True), new.splitlines(True),
                                        fromfile=f"{name} (yours)", tofile=f"{name} (template)"))


def _apply_manifest(root: Path, m: Manifest, prefix: str, ctx: dict, force: bool, dry_run: bool,
                    replaced, kept):
    for rel, entry in sorted(m.files.items()):
        if entry.get("owner") == "user" or not entry.get("source"):
            continue
        src = template_path(entry["source"])
        if src is None or not src.exists():
            continue
        target = root / rel
        label = f"{prefix}{rel}"
        raw = src.read_bytes()
        try:
            new_text = render(raw.decode("utf-8"), ctx)
        except UnicodeDecodeError:
            new_text = None
        if not target.exists():
            if not dry_run:
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(raw if new_text is None else new_text.encode())
                m.record(rel, entry["owner"], source=entry["source"], region=entry.get("region", False))
            replaced.append(label)
            continue
        if entry.get("region"):
            body = get_region(new_text or "", "base")
            if body is None:
                continue
            current = target.read_text()
            updated = upsert_region(current, "base", body)
            if updated != current:
                if not dry_run:
                    target.write_text(updated)
                    m.record(rel, entry["owner"], source=entry["source"], region=True)
                replaced.append(label)
            continue
        if new_text is None:
            continue
        if m.is_unmodified(rel) or force:
            if target.read_text() != new_text:
                if not dry_run:
                    if force and not m.is_unmodified(rel):
                        bdir = root / ".rharness" / "backup" / today()
                        bdir.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(target, bdir / rel.replace("/", "__"))
                    target.write_text(new_text)
                    m.record(rel, entry["owner"], source=entry["source"])
            replaced.append(label)
        else:
            kept.append(label)
            print(_diff(target.read_text(), new_text, label), end="")
    if not dry_run:
        m.save()


def apply_managed(ws, force=False, dry_run=False):
    replaced, kept = [], []
    ctx = {"workspace": str(ws.root), "date": today()}
    _apply_manifest(ws.root, ws.manifest, "", ctx, force, dry_run, replaced, kept)
    for slug in ws.manifest.projects:
        pdir = ws.root / slug
        pm_path = pdir / PROJECT_MANIFEST_REL
        if not pm_path.exists():
            continue
        pm = Manifest.load(pm_path)
        pctx = dict(ctx)
        pctx.update(pm.ctx)
        _apply_manifest(pdir, pm, f"{slug}/", pctx, force, dry_run, replaced, kept)
    return replaced, kept
