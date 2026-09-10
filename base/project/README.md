# {{title}}

<!-- One paragraph: what the project is and what the paper claims. -->

## Install

    python3 -m venv .venv && . .venv/bin/activate
    pip install -r requirements.txt

## Run tests

    python3 -m pytest tests/ -q

## Run the main tool

<!-- Exact command. -->

## Layout

- `CHARTER.md` — the research contract. Read first.
- `AGENTS.md` — orientation for agents and collaborators.
- `spec/` — component specs, written before code.
- `research/` — the living knowledge base (see its README).
- `paper/` — LaTeX sources and the writing guide.
- `data/`, `papers/`, `traces/` — LFS-tracked.
- `handoff/`, `changelog/` — dated session records.
