# review-panel

Reusable LLM review-panel harness: simulate how LLM reviewers will read a
paper before submitting it. Works for any venue by adding a panel config and
prompts.

## Threat model (why these models)

Two kinds of LLM read your submission now:

1. **The official AI reviewer.** Some venues attach an AI-generated,
   non-decisional review to every paper (frontier reasoning model,
   multi-stage, tool use). Approximated here by the `tough` tier.
2. **The reviewer who pastes the PDF into a free chatbot.** One shot, no
   supplemental, mangled `pdftotext` input, default settings. This is the
   `target` tier: whatever the free-tier defaults are this cycle.

A `holdout` model is never consulted while revising; run it at baseline and
at the end to confirm gains transfer. Published attack-transfer results show
meaning-preserving rephrasing alone moves AI review scores by about one
point, so the canary matters.

## Protocol

- Baseline: `python3 panel.py run --paper submission.pdf --out runs/<paper>-r0`
- `python3 panel.py report --out runs/<paper>-r0`
- The key diagnostic is **paper_summary fidelity**: does each model's summary
  state the paper's actual one-sentence claim? Misread summaries localize
  framing failures (usually abstract/intro). Ratings are the symptom.
- Split deduped weaknesses: *real* (fix content) vs *misread* (fix framing).
- Revise, rerun `--tiers target` (cheap), accept only if mean rating rises
  by more than about one standard deviation AND summary fidelity holds AND
  the tough canary does not drop (canary dropping while targets rise means
  you are gaming, not clarifying).
- Final round: all tiers including holdout.
- Stay meaning-preserving. Overclaiming is counterproductive: human reviewers
  and area chairs still decide, and it is what they punish.

## Files

- `panel.py` — CLI (estimate / run / report)
- `review_panel/` — package: `config.py` (yaml + pricing), `inputs.py`
  (pdf extraction, prompts, parsing), `runner.py` (jobs, budget, execution),
  `report.py` (aggregation)
- `config.yaml` — retries, limits, budget ceiling, pricing table. Update the
  pricing table before adding a model; a model missing there refuses to run.
- `panels/` — venue panel configs (`aaai2027*.json`, `iclr2026.json`,
  `tacl.json`, `abstract-pilot.json`)
- `prompts/` — rubric'd and lazy reviewer prompts per venue form
- `runs/<paper>-r<n>/` — reviews.jsonl, extracted text, report.md (gitignored)
- `AGENTS.md` — spending policy (hard rules); `RUNS.md` — spend ledger

## Costs

Run `panel.py estimate` before every run. The cost ladder goes zero-cost
panel, open-weight pilot, real panel without final-only models, full final
panel. Only the last two need approval, and every paid run needs it.
