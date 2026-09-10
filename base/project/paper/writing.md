# Writing guide — {{title}}

**Created:** {{date}}. Generic sections (1, 3, 4, 5, 9) are managed by
rharness and shared across projects. Project-specific sections (2, 6, 7, 8)
are filled in as the paper takes shape.
**Evidence authority:** `../research/SCORES.md` (when it exists) and the
dated research records.
**Scope authority:** `../CHARTER.md`.

This guide controls how the paper and the living docs explain the work. It
does not change a frozen claim, promote an exploratory result, or authorize
a number absent from the evidence ledger.

<!-- rharness:begin base -->
## 1. The three-reader test

Write every main-text section, and every living doc, for three people at
once:

1. A final-year secondary-school computer science student should understand
   the failure, the main comparison, and why it matters on the first pass.
2. A PhD student in the field should be able to recover the design,
   evidence, and limits without guessing.
3. A senior scientist should be able to read quickly without translating
   inflated language or repeated defenses.

If the student cannot retell the main result, the prose is too compressed.
If the PhD reader cannot tell what was held fixed, the prose is too vague.
If the senior reader feels that a paragraph repeats itself, cut or combine
it.

## 3. Default prose rules

- Choose the simplest accurate word.
- Give each sentence one main job.
- Give each paragraph one argumentative job.
- State the claim, then the evidence, then what the evidence changes.
- Put the subject and verb before a technical term or equation.
- Explain a distinction with an example before naming it.
- Put a necessary qualification after the claim it limits.
- Keep internal experiment codes in Methods, tables, or the appendix.
- Use concrete verbs such as `keeps`, `changes`, `replaces`, `retrieves`,
  `opens`, `chooses`, and `serves`.
- If a sentence invites rereading, rewrite it.

Technical precision does not require technical-sounding prose. Once the
example is on the page, prefer the plain phrase over the label: "the old
sentence" over "the superseded statement", "in front of the model" over
"surfaced", "the model chose the old one" over "resolution failure", "any
kind of system" over "paradigm-agnostic". Record the project's own
preferred terms in section 3 below.

## 4. Do not turn a useful pattern into a template

Claim, evidence, and interpretation is a reading rhythm, not a form that
every paragraph must visibly repeat. Use it where it clarifies the
argument. Do not add an interpretation sentence that merely restates the
claim.

The title, abstract, Figure 1, section openings, and conclusion should
preserve one scientific meaning without copying the same prose. Each
occurrence has a different job:

- the title names the phenomenon;
- the abstract gives the shortest complete argument;
- Figure 1 makes the transformation visible;
- section openings advance the evidence;
- the conclusion states the durable lesson.

Before repeating a claim, ask what new work the repetition performs. If
the answer is "emphasis," keep the strongest version once.

## 5. Banned or strongly discouraged formats

- No em dashes. Use a period, comma, colon, or semicolon.
- Do not repeatedly use "X, not Y" or "This is not X. It is Y." State the
  positive claim and give the boundary once.
- Do not use an `ABC: XYZ` title merely to sound like a paper.
- Do not write a numbered contribution list as one dense prose paragraph.
- Do not open the abstract with field-wide motivation or a taxonomy.
- Do not turn the abstract into an inventory of every model, control, and
  result.
- Do not stack setup, result, limitation, and interpretation in one
  sentence.
- Do not use `First`, `Second`, and `Third` to disguise a list of loosely
  connected claims.
- Do not put a load-bearing result inside parentheses.
- Do not repeat every value from a table or figure in the surrounding
  prose.
- Do not make every paragraph sound like a response to a hostile reviewer.
- Do not introduce a new label when an existing plain term already works.

Suspect filler includes `it is important to note`, `this highlights the
need`, `robustly demonstrates`, `fundamentally`, `localizes`,
`operationalizes`, and `provides an instrument for`. Use such language
only when the exact meaning is necessary and immediately clear.

## 9. Final reading audit

Read the title, abstract, Figure 1, section openings, captions, and
conclusion as one short paper. A reader should be able to answer:

1. What was the input, and what did the system do with it?
2. What did the experiment hold fixed between the easy and hard conditions?
3. Where did the failure happen, for which systems?
4. Which interventions closed the gap, and which did not?
5. What did the study not establish?

Then read the full paper for duplication. Remove adjacent sentences that
make the same claim, numbers repeated without a new purpose, and caveats
already stated in the correct section. Clarity takes priority over
symmetry, quotas, and rhetorical formulas.
<!-- rharness:end base -->

## 2. The paper in plain language

<!-- Two paragraphs a smart outsider could repeat back. One concrete
     example, then the name of the phenomenon. The benchmark or tool is
     the instrument and must not displace the phenomenon as the subject. -->

## 3. Preferred plain terms

| jargon | plain term we use |
|---|---|

## 6. Abstract contract

<!-- The sentences the abstract must contain, in order. One story, roughly
     130 to 170 readable words, at most two headline numeric events,
     statistical detail in Results. -->

## 7. Figures and captions

Every figure answers one question. Every panel must add information
unavailable from another panel. A caption starts with the takeaway, then
explains only what is needed to read the marks.

<!-- Figure 1 owns: [the example and the stages]. Later figures should not
     repeat it unless the comparison changes. -->

## 8. Section-level term list

<!-- Per section: the terms introduced there and nowhere earlier. Define
     each once with the example; do not alternate synonyms. -->
