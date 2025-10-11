# Evals

LLM-as-a-judge evaluations for testing prompt quality and model accuracy.

## Running Evals

```bash
# From bot/ directory
PYTHONPATH=. venv/bin/python evals/eval_quality_judge.py
```

## Citation Validation Evals

Comprehensive test suite for the citation validation system, including helper functions and quality judge.

### Running Citation Validation Evals

```bash
# From bot/ directory
PYTHONPATH=. venv/bin/python evals/eval_citation_validation.py
```

**Current Results**: Testing in progress

### Test Suites

#### 1. Citation Extraction Tests
Tests the `extract_citations_from_report()` helper function:
- ✅ Sequential and sparse citations
- ✅ Out of order citations (should sort)
- ✅ Duplicate citations (should dedupe)
- ✅ No citations
- ✅ Text with numbers (only actual citations)

#### 2. Source Counting Tests
Tests the `count_sources_in_section()` helper function:
- ✅ Various source counts (3, 10, 36, 52)
- ✅ No sources section
- ✅ Sources section with no numbered entries

#### 3. Quality Judge Tests
Tests the LLM-as-a-judge quality control:
1. ✅ Perfect match - 10 citations, 10 sources
2. ✅ Perfect match - 25 citations, 25 sources
3. ❌ **Production bug case** - 52 citations, only 36 sources (CRITICAL)
4. ❌ Missing sources - 18 citations, 10 sources
5. ❌ Large gap - 30 citations, 15 sources
6. ❌ No sources section at all
7. ✅ Sparse citations [1], [5], [10], [15], [20] - all 20 sources present
8. ❌ Sparse citations [1], [5], [10], [15], [20] - only 10 sources
9. ✅ Edge case - 1 citation, 1 source
10. ❌ Off by one - 50 citations, 49 sources

### Key Learnings

- GPT-4o performs better than GPT-4o-mini (no hallucinations)
- Evidence requirement forces the judge to show its work
- Out-of-order citations are common in production
- Judge must understand: "If highest citation is [X], sources 1-X must ALL exist"
- Production bug: Reports with 52 citations but only 36 sources listed
- Allow ±1 tolerance for LLM counting to avoid false negatives

## Quality Judge Evals (Legacy)

Original quality judge eval suite (still maintained for backward compatibility).

```bash
# From bot/ directory
PYTHONPATH=. venv/bin/python evals/eval_quality_judge.py
```

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
