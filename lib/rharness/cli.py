import argparse
import re
import sys
from pathlib import Path

from . import __version__, gitutil
from .manifest import Manifest, today
from .paths import BASE_DIR
from .templates import copy_tree
from .plugin import (PluginNotFound, apply_all_project_files, available_plugins,
                     install_plugin, scaffold_plugin, uninstall_plugin)
from .regions import get_region, upsert_region
from .workspace import (MANIFEST_REL, PROJECT_MANIFEST_REL, NotAWorkspace, Workspace,
                        detect_projects, find_root)

HARNESSES = ("claude", "codex")
DEFAULT_PLUGINS = ("rtk",)


def err(msg):
    print(f"rharness: {msg}", file=sys.stderr)


def parse_harness(value: str):
    names = [v.strip() for v in value.split(",") if v.strip()]
    bad = [n for n in names if n not in HARNESSES]
    if bad or not names:
        raise argparse.ArgumentTypeError(
            f"unknown harness {', '.join(bad) or '(empty)'}; choose from {', '.join(HARNESSES)}")
    return names


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="rharness",
                                description="Research workspace harness for coding agents.")
    p.add_argument("--workspace", help="workspace root (default: walk up from cwd)")
    p.add_argument("--dry-run", action="store_true", help="print actions, write nothing")
    p.add_argument("--yes", action="store_true", help="skip confirmations")
    sub = p.add_subparsers(dest="cmd")

    sub.add_parser("version", help="print the installed version")

    s = sub.add_parser("init", help="create a workspace")
    s.add_argument("dir", nargs="?", default=".")
    s.add_argument("--harness", type=parse_harness, default=list(HARNESSES),
                   help="comma-separated: claude,codex (default both)")
    s.add_argument("--no-plugins", action="store_true", help="skip default plugins")

    s = sub.add_parser("new", help="scaffold a paper project inside the workspace")
    s.add_argument("slug", type=slug_type)
    s.add_argument("--title", help="human title (default: slug)")

    s = sub.add_parser("add", help="install a plugin: built-in name, local path, git URL, or owner/repo[/subdir]")
    s.add_argument("name", metavar="plugin")
    s.add_argument("--refresh", action="store_true", help="re-fetch an external plugin before installing")
    s = sub.add_parser("remove", help="uninstall a plugin")
    s.add_argument("name")
    sub.add_parser("list", help="list plugins: built-in, fetched, and installed here")
    s = sub.add_parser("plugin", help="plugin authoring")
    ps = s.add_subparsers(dest="plugin_cmd")
    pn = ps.add_parser("new", help="scaffold a plugin directory")
    pn.add_argument("name", type=slug_type)
    pn.add_argument("--dir", default=".", help="parent directory (default: cwd)")

    s = sub.add_parser("adopt", help="retrofit an existing workspace or project")
    s.add_argument("dir", nargs="?", default=".")
    s.add_argument("--projects", help="comma-separated subset of project dirs")

    s = sub.add_parser("lint", help="check projects against the rules")
    s.add_argument("dir", nargs="?")
    s.add_argument("--json", action="store_true", help="one JSON object per finding")

    sub.add_parser("doctor", help="check the machine and workspace")

    s = sub.add_parser("update", help="fetch the latest release and re-apply managed files")
    s.add_argument("--no-fetch", action="store_true", help="only re-apply managed files")
    s.add_argument("--force", action="store_true", help="overwrite modified files (backed up first)")
    return p


def run_update(args):
    from .paths import rharness_home
    from .update import apply_managed, fetch_release, relink, resolve_version
    if not args.no_fetch:
        try:
            version = resolve_version()
            home = rharness_home()
            fetch_release(version, home, None)
            relink(home, version)
            print(f"fetched {version} into {home / 'store' / version}")
        except Exception as e:  # network, tar, or filesystem errors
            err(f"fetch failed: {e}")
            return 2
    ws = Workspace.open(override=args.workspace)
    replaced, kept = apply_managed(ws, force=args.force, dry_run=args.dry_run)
    ws.manifest.version = __version__
    if not args.dry_run:
        ws.manifest.save()
    print(f"{len(replaced)} replaced, {len(kept)} kept (modified; diffs above)")
    for r in replaced:
        print(f"  replaced {r}")
    for k in kept:
        print(f"  kept {k}")
    return 0


def run_doctor(args):
    from .doctor import doctor_checks
    try:
        ws = Workspace.open(override=args.workspace)
    except NotAWorkspace:
        ws = None
    failed = False
    for name, ok, detail in doctor_checks(ws):
        print(f"{'ok  ' if ok else 'FAIL'} {name}: {detail}")
        failed |= not ok
    return 1 if failed else 0


