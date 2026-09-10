# review-panel — agent orientation and spending policy

Simulates LLM reviewers (free-tier chatbots plus an official-AI-reviewer
class) against a paper PDF before submission. See README.md for the threat
model and protocol; follow the protocol exactly, especially the holdout
discipline (never look at holdout results mid-revision) and the
meaning-preserving rule.

## Spending policy (hard rules, non-negotiable)

1. **Never start a paid run without explicit user approval.** Before any
   `panel.py run` (anything that is not `--dry-run` or `estimate`), show the
   user the `panel.py estimate` output for that exact invocation and wait for
   approval in the current conversation. Approval for one run does not carry
   over to the next.
2. **Iterate cheap, confirm expensive.** Day-to-day iteration uses the
   open-weight pilot panel (`panels/aaai2027-pilot.json`). Models marked
   `"final_only": true` in panel configs run only in a final confirmation
   round, with `--final`, and only with per-run approval.
3. **Budget ceiling** (`limits.budget_usd_per_run` in `config.yaml`) stays at
   its shipped value unless the user raises it themselves.
4. **Ledger.** Append every paid run to `RUNS.md`: date, run dir, panel,
   review count, estimated cost, actual cost. Reruns must reuse existing
   results via resume-skip (same `--out` dir) rather than re-paying.

## Known traps

- Consumer chatbot defaults rotate every few months; the `target` tier's
  model ids in `panels/*.json` need re-checking each cycle.
- `paper_summary` fidelity grading is deliberately manual (needs the paper's
  one-sentence claim). Do not automate it with another LLM without checking
  the grader agrees with a human on a sample first.
- Runs append to `reviews.jsonl`; use a fresh `--out` dir per round.

## Infrastructure

OpenRouter via `OPENROUTER_API_KEY` (name only; never print the value), the
`openai` SDK, `pyyaml`, and `pdftotext` (poppler).

## Workflow reminders

- `python3 panel.py estimate --paper X [--panel Y] [--final]` is always free;
  run it liberally.
- `panel.py report` is local and free.
