"""Venue state on a project: the venue block, charter notes, package install and removal."""
import datetime as _dt
import hashlib
import io
import json
import re
import shutil
import sys
import tempfile
import urllib.request
import zipfile
from pathlib import Path

from .manifest import Manifest, today
from .plugin import (Plugin, PluginNotFound, capability_summary, clone_at, confirm, fetch_plugin,
                     remote_url, source_info, tree_hash, user_plugins_dir)
from .regions import remove_region, upsert_region
from .templates import copy_tree
from .venuemeta import (days_until, is_source_spec, normalize_name, primary_deadline,
                        split_pin, validate)
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


AGENT_SENTENCE = ("If you are an agent, confirm with the user before re-running as "
                  "`rharness --yes venue {sub} ...`: this swaps the paper style, the check set, "
                  "and the deadline agents see.")
TINYTEX = 'wget -qO- "https://yihui.org/tinytex/install-bin-unix.sh" | sh'


def resolve_source(tokens, cfg):
    """(spec, name_hint, from_index, ref). Bare names resolve against cfg['venue_index']."""
    if len(tokens) == 1 and is_source_spec(tokens[0]):
        base, ref = split_pin(tokens[0])
        from_index = base.startswith(cfg["venue_index"].rstrip("/") + "/") and ref is None
        return tokens[0], base.rstrip("/").rsplit("/", 1)[-1], from_index, ref
    name = normalize_name(tokens)
    if not name:
        raise VenueError(f"cannot make a venue name from {' '.join(tokens)!r}")
    return f"{cfg['venue_index']}/{name}", name, True, None


def fetch_package(spec: str, name_hint: str, refresh: bool = False) -> Plugin:
    cache = package_dir(name_hint)
    if not refresh and (cache / "plugin.json").exists() and source_info(cache).get("spec") == spec:
        plugin = Plugin(name_hint, cache)
    else:
        try:
            d = fetch_plugin(spec)
        except PluginNotFound as e:
            raise VenueError(f"no venue package at {spec}: {e}")
        plugin = Plugin(d.name, d)
    if plugin.scope != "project" or plugin.kind != "venue":
        raise VenueError(f"{plugin.name} is not a venue package (plugin.json needs scope=project and kind=venue)")
    return plugin


def confirm_or_refuse(lines, yes: bool, sub: str) -> bool:
    for l in lines:
        print(l)
    if yes:
        return True
    if confirm(f"Proceed with `venue {sub}`?"):
        return True
    print(AGENT_SENTENCE.format(sub=sub))
    return False


def _engine_hint():
    if shutil.which("latexmk") or shutil.which("pdflatex"):
        return []
    return [f"  No TeX engine on PATH. Optional: install TinyTeX with `{TINYTEX}`, or download the compiled PDF "
            "from Overleaf into paper/main.pdf; the page check needs one of the two."]


def cmd_add(ws, pdir, tokens, cfg, yes=False, dry_run=False, refresh=False, note=None):
    if read_block(pdir) and note is None:
        print(f"rharness: {pdir.name} already targets {read_block(pdir)['name']}; use `rharness venue change`", file=sys.stderr)
        return 1
    spec, hint, from_index, ref = resolve_source(tokens, cfg)
    plugin = fetch_package(spec, hint, refresh=refresh)
    venue = load_venue(plugin.dir)
    if dry_run:
        print(f"would install venue {plugin.name} into {pdir.name} from {spec}")
        return 0
    if not from_index:
        lines = [capability_summary(plugin, ws),
                 f"  checks.py: {'yes, runs in-process during lint' if (plugin.dir / 'checks.py').exists() else 'no'}"]
        if not yes:
            for l in lines:
                print(l)
            print("Not installed. Re-run with --yes (before the subcommand) to accept this source.")
            return 1
    written = install_package(ws, pdir, plugin, venue, spec, ref, note=note)
    print(f"Installed venue {plugin.name} into {pdir.name} (targeted)")
    for rel in written:
        print(f"  wrote {pdir.name}/{rel}")
    stem = None
    tpl = venue.get("template") or {}
    for rel in tpl.get("files", []) + tpl.get("extract", []):
        if rel.endswith((".sty", ".cls")):
            stem = Path(rel).stem
            break
    print("  These findings are expected to be open until the agent acts on them:")
    if stem:
        print(f"    add \\usepackage{{{stem}}} at the % rharness:venue-style line in paper/main.tex")
    print("    build paper/main.pdf (`rharness paper build`) or download it from Overleaf into paper/main.pdf")
    for l in _engine_hint():
        print(l)
    print(f"Next: `rharness venue` for status and checks; `rharness venue lock` when the paper is committed to {plugin.name}")
    return 0


def _age_days(iso: str) -> int:
    try:
        t = _dt.datetime.fromisoformat(iso)
    except (TypeError, ValueError):
        return 0
    now = _dt.datetime.now(tz=t.tzinfo) if t.tzinfo else _dt.datetime.now()
    return max(0, (now - t).days)


