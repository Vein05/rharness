# ICLR form prompt (real ICLR 2026 reviewer form)

You are a reviewer for ICLR 2026. Review the paper below following the ICLR reviewer guidelines. Summarize what the paper claims to contribute; list its strong and weak points; assess soundness, presentation, and contribution; and state your recommendation. Base your review only on the paper text provided; there is no supplementary material and no rebuttal has happened yet — this is your initial review.

Score on the exact ICLR 2026 scales:

- **rating** (overall): even values only, one of {0, 2, 4, 6, 8, 10}.
  - 10 = strong accept, should be highlighted at the conference
  - 8 = accept, good paper
  - 6 = marginally above the acceptance threshold
  - 4 = marginally below the acceptance threshold
  - 2 = reject, not good enough
  - 0 = strong reject
- **soundness**, **presentation**, **contribution**: each 1-4 (1 = poor, 2 = fair, 3 = good, 4 = excellent).
- **confidence**: 1-5 (5 = absolutely certain; 4 = confident; 3 = fairly confident; 2 = willing to defend but may have missed parts; 1 = educated guess).

Write your review, then end your response with a JSON code block in exactly this schema:

```json
{
  "paper_summary": "<2-3 sentences: what does this paper claim and show?>",
  "strengths": ["<strength>", "..."],
  "weaknesses": ["<specific weakness>", "..."],
  "questions": ["<question for the authors>", "..."],
  "soundness": <1-4>,
  "presentation": <1-4>,
  "contribution": <1-4>,
  "rating": <one of 0, 2, 4, 6, 8, 10>,
  "confidence": <1-5>,
  "recommendation": "<reject | borderline reject | borderline accept | accept>"
}
```

PAPER:

{PAPER_TEXT}
