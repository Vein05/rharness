# ICLR naive prompt (lazy reviewer, pasted the PDF into a chatbot)

I got asked to review this paper for ICLR 2026 and I'm short on time. Can you read it and tell me if it's any good — should it be accepted? Give me an overall score and your honest take on its strengths and weaknesses.

ICLR 2026 scores overall rating on even values only: {0, 2, 4, 6, 8, 10}, where 6 is marginally above the bar, 8 is a good accept, 4 is marginally below, and 0-2 is a reject. Soundness, presentation, and contribution are each 1-4 (poor to excellent). Confidence is 1-5.

End your response with a JSON code block in exactly this schema:

```json
{
  "paper_summary": "<2-3 sentences: what does this paper claim and show?>",
  "strengths": ["<strength>", "..."],
  "weaknesses": ["<specific weakness>", "..."],
  "questions": [],
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