def status_lines(pdir, block, venue, now=None):
    out = [f"Venue: {block['name']} ({block['state']}" + (f", locked {block['locked_on']}" if block.get("locked_on") else "") + ")"]
    pk, _ = primary_deadline(venue)
    for key, iso in venue["deadlines"].items():
        d = days_until(iso, now=now)
        when = f"in {d} days" if d >= 0 else f"{-d} days ago"
        out.append(f"  {key} deadline {iso} {when}" + (" (primary)" if key == pk else ""))
    out.append(f"  package commit {block.get('commit', '')[:12]} fetched {block.get('fetched', '?')} "
               f"({_age_days(block.get('fetched', ''))} days old)" + (f", pinned to {block['ref']}" if block.get("ref") else ""))
    return out


def cmd_status(ws, pdir, cfg, env=None):
    from . import venuecheck
    block = read_block(pdir)
    if not block:
        print(f"No venue on {pdir.name}. Attach one with `rharness venue add <venue> <year>`; `rharness venue list` shows the index.")
        return 0
    try:
        venue = load_venue(package_dir(block["name"]))
    except VenueError as e:
        print(f"Venue: {block['name']} ({block['state']}); package not usable: {e}. Run `rharness venue update`.")
        return 1
    for l in status_lines(pdir, block, venue):
        print(l)
    findings = venuecheck.lint_findings(pdir, env=env)
    print("Checks:")
    if not findings:
        print("  none")
    for sev, path, msg in findings:
        print(f"  {sev} {pdir.name}/{path}: {msg}")
    return 0


def _scoring_proposed(pdir) -> bool:
    f = Path(pdir) / "spec" / "scoring.md"
    return f.exists() and re.search(r"^Status: proposed", f.read_text(errors="replace"), re.M) is not None


def cmd_lock(ws, pdir, cfg):
    from .venuecheck import _success_not_yet
    block = read_block(pdir)
    if not block:
        print(f"rharness: {pdir.name} has no venue; `rharness venue add` first", file=sys.stderr)
        return 1
    if block["state"] == "locked":
        print(f"{block['name']} is already locked (since {block['locked_on']})")
        return 0
    if _success_not_yet(pdir):
        print("warning: the success criterion in CHARTER.md is still NOT YET; locking a venue before the result exists is a hope, not a plan")
    if _scoring_proposed(pdir):
        print("warning: spec/scoring.md is still proposed; freeze the headline table before locking")
    pm = load_pm(pdir)
    block["state"], block["locked_on"] = "locked", today()
    pm.data["venue"] = block
    charter_note(pdir, pm, f"venue {block['name']} locked")
    pm.save()
    set_table_cell(ws, pdir.name, f"{block['name']} (locked)")
    print(f"Locked {block['name']} on {pdir.name}; venue checks now report at full severity")
    return 0


def cmd_unlock(ws, pdir, cfg, yes=False):
    block = read_block(pdir)
    if not block or block["state"] != "locked":
        print(f"rharness: {pdir.name} has no locked venue", file=sys.stderr)
        return 1
    if not confirm_or_refuse([f"Unlock {block['name']} on {pdir.name} (locked {block['locked_on']}); venue checks drop to warnings."],
                             yes, "unlock"):
        return 1
    pm = load_pm(pdir)
    block["state"], block["locked_on"] = "targeted", None
    pm.data["venue"] = block
    charter_note(pdir, pm, f"venue {block['name']} unlocked")
    pm.save()
    set_table_cell(ws, pdir.name, f"{block['name']} (targeted)")
    print(f"Unlocked {block['name']} on {pdir.name}")
    return 0


def cmd_remove(ws, pdir, cfg, yes=False, dry_run=False):
    block = read_block(pdir)
    if not block:
        print(f"rharness: {pdir.name} has no venue", file=sys.stderr)
        return 1
    pm = load_pm(pdir)
    files = pm.files_owned_by(owner(block["name"]))
    lines = [f"Remove venue {block['name']} from {pdir.name}:"] + [f"  would remove {r} (kept if modified)" for r in files] + \
            ["  would drop the AGENTS.md venue section, the venue block, and the deadline shown to agents"]
    if dry_run:
        for l in lines:
            print(l)
        return 0
    if not confirm_or_refuse(lines, yes, "remove"):
        return 1
    removed, kept = remove_package(ws, pdir, block["name"], f"venue {block['name']} removed")
    for r in removed:
        print(f"  removed {r}")
    for k in kept:
        print(f"  kept {k} (modified; now untracked)")
    print(f"Removed venue {block['name']} from {pdir.name}")
    return 0


def cmd_list(ws, cfg):
    raise VenueError("venue list is not implemented yet")


def cmd_change(ws, pdir, tokens, cfg, yes=False, dry_run=False):
    raise VenueError("venue change is not implemented yet")


def cmd_check(ws, pdir, cfg, build=False):
    raise VenueError("venue check is not implemented yet")


def cmd_update(ws, pdir, cfg, yes=False):
    raise VenueError("venue update is not implemented yet")
