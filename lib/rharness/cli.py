import argparse
import re
import sys
from pathlib import Path

from . import __version__, gitutil
from .manifest import Manifest, today
from .paths import BASE_DIR
from .templates import copy_tree
from .plugin import (PluginNotFound, apply_all_project_files, install_plugin,
                     list_available, uninstall_plugin)
from .workspace import MANIFEST_REL, PROJECT_MANIFEST_REL, NotAWorkspace, Workspace

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

    s = sub.add_parser("add", help="install a plugin")
    s.add_argument("name")
    s = sub.add_parser("remove", help="uninstall a plugin")
    s.add_argument("name")
    sub.add_parser("list", help="list plugins")
    return p


def run_add(args):
    ws = Workspace.open(override=args.workspace)
    return install_plugin(ws, args.name, dry_run=args.dry_run)


def run_remove(args):
    ws = Workspace.open(override=args.workspace)
    if args.name not in ws.manifest.plugins:
        err(f"{args.name} is not installed")
        return 1
    return uninstall_plugin(ws, args.name, dry_run=args.dry_run)


def run_list(args):
    ws = Workspace.open(override=args.workspace)
    installed = set(ws.manifest.plugins)
    for name in list_available():
        print(f"{name:14s} {'installed' if name in installed else 'available'}")
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
    pm_path = dest / PROJECT_MANIFEST_REL
    if pm_path.exists():
        pm = Manifest.load(pm_path)
    else:
        pm = Manifest.new(pm_path, __version__, harness=ws.manifest.harness,
                          ctx={"slug": slug, "title": title})
    for rel in written:
        pm.record(rel, "base", source=f"base/project/{rel}", region=rel == "paper/writing.md")
    for rel in skipped:
        if pm.entry(rel) is None:
            pm.record(rel, "user", region=rel == "paper/writing.md")
    if not gitutil.is_repo(dest):
        gitutil.git(["init", "-q"], dest)
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
