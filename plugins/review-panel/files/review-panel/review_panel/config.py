"""Config loading and per-token pricing (see config.yaml)."""

from __future__ import annotations

import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
CONFIG = yaml.safe_load((ROOT / "config.yaml").read_text())
OPENROUTER_BASE = "https://openrouter.ai/api/v1"


def price_of(model_id: str) -> tuple[float, float]:
    entry = CONFIG["pricing_usd_per_mtok"].get(model_id)
    if entry is None:
        sys.exit(f"{model_id} missing from config.yaml pricing_usd_per_mtok — add it before running")
    return entry["in"] / 1e6, entry["out"] / 1e6


def cost_of(model_id: str, usage: dict | None) -> float:
    if not usage:
        return 0.0
    pin, pout = price_of(model_id)
    return usage.get("prompt_tokens", 0) * pin + usage.get("completion_tokens", 0) * pout