def run_lint(args):
    from .lint import (format_findings, format_json, lint_project, lint_workspace,
                       writing_template_region)
    from .lintcfg import load_lint_config
    target = Path(args.dir).resolve() if args.dir else None
    findings = []
    if target and ((target / "CHARTER.md").exists() or (target / "AGENTS.md").exists()) \
            and not (target / MANIFEST_REL).exists():
        root = find_root(target.parent)
        cfg = load_lint_config(root / "lint.toml" if root else None)
        findings = lint_project(target, cfg, writing_template_region())
    else:
        ws = Workspace.open(start=target, override=args.workspace)
        cfg = load_lint_config(ws.root / "lint.toml")
        for pdir in ws.projects():
            findings += lint_project(pdir, cfg, writing_template_region())
        findings += lint_workspace(ws, cfg)
    print(format_json(findings) if args.json else format_findings(findings))
    return 1 if findings else 0


def _table_has(agents_text, slug):
    return f"| `{slug}/` |" in agents_text


def _add_adopted_row(agents_path: Path, slug: str):
    agents = agents_path.read_text() if agents_path.exists() else ""
    if _table_has(agents, slug):
        return False
    row_text = append_project_row(agents, slug, slug)
    agents_path.write_text(row_text.replace(f"| scaffolded {today()} |", f"| adopted {today()} |"))
    return True


def adopt_workspace(root: Path, only, dry_run):
    src = BASE_DIR / "workspace"
    mpath = root / MANIFEST_REL
    m = Manifest.load(mpath) if mpath.exists() else Manifest.new(mpath, __version__)
    ctx = {"workspace": str(root), "date": today()}
    if dry_run:
        for p in sorted(x for x in src.rglob("*") if x.is_file()):
            rel = p.relative_to(src).as_posix()
            print(f"{'would keep' if (root / rel).exists() else 'would add'} {root / rel}")
    else:
        written, skipped = copy_tree(src, root, ctx)
        for rel in written:
            m.record(rel, "base", source=f"base/workspace/{rel}", region=rel in ("AGENTS.md", "CLAUDE.md"))
            print(f"  added {rel}")
        for rel in skipped:
            if m.entry(rel) is None:
                m.record(rel, "user", source=f"base/workspace/{rel}", region=rel in ("AGENTS.md", "CLAUDE.md"))
            print(f"  kept  {rel}")
        base_region = get_region((src / "AGENTS.md").read_text(), "base")
        agents = (root / "AGENTS.md").read_text()
        (root / "AGENTS.md").write_text(upsert_region(agents, "base", base_region))
    ws = Workspace(root, m)
    ensure_archetypes(ws, dry_run)
    projects = [p for p in detect_projects(root) if not only or p.name in only]
    for pdir in projects:
        slug = pdir.name
        print(f"Project {slug}:")
        scaffold_project(ws, pdir, slug, slug, dry_run)
        if dry_run:
            continue
        apply_all_project_files(ws, pdir)
        if slug not in m.projects:
            m.projects.append(slug)
        _add_adopted_row(root / "AGENTS.md", slug)
    if dry_run:
        return 0
    m.record("AGENTS.md", m.entry("AGENTS.md")["owner"], source="base/workspace/AGENTS.md", region=True)
    m.save()
    print(f"Adopted workspace at {root} ({len(projects)} projects)")
    return 0


def adopt_project(pdir: Path, dry_run):
    root = find_root(pdir.parent)
    if root:
        ws = Workspace.open(override=root)
    else:
        ws = Workspace(pdir.parent, Manifest.new(pdir.parent / MANIFEST_REL, __version__))  # never saved
    slug = pdir.name
    scaffold_project(ws, pdir, slug, slug, dry_run)
    if dry_run:
        return 0
    if root:
        apply_all_project_files(ws, pdir)
        if slug not in ws.manifest.projects:
            ws.manifest.projects.append(slug)
        if _add_adopted_row(ws.agents_path, slug):
            prev = ws.manifest.entry("AGENTS.md") or {}
            ws.manifest.record("AGENTS.md", prev.get("owner", "base"),
                               source="base/workspace/AGENTS.md", region=True)
        ws.manifest.save()
    print(f"Adopted project {slug}")
    return 0


def run_adopt(args):
    target = Path(args.dir).resolve()
    if not target.is_dir():
        err(f"{target} is not a directory")
        return 2
    only = [s.strip() for s in args.projects.split(",")] if args.projects else None
    subprojects = detect_projects(target)
    looks_like_project = (target / "CHARTER.md").exists() or (target / "AGENTS.md").exists()
    if (target / MANIFEST_REL).exists() or (subprojects and not (target / "CHARTER.md").exists()):
        return adopt_workspace(target, only, args.dry_run)
    if looks_like_project:
        return adopt_project(target, args.dry_run)
    err(f"nothing to adopt at {target}: no CHARTER.md/AGENTS.md here and no project subdirectories")
    return 1


