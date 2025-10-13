# Evals

LLM-as-a-judge evaluations for testing prompt quality and model accuracy.

## Running Evals

```bash
# From bot/ directory
PYTHONPATH=. venv/bin/python evals/eval_quality_judge.py
PYTHONPATH=. venv/bin/python evals/eval_source_selection.py
```

## Quality Judge Evals

Tests the quality control judge's accuracy at counting citations and matching them to sources.

**Current Results**: 6-7/8 passing (75-87.5%) - Test 8 reproduces production bug

### Test Cases

1. ✅ Perfect match - 5 citations, 5 sources
2. ✅ Perfect match - 21 citations, 21 sources
3. ✅ Missing sources - 10 citations, 5 sources
4. ✅ Missing sources - 18 citations, 10 sources
5. ✅ No sources section
6. ⚠️ Duplicate citations (flaky - sometimes passes)
7. ✅ **Out-of-order citations** (CRITICAL for production)
8. 🐛 **BUG REPRODUCTION - 25 citations with all 25 sources present** (Tests multi-line URL handling)

### Key Learnings

- GPT-4o performs significantly better than GPT-4o-mini (no hallucinations)
- Evidence requirement forces the judge to show its work, improving accuracy
- Out-of-order citations ([1], [5], [10]) are common in production reports
- Judge must understand: "If highest citation is [10], sources 1-10 must ALL exist"

## Source Selection Evals

Tests the LLM's ability to intelligently select the top N most relevant sources from a larger set.

**Exports**: `evals/results_source_selection.json` with structured results

### Test Cases

1. ✅ Mix of official and news sources - should prioritize official sites and SEC filings
2. ✅ Duplicate/redundant sources - should deduplicate and pick best coverage
3. ✅ Technical depth indicators - should prefer detailed content over brief articles
4. ✅ Authority hierarchy - should rank official > tier-1 news > tier-2 news > random
5. ✅ Diversity of source types - should balance variety (not all news)

### Selection Criteria

The LLM evaluates sources based on:
- **Authority**: Official sites, SEC filings, reputable news outlets
- **Diversity**: Mix of company site, news, financial data, reviews, analysis
- **Content depth**: Detailed descriptions indicate richer content
- **Recency vs authority**: Balance between fresh and authoritative
- **Deduplication**: Avoid redundant sources on same topic

### Metrics Tracked

- `count`: Number of sources selected
- `expected_overlap`: How many expected sources were included
- `expected_overlap_pct`: Percentage match with expected sources
- `diversity`: Breakdown by source type (official, news, financial, reviews)
- `reasoning_length`: Length of LLM's explanation

### Key Learnings

- GPT-4o-mini performs well at prioritizing authoritative sources
- LLM successfully deduplicates redundant coverage of same events
- Diversity requirement prevents overloading single source type
- Reasoning field helps debug unexpected selections

## MEDDPICC Clarification Evals

Tests the MEDDPICC agent's `check_input_completeness` logic for deciding when to PROCEED vs CLARIFY.

**Current Results**: 9-10/10 passing (90-100%)

### Test Cases

1. ✅ Comprehensive notes (Jane's Equipment) - All MEDDPICC elements present
2. ✅ Sample sales call (Acme Corp) - 5+ elements with medium coverage
3. ✅ Minimal notes (TechStartup) - Customer + pain point = sufficient
4. ✅ URL notes (DataCorp) - Customer + pain + budget mention
5. ✅ Comprehensive notes (GlobalTech) - All 8 MEDDPICC elements explicitly covered
6. ✅ Very vague ("bob wants software") - Correctly triggers CLARIFY
7. ✅ Minimal but contextual ("Jane's Equipment wants AI") - Correctly proceeds
8. ✅ Name + generic interest ("talked to susan") - Correctly triggers CLARIFY
9. ✅ Company + vague problem (Acme Corp) - Sufficient for analysis
10. ⚠️ Second turn follow-up (flaky - no conversation context in eval)

### Key Learnings

- LLM correctly identifies 2+ MEDDPICC elements as sufficient to proceed
- Structured call notes with pain points always proceed (as expected)
- Very brief vague input (< 50 chars, no context) correctly triggers clarification
- Customer name + specific pain point = minimum viable context
- Decision logic is permissive (defaults to PROCEED for borderline cases)

### Run Command

```bash
# From bot/ directory
PYTHONPATH=. venv/bin/python evals/eval_meddpicc_clarification.py
```

## Adding New Evals

1. Create eval script in `evals/`
2. Import production code from `agents/`, `services/`, etc.
3. Use descriptive test case names
4. Include expected vs actual in error messages
5. Return exit code 0 for pass, 1 for fail

```python
import sys
import asyncio

async def run_evals():
    # Your eval logic
    passed = test_something()
    return passed

if __name__ == "__main__":
    success = asyncio.run(run_evals())
    sys.exit(0 if success else 1)
```
