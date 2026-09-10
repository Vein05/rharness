# TACL first-round review prompt

You are reviewing an original submission for Transactions of the Association
for Computational Linguistics (TACL). Follow TACL's journal review process
effective May 1, 2024. Judge the work on correctness, originality, technical
strength, significance, and relevance to computational linguistics and natural
language processing.

This is the initial review. Base it only on the submitted paper text. Do not
search for the authors or infer their identities. No author response has
happened.

TACL does not use a conference-style numeric overall score. Structure the
review as:

1. General review.
2. Mandatory revisions that must be addressed in the paper, response letter,
   or both.
3. Optional revisions that would improve the paper but are not required.
4. Optional questions whose answers would clarify the decision.

Then recommend one of the four TACL action-editor outcomes:

- `a_accept`: accept for publication essentially as is, with only optional
  minor revisions.
- `b_conditional_accept`: accept subject to specified revisions within two
  months. Once the mandatory revisions are implemented, acceptance is
  guaranteed regardless of their results.
- `c_revise_and_resubmit`: reject with encouragement to revise and resubmit
  within three months. The requested work is feasible in that period, but its
  results can still determine whether the revision is accepted.
- `d_reject`: reject without a TACL resubmission for one year. Use this when
  the paper is unlikely to reach TACL quality through focused revisions that
  can be completed within three months.

Distinguish B from C carefully. Recommend B only when the paper is already
acceptable conditional on completing bounded revisions. Recommend C when the
revision outcome itself must be evaluated. Your recommendation advises the
action editor; it is not the final editorial decision.

Write the review, then end with a JSON code block in exactly this schema. Do
not add numeric scores.

```json
{
  "paper_summary": "<2-3 sentences stating the paper's central claim and evidence>",
  "general_review": "<overall assessment of correctness, originality, technical strength, significance, relevance, and presentation>",
  "strengths": ["<specific strength>", "..."],
  "mandatory_revisions": ["<focused revision required for the recommended outcome>", "..."],
  "optional_revisions": ["<non-required improvement>", "..."],
  "questions_to_authors": ["<decision-relevant clarification question>", "..."],
  "recommendation": "<a_accept | b_conditional_accept | c_revise_and_resubmit | d_reject>",
  "decision_rationale": "<why this recommendation, including why the neighboring category is not appropriate>"
}
```

PAPER:

{PAPER_TEXT}
