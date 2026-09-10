"""Job building, cost estimation, budget guarding, and panel execution."""

from __future__ import annotations

import concurrent.futures
import json
import os
import sys
import threading
import time
from pathlib import Path

from openai import OpenAI

from .config import CONFIG, OPENROUTER_BASE, cost_of, price_of
from .inputs import load_prompt, parse_review_json, salvage_review


class BudgetGuard:
    def __init__(self, ceiling_usd: float):
        self.ceiling = ceiling_usd
        self.spent = 0.0
        self._lock = threading.Lock()

    def add(self, usd: float) -> None:
        with self._lock:
            self.spent += usd

    def exceeded(self) -> bool:
        with self._lock:
            return self.spent >= self.ceiling


def build_jobs(panel: dict, tiers: set[str], samples_cap: int | None,
               include_final: bool = False) -> list[tuple]:
    jobs = []
    for model in panel["models"]:
        if model["tier"] not in tiers:
            continue
        if model.get("final_only") and not include_final:
            continue
        samples = min(model["samples"], samples_cap or model["samples"])
        for prompt_name in model["prompts"]:
            for i in range(samples):
                jobs.append((model, prompt_name, i))
    return jobs


def estimate_cost(jobs: list[tuple], paper_text: str) -> tuple[float, list[str]]:
    input_tokens = len(paper_text) / 3.9  # calibrated on corrections-r0 actuals
    est_out = CONFIG["estimate_output_tokens"]
    per_model: dict[str, list[float]] = {}
    for model, _prompt, _i in jobs:
        pin, pout = price_of(model["id"])
        usd = input_tokens * pin + est_out.get(model["id"], est_out["default"]) * pout
        per_model.setdefault(model["label"], []).append(usd)
    lines = [f"  {label:20s} {len(costs):3d} reviews  ~${sum(costs):.2f}"
             for label, costs in per_model.items()]
    return sum(sum(c) for c in per_model.values()), lines


def already_done(results_path: Path) -> set[tuple]:
    if not results_path.exists():
        return set()
    done = set()
    for line in results_path.read_text().splitlines():
        record = json.loads(line)
        if record.get("review"):
            done.add((record["label"], record["prompt"], record["sample"]))
    return done


def call_one(client: OpenAI, model: dict, prompt_name: str, prompt_template: str,
             paper_text: str, sample_idx: int, budget: BudgetGuard) -> dict:
    prompt = prompt_template.replace("{PAPER_TEXT}", paper_text)
    extra_body = {}
    if model.get("reasoning_effort"):
        extra_body["reasoning"] = {"effort": model["reasoning_effort"]}
    record = {
        "model": model["id"], "label": model["label"], "tier": model["tier"],
        "prompt": prompt_name, "sample": sample_idx,
    }
    if budget.exceeded():
        record.update(raw=None, review=None, usage=None,
                      error=f"budget_exceeded (${budget.spent:.2f} >= ${budget.ceiling:.2f})")
        return record
    retry_cfg = CONFIG["retries"]
    for attempt in range(retry_cfg["max_attempts"]):
        try:
            response = client.chat.completions.create(
                model=model["id"],
                messages=[{"role": "user", "content": prompt}],
                max_tokens=CONFIG["limits"]["max_output_tokens"],
                extra_body=extra_body or None,
            )
            text = response.choices[0].message.content or ""
            record["raw"] = text
            record["review"] = parse_review_json(text) or salvage_review(text)
            record["usage"] = response.usage.model_dump() if response.usage else None
            budget.add(cost_of(model["id"], record["usage"]))
            record["error"] = None if record["review"] else "unparseable_json"
            return record
        except Exception as exc:  # noqa: BLE001 - record and retry
            record["error"] = f"{type(exc).__name__}: {exc}"
            if "429" in str(exc):
                time.sleep(retry_cfg.get("rate_limit_wait_s", 30) * (attempt + 1))
            else:
                time.sleep(retry_cfg["backoff_base_s"] ** attempt)
    record.setdefault("raw", None)
    record["review"] = None
    return record


def run_panel(panel: dict, paper_path: Path, out_dir: Path, tiers: set[str],
              samples_cap: int | None, include_final: bool, force: bool,
              dry_run: bool, paper_text: str) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "paper_extracted.txt").write_text(paper_text)

    jobs = build_jobs(panel, tiers, samples_cap, include_final)
    results_path = out_dir / "reviews.jsonl"
    skip = already_done(results_path)
    jobs = [(m, p, i) for m, p, i in jobs if (m["label"], p, i) not in skip]
    total_est, est_lines = estimate_cost(jobs, paper_text)
    print(f"paper: {paper_path} ({len(paper_text)} chars extracted)")
    print(f"jobs: {len(jobs)} reviews (skipping {len(skip)} already done); estimate:")
    print("\n".join(est_lines))
    print(f"  estimated total ~${total_est:.2f}, ceiling ${CONFIG['limits']['budget_usd_per_run']:.2f}")
    if dry_run:
        for model, prompt_name, i in jobs:
            print(f"  {model['label']:20s} {prompt_name:6s} sample {i}")
        return
    if total_est > CONFIG["limits"]["budget_usd_per_run"] and not force:
        sys.exit("estimate exceeds budget ceiling; raise limits.budget_usd_per_run "
                 "in config.yaml or rerun with --force")

    api_key = os.environ.get("OPENROUTER_API_KEY") or sys.exit("OPENROUTER_API_KEY not set")
    client = OpenAI(base_url=OPENROUTER_BASE, api_key=api_key)
    models = {m["label"]: m for m, _p, _i in jobs}.values()
    prompts = {name: load_prompt(name) for name in {p for m in models for p in m["prompts"]}}
    budget = BudgetGuard(CONFIG["limits"]["budget_usd_per_run"])
    concurrency = panel.get("concurrency", CONFIG["limits"]["concurrency"])

    done = 0
    with results_path.open("a") as sink, \
            concurrent.futures.ThreadPoolExecutor(concurrency) as pool:
        futures = [
            pool.submit(call_one, client, model, prompt_name, prompts[prompt_name],
                        paper_text, i, budget)
            for model, prompt_name, i in jobs
        ]
        for future in concurrent.futures.as_completed(futures):
            record = future.result()
            sink.write(json.dumps(record) + "\n")
            sink.flush()
            done += 1
            status = "ok" if record.get("review") else record.get("error")
            print(f"[{done}/{len(jobs)}] {record['label']} {record['prompt']} "
                  f"#{record['sample']}: {status} (spent ${budget.spent:.2f})", flush=True)
    print(f"wrote {results_path} | actual spend this run: ${budget.spent:.2f}", flush=True)
