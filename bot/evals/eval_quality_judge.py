"""Evals for quality control LLM judge.

Tests various scenarios to ensure the judge accurately counts citations and sources.
"""

import asyncio
import json
import logging
import os
import sys

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

# Load .env file
load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Import the actual quality judge prompt
from agents.company_profile.nodes.quality_control import QUALITY_JUDGE_PROMPT

# Test cases covering various scenarios
TEST_CASES = [
    {
        "name": "Perfect match - 5 citations, 5 sources",
        "report": """# Company Profile

## Overview
This company [1] was founded [2] in 2020 [3] and has grown [4] significantly [5].

## Priorities
Strategic priorities.

## News
Recent news.

## Executive Team
Leadership team.

## Sources

1. https://example.com/source1 - Source 1
2. https://example.com/source2 - Source 2
3. https://example.com/source3 - Source 3
4. https://example.com/source4 - Source 4
5. https://example.com/source5 - Source 5
""",
        "expected_pass": True,
        "expected_highest": 5,
        "expected_count": 5,
        "expected_missing": [],
    },
    {
        "name": "Perfect match - 21 citations, 21 sources",
        "report": """# Company Profile

Citation [1] [2] [3] [4] [5] [6] [7] [8] [9] [10] [11] [12] [13] [14] [15] [16] [17] [18] [19] [20] [21].

## Sources

1. https://example.com/1 - Source 1
2. https://example.com/2 - Source 2
3. https://example.com/3 - Source 3
4. https://example.com/4 - Source 4
5. https://example.com/5 - Source 5
6. https://example.com/6 - Source 6
7. https://example.com/7 - Source 7
8. https://example.com/8 - Source 8
9. https://example.com/9 - Source 9
10. https://example.com/10 - Source 10
11. https://example.com/11 - Source 11
12. https://example.com/12 - Source 12
13. https://example.com/13 - Source 13
14. https://example.com/14 - Source 14
15. https://example.com/15 - Source 15
16. https://example.com/16 - Source 16
17. https://example.com/17 - Source 17
18. https://example.com/18 - Source 18
19. https://example.com/19 - Source 19
20. https://example.com/20 - Source 20
21. https://example.com/21 - Source 21
""",
        "expected_pass": True,
        "expected_highest": 21,
        "expected_count": 21,
        "expected_missing": [],
    },
    {
        "name": "Missing sources - 10 citations, 5 sources",
        "report": """# Company Profile

Citations [1] [2] [3] [4] [5] [6] [7] [8] [9] [10].

## Sources

1. https://example.com/1 - Source 1
2. https://example.com/2 - Source 2
3. https://example.com/3 - Source 3
4. https://example.com/4 - Source 4
5. https://example.com/5 - Source 5
""",
        "expected_pass": False,
        "expected_highest": 10,
        "expected_count": 5,
        "expected_missing": [6, 7, 8, 9, 10],
    },
    {
        "name": "Missing sources - 18 citations, 10 sources (like the hallucination case)",
        "report": """# Company Profile

Citations [1] [2] [3] [4] [5] [6] [7] [8] [9] [10] [11] [12] [13] [14] [15] [16] [17] [18].

## Sources

1. https://example.com/1 - Source 1
2. https://example.com/2 - Source 2
3. https://example.com/3 - Source 3
4. https://example.com/4 - Source 4
5. https://example.com/5 - Source 5
6. https://example.com/6 - Source 6
7. https://example.com/7 - Source 7
8. https://example.com/8 - Source 8
9. https://example.com/9 - Source 9
10. https://example.com/10 - Source 10
""",
        "expected_pass": False,
        "expected_highest": 18,
        "expected_count": 10,
        "expected_missing": [11, 12, 13, 14, 15, 16, 17, 18],
    },
    {
        "name": "No sources section",
        "report": """# Company Profile

This company [1] was founded [2] in 2020 [3].

## Conclusion

No sources provided.
""",
        "expected_pass": False,
        "expected_highest": 3,
        "expected_count": 0,
        "expected_missing": [1, 2, 3],
    },
    {
        "name": "Duplicate citations (should still count highest)",
        "report": """# Company Profile

## Overview
The company [1] was founded [1] in [2] the year [2] 2020 [3].

## Priorities
Strategic focus.

## News
Recent updates.

## Executive Team
Leadership.

## Sources

1. https://example.com/1 - Source 1
2. https://example.com/2 - Source 2
3. https://example.com/3 - Source 3
""",
        "expected_pass": True,
        "expected_highest": 3,
        "expected_count": 3,
        "expected_missing": [],
    },
    {
        "name": "Non-sequential citations (1, 5, 10 - but all 10 sources present)",
        "report": """# Company Profile

## Overview
The company [1] was founded in [5] the year [10].

## Priorities
Strategic focus areas here.

## News
Recent developments.

## Executive Team
Leadership information.

## Sources

1. https://example.com/1 - Source 1
2. https://example.com/2 - Source 2
3. https://example.com/3 - Source 3
4. https://example.com/4 - Source 4
5. https://example.com/5 - Source 5
6. https://example.com/6 - Source 6
7. https://example.com/7 - Source 7
8. https://example.com/8 - Source 8
9. https://example.com/9 - Source 9
10. https://example.com/10 - Source 10
""",
        "expected_pass": True,
        "expected_highest": 10,
        "expected_count": 10,
        "expected_missing": [],
    },
]