def run_add(args):
    ws = Workspace.open(override=args.workspace)
    return install_plugin(ws, args.name, dry_run=args.dry_run, refresh=args.refresh)


def run_plugin(args):
    if args.plugin_cmd != "new":
        err("usage: rharness plugin new <name> [--dir DIR]")
        return 2
    dest = Path(args.dir).resolve()
    try:
        written = scaffold_plugin(dest, args.name)
    except FileExistsError as e:
        err(f"{e} already exists")
        return 1
    except ValueError as e:
        err(str(e))
        return 2
    print(f"Created plugin {args.name} at {dest / args.name}")
    for rel in written:
        print(f"  wrote {rel}")
    print(f"Next: edit plugin.json and agents.md, then `rharness add {dest / args.name}` to try it")
    return 0


def run_remove(args):
    ws = Workspace.open(override=args.workspace)
    if args.name not in ws.manifest.plugins:
        err(f"{args.name} is not installed")
        return 1
    return uninstall_plugin(ws, args.name, dry_run=args.dry_run)


def run_list(args):
    ws = Workspace.open(override=args.workspace)
    installed = set(ws.manifest.plugins)
    sources = ws.manifest.plugin_sources
    rows = []
    for name, plugin in available_plugins().items():
        rows.append((name, plugin.origin, "installed" if name in installed else "available",
                     sources.get(name, ""), plugin.meta.get("description", "")))
    for name in sorted(installed - set(available_plugins())):
        rows.append((name, "missing", "installed", sources.get(name, ""), "directory not found; re-add it"))
    for name, origin, status, source, desc in rows:
        tail = f"  {source}" if source else ""
        print(f"{name:14s} {origin:8s} {status:10s} {desc}{tail}")
    return 0


SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")


def slug_type(value):
    if not SLUG_RE.match(value):
        raise argparse.ArgumentTypeError("slug must be lowercase letters, digits, and hyphens")
    return value


def append_project_row(agents_text: str, slug: str, title: str) -> str:
    row = f"| `{slug}/` | {title} | TBD | scaffolded {today()} |"
    lines = agents_text.split("\n")
    header_idx = None
    for i, line in enumerate(lines):
        if line.startswith("| dir |"):
            header_idx = i
            break
    if header_idx is None:
        return agents_text.rstrip("\n") + f"\n\n| dir | paper | venue target | status |\n|---|---|---|---|\n{row}\n"
    j = header_idx + 1
    while j < len(lines) and lines[j].startswith("|"):
        j += 1
    lines.insert(j, row)
    return "\n".join(lines)


def ensure_archetypes(ws, dry_run):
    dest = ws.root / ".rharness" / "archetypes"
    if dest.exists():
        return
    if dry_run:
        print(f"would write {dest}/")
        return
    copy_tree(BASE_DIR / "archetypes", dest, {})


def write_handoff_stub(dest: Path, slug: str):
    path = dest / "handoff" / f"{today()}.md"
    if path.exists():
        return None
    path.write_text(
        f"# Handoff — {today()}\n\nRead AGENTS.md first. First session for `{slug}`.\n\n"
        "## What happened today\n\n- Project scaffolded with rharness.\n\n"
        "## Canonical artifacts\n\n- `CHARTER.md`, `spec/scoring.md`\n\n"
        "## Results so far\n\n- None.\n\n## Next up\n\n1. Fill in CHARTER.md, kill criterion first.\n"
        "2. Write spec/scoring.md.\n3. Novelty scan (archetype E).\n\n## Deadlines\n\n- None set.\n")
    return path


