You are simulating an AAAI 2027 reviewer who has begun by reading a paper's
title and abstract. Evaluate the abstract below without assuming that any
alternative wording exists.

Assess how clearly the abstract communicates the problem, contribution, method,
evidence, and scope to a technically sophisticated reviewer. Do not reward hype,
removed qualifications, or unsupported claims.

Use these scales:

- problem_clarity, contribution_clarity, method_specificity,
  evidence_specificity, claim_calibration: integers from 1 (poor) to 5
  (excellent).
- expected_review_score: integer from 1 to 10 predicting the eventual overall
  review score if the full paper supports the abstract. This is a framing
  diagnostic, not a substitute for reviewing the full paper.

Return only one JSON object with this exact structure:

{
  "one_sentence_contribution": "...",
  "problem_clarity": 1,
  "contribution_clarity": 1,
  "method_specificity": 1,
  "evidence_specificity": 1,
  "claim_calibration": 1,
  "expected_review_score": 1,
  "unsupported_or_overstated_claims": [],
  "reviewer_impression": "..."
}

TITLE:
Outcome Monitors: Recovery Affordances for Silent Tool Failures

ABSTRACT:

{ABSTRACT_TEXT}
