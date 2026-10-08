"""rharness venue subcommands. Re-exports the venue state, package, and refresh helpers."""
import datetime as _dt
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from .manifest import today
from .plugin import Plugin, PluginNotFound, capability_summary, confirm, fetch_plugin, fetched_commit, source_info
from .venuemeta import days_until, primary_deadline, style_line
from .venuepkg import (_cached_index, _keep_existing, _project_ctx, _record_paper_file, _under_index,  # noqa: F401
                       _upsert_agents, _validate_package, fetch_index, fetch_package, fetch_templates,
                       install_package, remove_package, resolve_source, template_blobs, INDEX_NAME_RE)
from .venuerefresh import _ls_remote_sha, _stamp, apply_upstream, is_from_index, refresh_if_stale  # noqa: F401
from .venuestate import (AGENT_SENTENCE, LS_REMOTE_TIMEOUT, TINYTEX, TTL_HOURS, VenueError, _stale,  # noqa: F401
                         charter_note, load_pm, load_venue, owner, package_dir, read_block, set_table_cell,
                         venue_block, write_block)


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
        print(f"    add {style_line(venue, stem)} at the % rharness:venue-style line in paper/main.tex")
        main = Path(pdir) / "paper" / "main.tex"
        if main.exists() and "% rharness:venue-style" not in main.read_text(errors="replace"):
            print("    (paper/main.tex has no % rharness:venue-style marker; add the "
                  "\\usepackage line to the preamble yourself)")
    print("    build paper/main.pdf (`rharness paper build`) or download it from Overleaf into paper/main.pdf")
    for l in _engine_hint():
        print(l)
    print(f"Next: `rharness venue` for status and checks; `rharness venue lock` when the paper is committed to {plugin.name}")
    return 0


def bare_package(tokens, cfg, yes=False):
    """(plugin, venue) for `lint --venue`, or None after printing why the source needs --yes.

    A cached package past the TTL is re-fetched; when that fails the cached copy is used,
    because a refresh problem must never block lint.
    """
    spec, hint, from_index, ref = resolve_source(tokens, cfg)
    cache = package_dir(hint)
    info = source_info(cache)
    plugin = None
    if (cache / "plugin.json").exists() and info.get("spec") == spec and _stale(info):
        try:
            plugin = fetch_package(spec, hint, refresh=True)
        except VenueError:
            plugin = None
    if plugin is None:
        plugin = fetch_package(spec, hint)
    venue = load_venue(plugin.dir)
    if not from_index and not yes:
        commit = fetched_commit(plugin.dir)
        print(f"Venue package {plugin.name} from {spec}" + (f" (commit {commit[:12]})" if commit else ""))
        print(f"  checks.py: {'yes, runs in-process during this lint' if (plugin.dir / 'checks.py').exists() else 'no'}")
        print("Not run. Re-run with --yes (before the subcommand) to accept this source.")
        return None
    return plugin, venue


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
    if block.get("held"):
        out.append("  checks.py changed upstream and is held; run rharness venue update to accept it")
    return out


def cmd_status(ws, pdir, cfg, env=None):
    from . import venuecheck
    block = read_block(pdir)
    if not block:
        print(f"No venue on {pdir.name}. Attach one with `rharness venue add <venue> <year>`; `rharness venue list` shows the index.")
        return 0
    r = refresh_if_stale(ws, pdir, cfg)
    block = read_block(pdir) or block
    try:
        venue = load_venue(package_dir(block["name"]))
    except VenueError as e:
        print(f"Venue: {block['name']} ({block['state']}); package not usable: {e}. Run `rharness venue update`.")
        return 1
    for l in status_lines(pdir, block, venue):
        print(l)
    detail = "update available (run rharness venue update)" if r["status"] == "available" else r["detail"]
    print(f"  upstream: {detail}")
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


