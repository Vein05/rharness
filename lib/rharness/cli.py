import argparse
import sys

from . import __version__


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="rharness",
                                description="Research workspace harness for coding agents.")
    p.add_argument("--workspace", help="workspace root (default: walk up from cwd)")
    p.add_argument("--dry-run", action="store_true", help="print actions, write nothing")
    p.add_argument("--yes", action="store_true", help="skip confirmations")
    sub = p.add_subparsers(dest="cmd")
    sub.add_parser("version", help="print the installed version")
    return p


def main(argv) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.cmd is None:
        parser.print_usage(sys.stderr)
        return 2
    if args.cmd == "version":
        print(__version__)
        return 0
    return 2
