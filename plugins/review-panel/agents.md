## Pre-submission review panel

`review-panel/` simulates LLM reviewers against a paper PDF. Protocol in
`review-panel/README.md`; spending rules in `review-panel/AGENTS.md` are hard
rules: no paid run without `panel.py estimate` output shown and explicit
approval in the current conversation, and every paid run goes in
`review-panel/RUNS.md`. Never look at holdout results mid-revision.
