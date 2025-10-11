# Evals

LLM-as-a-judge evaluations for testing prompt quality and model accuracy.

## Running Evals

```bash
# From bot/ directory
PYTHONPATH=. venv/bin/python evals/eval_quality_judge.py
```

## Quality Judge Evals

Tests the quality control judge's accuracy at counting citations and matching them to sources.

**Current Results**: 5-6/7 passing (71-85%)

### Test Cases

1. ✅ Perfect match - 5 citations, 5 sources
2. ✅ Perfect match - 21 citations, 21 sources
3. ✅ Missing sources - 10 citations, 5 sources
4. ✅ Missing sources - 18 citations, 10 sources
5. ✅ No sources section
6. ⚠️ Duplicate citations (flaky - sometimes passes)
7. ✅ **Out-of-order citations** (CRITICAL for production)

### Key Learnings

- GPT-4o performs significantly better than GPT-4o-mini (no hallucinations)
- Evidence requirement forces the judge to show its work, improving accuracy
- Out-of-order citations ([1], [5], [10]) are common in production reports
- Judge must understand: "If highest citation is [10], sources 1-10 must ALL exist"

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
