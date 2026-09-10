import argparse
import sys
from pathlib import Path

from . import __version__
from .manifest import Manifest, today
from .paths import BASE_DIR
from .templates import copy_tree
from .workspace import MANIFEST_REL, NotAWorkspace, Workspace

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
    return p


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
        from .plugin import install_plugin
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
