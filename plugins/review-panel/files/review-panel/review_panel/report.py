"""Aggregate reviews.jsonl into a summary table and markdown report."""

from __future__ import annotations

import json
import statistics
from collections import Counter
from pathlib import Path


def _group(records: list[dict]) -> dict[tuple[str, str], list[dict]]:
    by_config: dict[tuple[str, str], list[dict]] = {}
    for record in records:
        by_config.setdefault((record["label"], record["prompt"]), []).append(record)
    return by_config


SCORE_COLUMNS = (("soundness", "sound"), ("excitement", "excite"),
                 ("contribution", "contrib"), ("presentation", "present"),
                 ("clarity", "clarity"), ("confidence", "conf"),
                 ("reproducibility", "repro"))


def _summary_table(by_config: dict) -> str:
    all_reviews = [r["review"] for group in by_config.values() for r in group if r.get("review")]
    columns = [(key, header) for key, header in SCORE_COLUMNS
               if any(isinstance(r.get(key), (int, float)) for r in all_reviews)]
    has_ratings = any(isinstance(r.get("rating"), (int, float)) for r in all_reviews)
    has_recs = any(r.get("recommendation") for r in all_reviews)
    header = (["config", "n", "parsed"] + (["rating mean±sd"] if has_ratings else [])
              + [h for _k, h in columns]
              + (["recs"] if has_recs else []))
    lines = ["| " + " | ".join(header) + " |", "|" + "---|" * len(header)]
    for (label, prompt), group in sorted(by_config.items()):
        reviews = [r["review"] for r in group if r.get("review")]
        ratings = [r["rating"] for r in reviews if isinstance(r.get("rating"), (int, float))]

        def mean_of(key: str) -> str:
            vals = [r[key] for r in reviews if isinstance(r.get(key), (int, float))]
            return f"{statistics.mean(vals):.1f}" if vals else "-"

        rating_cell = (f"{statistics.mean(ratings):.2f}±{statistics.stdev(ratings):.2f}"
                       if len(ratings) > 1 else (f"{ratings[0]:.1f}" if ratings else "-"))
        cells = [f"{label}/{prompt}", str(len(group)), str(len(reviews))]
        if has_ratings:
            cells.append(rating_cell)
        cells += [mean_of(key) for key, _h in columns]
        if has_recs:
            counts = Counter(str(r["recommendation"]) for r in reviews
                             if r.get("recommendation"))
            cells.append(", ".join(f"{value}×{count}"
                                    for value, count in sorted(counts.items())))
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


def write_report(out_dir: Path) -> str:
    records = [json.loads(line)
               for line in (out_dir / "reviews.jsonl").read_text().splitlines()]
    by_config = _group(records)
    table = _summary_table(by_config)

    sections = [table, "\n## Paper summaries (grade these against the one-sentence claim)\n"]
    for (label, prompt), group in sorted(by_config.items()):
        for record in group:
            if record.get("review"):
                review = record["review"]
                if isinstance(review.get("rating"), (int, float)):
                    outcome = f"rating {review['rating']}"
                elif review.get("recommendation"):
                    outcome = f"recommendation {review['recommendation']}"
                else:
                    outcome = "parsed review"
                sections.append(f"- **{label}/{prompt}#{record['sample']}** "
                                f"({outcome}): "
                                f"{review.get('paper_summary', '').strip()}")
    sections.append("\n## All weaknesses by config\n")
    for (label, prompt), group in sorted(by_config.items()):
        sections.append(f"\n### {label}/{prompt}")
        for record in group:
            review = record.get("review") or {}
            for weakness in review.get("weaknesses", []):
                sections.append(f"- [{record['sample']}] {weakness}")
            for revision in review.get("mandatory_revisions", []):
                sections.append(f"- [{record['sample']}] **Mandatory:** {revision}")
            for revision in review.get("optional_revisions", []):
                sections.append(f"- [{record['sample']}] Optional: {revision}")

    (out_dir / "report.md").write_text("\n".join(sections))
    return table