def scaffold_project(ws, dest: Path, slug: str, title: str, dry_run: bool):
    """Write base/project into dest. Returns the project Manifest (or None on dry run)."""
    src = BASE_DIR / "project"
    ctx = {"slug": slug, "title": title, "date": today(), "workspace": str(ws.root)}
    if dry_run:
        for p in sorted(x for x in src.rglob("*") if x.is_file()):
            rel = p.relative_to(src).as_posix()
            print(f"{'would skip' if (dest / rel).exists() else 'would write'} {dest / rel}")
        return None
    dest.mkdir(parents=True, exist_ok=True)
    written, skipped = copy_tree(src, dest, ctx)
    if not ws.wants("claude") and "CLAUDE.md" in written:
        (dest / "CLAUDE.md").unlink()
        written.remove("CLAUDE.md")
    if "AGENTS.md" in skipped:
        # existing project: insert the managed workspace-rules region, keep the user's text
        region = get_region((src / "AGENTS.md").read_text(), "base")
        agents = dest / "AGENTS.md"
        updated = upsert_region(agents.read_text(), "base", region)
        if updated != agents.read_text():
            agents.write_text(updated)
    pm_path = dest / PROJECT_MANIFEST_REL
    if pm_path.exists():
        pm = Manifest.load(pm_path)
    else:
        pm = Manifest.new(pm_path, __version__, harness=ws.manifest.harness,
                          ctx={"slug": slug, "title": title})
    region_files = ("paper/writing.md", "AGENTS.md")
    for rel in written:
        pm.record(rel, "base", source=f"base/project/{rel}", region=rel in region_files)
    for rel in skipped:
        if pm.entry(rel) is None:
            pm.record(rel, "user", source=f"base/project/{rel}", region=rel in region_files)
        elif rel == "AGENTS.md":
            pm.record(rel, pm.entry(rel)["owner"], source=f"base/project/{rel}", region=True)
    if not gitutil.is_repo(dest):
        gitutil.init_repo(dest)
    if gitutil.has_lfs():
        gitutil.git(["lfs", "install", "--local"], dest)
    else:
        err("git-lfs not found; LFS not initialised for this project")
    h = write_handoff_stub(dest, slug)
    if h:
        pm.record(h.relative_to(dest).as_posix(), "base")
    pm.save()
    for rel in written:
        print(f"  wrote {slug}/{rel}")
    for rel in skipped:
        print(f"  kept  {slug}/{rel}")
    return pm


def run_new(args) -> int:
    ws = Workspace.open(override=args.workspace)
    slug, title = args.slug, args.title or args.slug
    dest = ws.root / slug
    if dest.exists():
        err(f"{dest} already exists; use `rharness adopt {slug}` to retrofit it")
        return 1
    ensure_archetypes(ws, args.dry_run)
    scaffold_project(ws, dest, slug, title, args.dry_run)
    if args.dry_run:
        return 0
    apply_all_project_files(ws, dest)
    agents = ws.agents_path.read_text() if ws.agents_path.exists() else ""
    ws.agents_path.write_text(append_project_row(agents, slug, title))
    ws.manifest.record("AGENTS.md", "base", source="base/workspace/AGENTS.md", region=True)
    if slug not in ws.manifest.projects:
        ws.manifest.projects.append(slug)
    ws.manifest.save()
    print(f"Created project {slug} at {dest}")
    print("Next: fill in CHARTER.md (kill criterion first), then spec/scoring.md")
    return 0


def run_init(args) -> int:
    root = Path(args.dir).resolve()
    if (root / MANIFEST_REL).exists():
        err(f"{root} is already a workspace; use `rharness adopt` to refresh it")
        return 1
    src = BASE_DIR / "workspace"
    if args.dry_run:
        for p in sorted(x for x in src.rglob("*") if x.is_file()):
            rel = p.relative_to(src).as_posix()
            if rel == "CLAUDE.md" and "claude" not in args.harness:
                continue
            print(f"would write {root / rel}")
        print(f"would write {root / MANIFEST_REL}")
        return 0
    root.mkdir(parents=True, exist_ok=True)
    ctx = {"workspace": str(root), "date": today()}
    written, _ = copy_tree(src, root, ctx)
    if "claude" not in args.harness and (root / "CLAUDE.md").exists():
        (root / "CLAUDE.md").unlink()
        written.remove("CLAUDE.md")
    m = Manifest.new(root / MANIFEST_REL, __version__, harness=args.harness)
    for rel in written:
        m.record(rel, "base", source=f"base/workspace/{rel}", region=rel in ("AGENTS.md", "CLAUDE.md"))
    m.save()
    print(f"Created workspace at {root}")
    for rel in written:
        print(f"  wrote {rel}")
    if not args.no_plugins:
        ws = Workspace(root, m)
        for name in DEFAULT_PLUGINS:
            rc = install_plugin(ws, name, dry_run=False)
            if rc != 0:
                return rc
    print("Next: rharness new <slug>   (inside the workspace)")
    return 0


def main(argv) -> int:
    parser = build_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as e:
        return int(e.code) if isinstance(e.code, int) else 2
    if args.cmd is None:
        parser.print_usage(sys.stderr)
        return 2
    if args.cmd == "version":
        print(__version__)
        return 0
    handler = globals().get(f"run_{args.cmd}")
    if handler is None:
        err(f"unknown command {args.cmd}")
        return 2
    try:
        return handler(args)
    except NotAWorkspace as e:
        err(str(e))
        return 2
    except PluginNotFound as e:
        err(str(e))
        return 2
