# Manual checks — what human eyes caught

Archetype: D, audit log. Running catalog of what human inspection caught. Each catch becomes a regression test.

## The rule
<!-- The standing discipline. What you do on every run. -->
**Never report a [detector/screen]'s first output.** For every new run:
1. Read every [high-signal hit] end-to-end.
2. Spot-check each [category]'s [extracted unit].
3. Check traces for [degenerate outputs].

## Catches to date

### [Component]: [bug/catch short name] (YYYY-MM-DD)
<!-- What was found → fix → regression test → impact on numbers. -->
- Found by [which protocol step].
- Fix: [what changed]. [N] regression tests.
- Effect: [which numbers moved, by how much].
- Rule: [standing rule that prevents recurrence].

## Why this is in the paper's interest
<!-- Frame the audit as evidence of rigor, not embarrassment. -->