def cmd_update(ws, pdir, cfg, yes=False):
    block = read_block(pdir)
    if not block:
        print(f"rharness: {pdir.name} has no venue", file=sys.stderr)
        return 1
    if not is_from_index(block, cfg):
        # foreign source: a changed checks.py needs consent, and the very directory that was
        # inspected is the one applied — no second clone between consent and apply
        tmp = Path(tempfile.mkdtemp(prefix="rharness-venue-"))
        try:
            try:
                new_dir = fetch_plugin(block["source"], dest_root=tmp)
            except (PluginNotFound, OSError, subprocess.SubprocessError) as e:
                print(f"rharness: cannot fetch {block['source']}: {e}", file=sys.stderr)
                return 2
            cache = package_dir(block["name"])
            old = (cache / "checks.py").read_text() if (cache / "checks.py").exists() else None
            new = (new_dir / "checks.py").read_text() if (new_dir / "checks.py").exists() else None
            if old != new and not yes:
                print(f"checks.py changed upstream for {block['name']} ({block['source']}); it runs in-process during lint.")
                print(capability_summary(Plugin(new_dir.name, new_dir), ws))
                print("Re-run with --yes (before the subcommand) to accept: `rharness --yes venue update`")
                return 1
            r = refresh_if_stale(ws, pdir, cfg, force=True, prefetched=new_dir)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
    else:
        r = refresh_if_stale(ws, pdir, cfg, force=True)
    print(f"{block['name']}: {r['status']}; {r['detail']}")
    for rel in r.get("replaced", []):
        print(f"  replaced {rel}")
    return 0 if r["status"] in ("updated", "unchanged", "code-held") else 1


def cmd_change(ws, pdir, tokens, cfg, yes=False, dry_run=False):
    block = read_block(pdir)
    if not block:
        print(f"rharness: {pdir.name} has no venue; use `rharness venue add`", file=sys.stderr)
        return 1
    spec, hint, from_index, ref = resolve_source(tokens, cfg)
    if hint == block["name"]:
        print(f"{pdir.name} already targets {hint}")
        return 0
    pm = load_pm(pdir)
    files = pm.files_owned_by(owner(block["name"]))
    lines = [f"Change venue on {pdir.name}: {block['name']} -> {hint}" +
             (f" (locked since {block['locked_on']})" if block.get("state") == "locked" else "")]
    lines += [f"  would remove {r} (kept if modified)" for r in files]
    lines.append("  would install the new package's files, AGENTS.md section, deadlines, and checks; state resets to targeted")
    if dry_run:
        for l in lines:
            print(l)
        return 0
    # fetch and validate the new package before removing the old one: a typo or a
    # refused source must leave the project on the venue it already had
    plugin = fetch_package(spec, hint)
    load_venue(plugin.dir)
    if not from_index and not yes:
        print(capability_summary(plugin, ws))
        print(f"  checks.py: {'yes, runs in-process during lint' if (plugin.dir / 'checks.py').exists() else 'no'}")
        print("Not changed. Re-run with --yes (before the subcommand) to accept this source.")
        return 1
    if not confirm_or_refuse(lines, yes, "change"):
        return 1
    old = block["name"]
    removed, kept = remove_package(ws, pdir, old, note=None)
    for k in kept:
        print(f"  kept {k} (modified; now untracked)")
    return cmd_add(ws, pdir, tokens, cfg, yes=True, note=f"venue changed from {old} to {hint}")


def cmd_list(ws, cfg):
    entries, fetched, cached = fetch_index(cfg)
    if not entries:
        print(f"rharness: no venue index reachable at {cfg['venue_index']} and nothing cached", file=sys.stderr)
        return 2
    head = f"Venues in {cfg['venue_index']}"
    if cached:
        head += f" (cached {fetched or 'unknown'}; upstream not fetched)"
    print(head)
    for e in sorted(entries, key=lambda x: x.get("deadline", "")):
        print(f"  {e.get('name', ''):14s} {e.get('primary', ''):9s} {e.get('deadline', '')[:10]:10s}  {e.get('description', '')}")
    return 0


def cmd_check(ws, pdir, cfg, build=False):
    from . import venuecheck
    if build:
        from .paper import build as paper_build
        code, msg = paper_build(pdir / "paper")
        print(msg if code == 0 else f"rharness: {msg}", file=sys.stdout if code == 0 else sys.stderr)
        if code != 0:
            return code
    if not read_block(pdir):
        print(f"rharness: {pdir.name} has no venue", file=sys.stderr)
        return 1
    refresh_if_stale(ws, pdir, cfg)
    findings = venuecheck.lint_findings(pdir)
    for sev, path, msg in findings:
        print(f"{sev} {pdir.name}/{path}: {msg}")
    errors = sum(1 for f in findings if f[0] == "error")
    print(f"Summary: {errors} errors, {len(findings) - errors} warnings")
    return 1 if findings else 0