async def run_quality_judge(report: str, api_key: str) -> dict:
    """Run the quality judge on a test report."""
    judge_llm = ChatOpenAI(
        model="gpt-4o",
        api_key=api_key,
        temperature=0.0,
        max_completion_tokens=500,
    )

    prompt = QUALITY_JUDGE_PROMPT.format(report=report)
    response = await judge_llm.ainvoke(prompt)
    response_text = response.content.strip()

    # Parse JSON
    import re

    json_match = re.search(r"```json\s*(\{.*?\})\s*```", response_text, re.DOTALL)
    if json_match:
        json_text = json_match.group(1)
    else:
        json_match = re.search(r"\{.*\}", response_text, re.DOTALL)
        json_text = json_match.group(0) if json_match else response_text

    return json.loads(json_text)


async def evaluate_judge_accuracy(
    test_case: dict, judge_result: dict
) -> tuple[bool, list[str]]:
    """Evaluate if the judge's assessment was correct.

    Returns:
        (passed, errors) - True if judge was accurate, list of error messages
    """
    errors = []

    # Check pass/fail accuracy
    if judge_result.get("passes_quality") != test_case["expected_pass"]:
        errors.append(
            f"Expected passes_quality={test_case['expected_pass']}, "
            f"got {judge_result.get('passes_quality')}"
        )

    # Check highest citation accuracy
    actual_highest = judge_result.get("highest_citation", 0)
    if actual_highest != test_case["expected_highest"]:
        errors.append(
            f"Expected highest_citation={test_case['expected_highest']}, "
            f"got {actual_highest}"
        )

    # Check sources count accuracy
    actual_count = judge_result.get("sources_count", 0)
    if actual_count != test_case["expected_count"]:
        errors.append(
            f"Expected sources_count={test_case['expected_count']}, got {actual_count}"
        )

    # Check missing sources accuracy
    actual_missing = judge_result.get("missing_sources", [])
    if actual_missing != test_case["expected_missing"]:
        errors.append(
            f"Expected missing_sources={test_case['expected_missing']}, "
            f"got {actual_missing}"
        )

    # Check that evidence was provided when failing
    if not judge_result.get("passes_quality"):
        evidence = judge_result.get("evidence", "")
        if not evidence or evidence == "No evidence provided":
            errors.append("Judge failed report but provided no evidence")

    return len(errors) == 0, errors


async def run_evals():
    """Run all quality judge evals."""
    api_key = os.getenv("LLM_API_KEY") or os.getenv("OPENAI_API_KEY")
    if not api_key:
        logger.error("❌ LLM_API_KEY or OPENAI_API_KEY environment variable not set")
        return False

    logger.info("=" * 80)
    logger.info("QUALITY JUDGE EVALS")
    logger.info("=" * 80)

    total_tests = len(TEST_CASES)
    passed_tests = 0
    failed_tests = 0

    for i, test_case in enumerate(TEST_CASES, 1):
        logger.info(f"\n[Test {i}/{total_tests}] {test_case['name']}")
        logger.info("-" * 80)

        try:
            # Run judge
            judge_result = await run_quality_judge(test_case["report"], api_key)

            # Evaluate accuracy
            passed, errors = await evaluate_judge_accuracy(test_case, judge_result)

            if passed:
                logger.info("✅ PASS - Judge was accurate")
                logger.info(
                    f"   Judge result: passes={judge_result.get('passes_quality')}, "
                    f"highest={judge_result.get('highest_citation')}, "
                    f"count={judge_result.get('sources_count')}"
                )
                evidence = judge_result.get("evidence", "")
                if evidence:
                    logger.info(f"   Evidence: {evidence[:200]}...")
                passed_tests += 1
            else:
                logger.error("❌ FAIL - Judge was inaccurate")
                for error in errors:
                    logger.error(f"   - {error}")
                logger.error(
                    f"   Full judge result: {json.dumps(judge_result, indent=2)}"
                )
                failed_tests += 1

        except Exception as e:
            logger.error(f"❌ ERROR - Exception during test: {e}")
            failed_tests += 1

    # Summary
    logger.info("\n" + "=" * 80)
    logger.info("SUMMARY")
    logger.info("=" * 80)
    logger.info(f"Total tests: {total_tests}")
    logger.info(f"Passed: {passed_tests} ({passed_tests / total_tests * 100:.1f}%)")
    logger.info(f"Failed: {failed_tests} ({failed_tests / total_tests * 100:.1f}%)")

    if failed_tests == 0:
        logger.info("\n🎉 ALL TESTS PASSED! Quality judge is accurate.")
    else:
        logger.warning(f"\n⚠️  {failed_tests} test(s) failed. Judge needs improvement.")

    return failed_tests == 0


if __name__ == "__main__":
    success = asyncio.run(run_evals())
    sys.exit(0 if success else 1)
