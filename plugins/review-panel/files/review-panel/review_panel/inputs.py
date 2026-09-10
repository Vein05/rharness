"""Paper text extraction, prompt loading, and review-JSON parsing."""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

from .config import ROOT


def _is_review(value: object) -> bool:
    """Accept numeric conference reviews and recommendation-only journal reviews."""

    if not isinstance(value, dict):
        return False
    return isinstance(value.get("rating"), (int, float)) or bool(value.get("recommendation"))


def extract_pdf_text(pdf: Path) -> str:
    out = subprocess.run(
        ["pdftotext", "-enc", "UTF-8", str(pdf), "-"],
        capture_output=True, check=True,
    )
    return out.stdout.decode("utf-8", errors="replace")


def load_prompt(name: str) -> str:
    text = (ROOT / "prompts" / f"{name}.md").read_text()
    return re.sub(r"^#[^\n]*\n+", "", text)


def parse_review_json(text: str) -> dict | None:
    blocks = re.findall(r"```(?:json)?\s*(\{.*?\})\s*```", text, flags=re.DOTALL)
    for raw in reversed(blocks):
        value = _try_load(raw)
        if value is not None:
            return value
    decoder = json.JSONDecoder()
    for start in reversed([m.start() for m in re.finditer(r"\{", text)]):
        try:
            value, _ = decoder.raw_decode(text[start:])
        except json.JSONDecodeError:
            continue
        if _is_review(value):
            return value
    return None


def _try_load(raw: str) -> dict | None:
    try:
        value = json.loads(raw)
    except json.JSONDecodeError:
        return None
    return value if _is_review(value) else None


def salvage_review(text: str) -> dict | None:
    """Recover scores from malformed JSON (unescaped quotes etc.)."""
    review: dict = {"salvaged": True}
    for key in ("soundness", "contribution", "presentation", "clarity", "rating", "confidence"):
        match = re.search(rf'"{key}"\s*:\s*(\d+(?:\.\d+)?)', text)
        if match:
            review[key] = float(match.group(1)) if "." in match.group(1) else int(match.group(1))
    match = re.search(r'"recommendation"\s*:\s*"([^"]*)"', text)
    if match:
        review["recommendation"] = match.group(1)
    match = re.search(r'"paper_summary"\s*:\s*"((?:[^"\\]|\\.)*)"', text)
    if match:
        review["paper_summary"] = match.group(1)
    return review if _is_review(review) else None
