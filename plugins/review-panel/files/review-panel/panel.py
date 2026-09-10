#!/usr/bin/env python3
"""LLM review panel CLI: simulate how LLM reviewers read a paper one-shot.

  python3 panel.py estimate --paper X.pdf [--panel P] [--final]     # free
  python3 panel.py run --paper X.pdf --out runs/NAME [--dry-run]    # paid: see CLAUDE.md
  python3 panel.py report --out runs/NAME                           # free

Protocol and threat model: README.md. Spending policy: CLAUDE.md.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from review_panel.config import CONFIG, ROOT
from review_panel.inputs import extract_pdf_text
from review_panel.report import write_report
from review_panel.runner import build_jobs, estimate_cost, run_panel


def cmd_estimate(args: argparse.Namespace) -> None:
    panel = json.loads(Path(args.panel).read_text())
    paper_text = extract_pdf_text(Path(args.paper))
    jobs = build_jobs(panel, set(args.tiers.split(",")), args.samples_cap, args.final)
    total, lines = estimate_cost(jobs, paper_text)
    print(f"panel: {panel['name']}  paper: ~{int(len(paper_text) / 3.9)} input tokens/review")
    print("\n".join(lines))
    print(f"  {'TOTAL':20s} {len(jobs):3d} reviews  ~${total:.2f}"
          f"  (budget ceiling ${CONFIG['limits']['budget_usd_per_run']:.2f})")


def cmd_run(args: argparse.Namespace) -> None:
    panel = json.loads(Path(args.panel).read_text())
    paper_text = extract_pdf_text(Path(args.paper))
    run_panel(panel, Path(args.paper), Path(args.out), set(args.tiers.split(",")),
              args.samples_cap, args.final, args.force, args.dry_run, paper_text)


def cmd_report(args: argparse.Namespace) -> None:
    table = write_report(Path(args.out))
    print(table)
    print(f"\nfull report: {Path(args.out) / 'report.md'}")


def add_selection_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--paper", required=True)
    parser.add_argument("--panel", default=str(ROOT / "panels" / "aaai2027.json"))
    parser.add_argument("--tiers", default="target,tough,holdout")
    parser.add_argument("--samples-cap", type=int, default=None)
    parser.add_argument("--final", action="store_true",
                        help="include final_only models (needs per-run user approval, see CLAUDE.md)")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)

    run_parser = sub.add_parser("run")
    add_selection_arguments(run_parser)
    run_parser.add_argument("--out", required=True)
    run_parser.add_argument("--dry-run", action="store_true")
    run_parser.add_argument("--force", action="store_true",
                            help="run even if the estimate exceeds the budget ceiling")
    run_parser.set_defaults(func=cmd_run)

    est_parser = sub.add_parser("estimate")
    add_selection_arguments(est_parser)
    est_parser.set_defaults(func=cmd_estimate)

    report_parser = sub.add_parser("report")
    report_parser.add_argument("--out", required=True)
    report_parser.set_defaults(func=cmd_report)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
