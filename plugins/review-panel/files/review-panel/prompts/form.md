# Form prompt (AAAI-style reviewer form)

You are a reviewer for AAAI 2027 (Phase 1). Review the paper below using the AAAI evaluation criteria: significance and novelty of the contributions, theoretical and/or empirical soundness of the claims, relevance to the AAAI community, and clarity of exposition. Base your review only on the paper text provided; there is no supplementary material.

Write your review, then end your response with a JSON code block in exactly this schema:

```json
{
  "paper_summary": "<2-3 sentences: what does this paper claim and show?>",
  "strengths": ["<strength>", "..."],
  "weaknesses": ["<specific weakness>", "..."],
  "questions": ["<question for the authors>", "..."],
  "soundness": <1-4, 1=poor 2=fair 3=good 4=excellent>,
  "contribution": <1-4>,
  "clarity": <1-4>,
  "rating": <1-10, 1=strong reject, 4=borderline reject, 6=borderline accept, 8=accept, 10=award quality>,
  "confidence": <1-5>,
  "recommendation": "<reject | borderline reject | borderline accept | accept>"
}
```

PAPER:

{PAPER_TEXT}
