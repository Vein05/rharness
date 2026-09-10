# Naive prompt (lazy reviewer, no rubric)

I'm reviewing this paper for AAAI 2027. Can you review it and tell me if it's good? Give me a rating out of 10 and whether you'd accept it.

End your response with a JSON code block in exactly this schema:

```json
{
  "paper_summary": "<2-3 sentences: what does this paper claim and show?>",
  "strengths": ["<strength>", "..."],
  "weaknesses": ["<specific weakness>", "..."],
  "questions": [],
  "soundness": <1-4>,
  "contribution": <1-4>,
  "clarity": <1-4>,
  "rating": <1-10>,
  "confidence": <1-5>,
  "recommendation": "<reject | borderline reject | borderline accept | accept>"
}
```

PAPER:

{PAPER_TEXT}
