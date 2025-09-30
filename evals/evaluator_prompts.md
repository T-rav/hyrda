# Langfuse Evaluator Configurations

Copy-paste these into your Langfuse evaluator setup. Each evaluator has 3 sections:

## 1. Professional Tone Evaluator

**Name:** `professional_tone`

**Prompt:**
```
You are evaluating an AI assistant's response for professional communication standards.

EVALUATION CRITERIA:
- Uses professional, business-appropriate language
- Appropriate for executive-level interactions
- Avoids overly casual expressions or slang
- Maintains accessibility while being professional

USER INPUT: {{input}}
AI RESPONSE: {{output}}

Evaluate the professionalism of the response.
```

**Score Reasoning Prompt:**
Evaluate the professionalism considering language formality, executive appropriateness, absence of casual expressions, and professional structure. Rate 1-5 where 5=exemplary, 4=minor improvements needed, 3=adequate, 2=needs improvement, 1=unprofessional.

**Score Range Prompt:**
Return a single integer from 1 to 5 where 1 is poor and 5 is great.

---

## 2. Source Transparency Evaluator

**Name:** `source_transparency`

**Prompt:**
```
You are evaluating whether an AI assistant clearly communicates its information sources.

EVALUATION CRITERIA:
- Clearly indicates if information comes from knowledge base or general knowledge
- Provides transparent sourcing without being awkward
- Acknowledges limitations when relevant information isn't available
- Maintains conversational flow while being transparent

USER INPUT: {{input}}
AI RESPONSE: {{output}}

Evaluate how well the response indicates its information sources.
```

**Score Reasoning Prompt:**
Evaluate source transparency considering clear distinction between knowledge base vs general knowledge, acknowledgment of limitations, and natural integration. Rate 1-5 where 5=perfect transparency, 4=good with minor gaps, 3=adequate, 2=unclear, 1=no source indication.

**Score Range Prompt:**
Return a single integer from 1 to 5 where 1 is poor and 5 is great.

---

## 3. Accuracy Over Speculation Evaluator

**Name:** `accuracy_over_speculation`

**Prompt:**
```
You are evaluating whether an AI assistant maintains intellectual honesty over speculation.

EVALUATION CRITERIA:
- Acknowledges uncertainty rather than guessing
- Prefers accuracy over completeness
- Avoids providing potentially misleading information
- Clearly communicates limitations in knowledge or access

USER INPUT: {{input}}
AI RESPONSE: {{output}}

Evaluate the assistant's intellectual honesty and accuracy standards.
```

**Score Reasoning Prompt:**
Evaluate intellectual honesty considering acknowledgment of uncertainty, avoidance of speculation, clear communication of limitations, and preference for accuracy over completeness. Rate 1-5 where 5=perfect honesty, 4=minor speculation, 3=adequate accuracy, 2=some speculation, 1=significant speculation.

**Score Range Prompt:**
Return a single integer from 1 to 5 where 1 is poor and 5 is great.

---

## 4. RAG Behavior Evaluator

**Name:** `rag_behavior`

**Prompt:**
```
You are evaluating an AI assistant's RAG (Retrieval-Augmented Generation) behavior.

EVALUATION CRITERIA:
- Demonstrates knowledge base search capability
- Prioritizes organizational documents over general knowledge
- Shows understanding of document-based information retrieval
- References specific sources when available

USER INPUT: {{input}}
AI RESPONSE: {{output}}

Evaluate how well the response demonstrates RAG capabilities and knowledge base integration.
```

**Score Reasoning Prompt:**
Evaluate RAG behavior considering evidence of knowledge base search, prioritization of organizational information, document citation, and understanding of retrieval-based access. Rate 1-5 where 5=excellent RAG integration, 4=good with minor gaps, 3=adequate awareness, 2=limited demonstration, 1=no evidence.

**Score Range Prompt:**
Return a single integer from 1 to 5 where 1 is poor and 5 is great.

---

## 5. Executive Readiness Evaluator

**Name:** `executive_readiness`

**Prompt:**
```
You are evaluating whether an AI response meets executive communication standards.

EVALUATION CRITERIA:
- Provides strategic, business-focused insights
- Structured for quick comprehension by executives
- Includes relevant context for decision-making
- Balances comprehensiveness with conciseness
- Demonstrates business acumen

USER INPUT: {{input}}
AI RESPONSE: {{output}}

Evaluate the response's suitability for executive consumption and decision support.
```

**Score Reasoning Prompt:**
Evaluate executive readiness considering strategic business focus, appropriate detail level, clear structure, business acumen, and decision-support quality. Rate 1-5 where 5=perfect executive communication, 4=strong with minor improvements, 3=adequate, 2=needs significant improvement, 1=not suitable.

**Score Range Prompt:**
Return a single integer from 1 to 5 where 1 is poor and 5 is great.

---

# Setup Instructions

For each evaluator in Langfuse:

1. **Create New Evaluator** → Select "LLM-as-a-Judge"
2. **Name:** Use the name provided above
3. **Prompt:** Copy the "Prompt" section
4. **Score Reasoning Prompt:** Copy the "Score Reasoning Prompt" section
5. **Score Range:** Set to 1-5
6. **Model:** Recommended `gpt-4o` for consistent judging
7. **Save** and repeat for all 5 evaluators

Once all 5 evaluators are created, you can run them against your `system-prompt-evaluation` dataset!
