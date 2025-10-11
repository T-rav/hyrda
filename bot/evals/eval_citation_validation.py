"""Comprehensive eval for citation validation system.

Tests citation extraction, source counting, and quality judge accuracy
for detecting missing sources - including the production bug case.
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

# Import production code
from agents.company_profile.nodes.quality_control import (
    QUALITY_JUDGE_PROMPT,
    count_sources_in_section,
    extract_citations_from_report,
)


def generate_test_report(
    max_citation: int,
    num_sources: int,
    include_sources_section: bool = True,
    sparse_citations: bool = False,
) -> str:
    """Generate a test report with specified citations and sources.

    Args:
        max_citation: Highest citation number to use
        num_sources: Number of sources to list in Sources section
        include_sources_section: Whether to include ## Sources section
        sparse_citations: If True, use sparse citations like [1], [5], [10] instead of sequential

    Returns:
        Generated test report
    """
    # Generate citations in report body
    if sparse_citations and max_citation >= 10:
        # Use sparse citations (e.g., [1], [5], [10], [15], [20])
        citations_to_use = [1, 5, 10, 15, 20, max_citation]
        citations_to_use = [c for c in citations_to_use if c <= max_citation]
        citations_str = " ".join([f"[{c}]" for c in citations_to_use])
    else:
        # Use sequential citations
        citations_str = " ".join([f"[{i}]" for i in range(1, max_citation + 1)])

    report = f"""## Company Overview
This is a test company profile with citations {citations_str}.

## Company Priorities for Current/Next Year
The company has strategic priorities with more citations spread throughout.

## Recent News Stories (Past 12 Months)
Recent developments include various announcements and updates.

## Executive Team
The executive team consists of experienced leaders.

## Relationships via 8th Light Network
No known relationships identified.

## Industry Competitors
Main competitors include several companies in the space.

## Boutique Consulting Partners
Various consulting firms work in this space.

## Size of Product, Design, and Technology Teams
The technology team is approximately 500 engineers.

## Solutions 8th Light Can Offer
Based on the findings, 8th Light can provide consulting services.
"""

    if include_sources_section:
        report += "\n## Sources\n\n"
        for i in range(1, num_sources + 1):
            report += f"{i}. https://example.com/source{i} - Source {i} description\n"

    return report


# Comprehensive test cases
TEST_CASES = [
    {
        "name": "✅ Perfect match - 10 citations, 10 sources",
        "report": generate_test_report(10, 10),
        "expected_pass": True,
        "expected_highest": 10,
        "expected_count": 10,
        "expected_missing": [],
    },
    {
        "name": "✅ Perfect match - 25 citations, 25 sources",
        "report": generate_test_report(25, 25),
        "expected_pass": True,
        "expected_highest": 25,
        "expected_count": 25,
        "expected_missing": [],
    },
    {
        "name": "❌ Production bug case - 52 citations, only 36 sources",
        "report": generate_test_report(52, 36),
        "expected_pass": False,
        "expected_highest": 52,
        "expected_count": 36,
        "expected_missing": list(range(37, 53)),  # [37, 38, ..., 52]
    },
    {
        "name": "❌ Missing sources - 18 citations, 10 sources",
        "report": generate_test_report(18, 10),
        "expected_pass": False,
        "expected_highest": 18,
        "expected_count": 10,
        "expected_missing": [11, 12, 13, 14, 15, 16, 17, 18],
    },
    {
        "name": "❌ Large gap - 30 citations, 15 sources",
        "report": generate_test_report(30, 15),
        "expected_pass": False,
        "expected_highest": 30,
        "expected_count": 15,
        "expected_missing": list(range(16, 31)),
    },
    {
        "name": "❌ No sources section at all",
        "report": generate_test_report(20, 0, include_sources_section=False),
        "expected_pass": False,
        "expected_highest": 20,
        "expected_count": 0,
        "expected_missing": list(range(1, 21)),
    },
    {
        "name": "✅ Sparse citations [1], [5], [10], [15], [20] - all 20 sources present",
        "report": generate_test_report(20, 20, sparse_citations=True),
        "expected_pass": True,
        "expected_highest": 20,
        "expected_count": 20,
        "expected_missing": [],
    },
    {
        "name": "❌ Sparse citations [1], [5], [10], [15], [20] - only 10 sources",
        "report": generate_test_report(20, 10, sparse_citations=True),
        "expected_pass": False,
        "expected_highest": 20,
        "expected_count": 10,
        "expected_missing": [11, 12, 13, 14, 15, 16, 17, 18, 19, 20],
    },
    {
        "name": "✅ Edge case - 1 citation, 1 source",
        "report": generate_test_report(1, 1),
        "expected_pass": True,
        "expected_highest": 1,
        "expected_count": 1,
        "expected_missing": [],
    },
    {
        "name": "❌ Off by one - 50 citations, 49 sources",
        "report": generate_test_report(50, 49),
        "expected_pass": False,
        "expected_highest": 50,
        "expected_count": 49,
        "expected_missing": [50],
    },
]


async def test_citation_extraction():
    """Test the citation extraction helper function."""
    logger.info("\n" + "=" * 80)
    logger.info("TESTING CITATION EXTRACTION")
    logger.info("=" * 80)

    test_cases = [
        {
            "report": "Test [1] [2] [3] [10] [25]",
            "expected": [1, 2, 3, 10, 25],
            "name": "Sequential and sparse citations",
        },
        {
            "report": "Test [5] [1] [3] [2] [4]",
            "expected": [1, 2, 3, 4, 5],
            "name": "Out of order citations (should sort)",
        },
        {
            "report": "Test [1] [1] [2] [2] [3]",
            "expected": [1, 2, 3],
            "name": "Duplicate citations (should dedupe)",
        },
        {
            "report": "No citations here",
            "expected": [],
            "name": "No citations",
        },
        {
            "report": "Test [1] through [52]",
            "expected": [1, 52],
            "name": "Text with numbers (only actual citations)",
        },
    ]

    passed = 0
    failed = 0

    for test in test_cases:
        result = extract_citations_from_report(test["report"])
        if result == test["expected"]:
            logger.info(f"✅ PASS - {test['name']}")
            logger.info(f"   Expected: {test['expected']}, Got: {result}")
            passed += 1
        else:
            logger.error(f"❌ FAIL - {test['name']}")
            logger.error(f"   Expected: {test['expected']}")
            logger.error(f"   Got: {result}")
            failed += 1

    logger.info(f"\nCitation extraction: {passed}/{len(test_cases)} passed")
    return failed == 0


async def test_source_counting():
    """Test the source counting helper function."""
    logger.info("\n" + "=" * 80)
    logger.info("TESTING SOURCE COUNTING")
    logger.info("=" * 80)

    test_cases = [
        {
            "report": """## Sources

1. https://example.com/1 - Source 1
2. https://example.com/2 - Source 2
3. https://example.com/3 - Source 3
""",
            "expected": 3,
            "name": "3 sources",
        },
        {
            "report": generate_test_report(10, 10),
            "expected": 10,
            "name": "10 sources",
        },
        {
            "report": generate_test_report(52, 36),
            "expected": 36,
            "name": "36 sources (production bug case)",
        },
        {
            "report": "No sources section",
            "expected": 0,
            "name": "No sources section",
        },
        {
            "report": """## Sources

No numbered entries here, just text.
""",
            "expected": 0,
            "name": "Sources section with no numbered entries",
        },
    ]

    passed = 0
    failed = 0

    for test in test_cases:
        result = count_sources_in_section(test["report"])
        if result == test["expected"]:
            logger.info(f"✅ PASS - {test['name']}")
            logger.info(f"   Expected: {test['expected']}, Got: {result}")
            passed += 1
        else:
            logger.error(f"❌ FAIL - {test['name']}")
            logger.error(f"   Expected: {test['expected']}")
            logger.error(f"   Got: {result}")
            failed += 1

    logger.info(f"\nSource counting: {passed}/{len(test_cases)} passed")
    return failed == 0


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

    # Check highest citation accuracy (allow ±1 tolerance for LLM counting)
    actual_highest = judge_result.get("highest_citation", 0)
    expected_highest = test_case["expected_highest"]
    if abs(actual_highest - expected_highest) > 1:
        errors.append(
            f"Expected highest_citation={expected_highest}, "
            f"got {actual_highest} (off by more than 1)"
        )

    # Check sources count accuracy (allow ±1 tolerance)
    actual_count = judge_result.get("sources_count", 0)
    expected_count = test_case["expected_count"]
    if abs(actual_count - expected_count) > 1:
        errors.append(
            f"Expected sources_count={expected_count}, "
            f"got {actual_count} (off by more than 1)"
        )

    # Check missing sources (should identify the gap correctly)
    actual_missing = judge_result.get("missing_sources", [])
    expected_missing = test_case["expected_missing"]

    # For missing sources, we care that it correctly identifies there ARE missing sources
    # The exact list might vary slightly, so we check:
    # 1. If we expect missing sources, judge should report some
    # 2. If we expect no missing sources, judge should report none
    if expected_missing and not actual_missing:
        errors.append(
            f"Expected missing sources {expected_missing[:5]}..., but got none"
        )
    elif not expected_missing and actual_missing:
        errors.append(f"Expected no missing sources, but got {actual_missing[:5]}...")

    # Check that evidence was provided when failing
    if not judge_result.get("passes_quality"):
        evidence = judge_result.get("evidence", "")
        if not evidence or evidence == "No evidence provided":
            errors.append("Judge failed report but provided no evidence")

    return len(errors) == 0, errors


async def test_quality_judge():
    """Test the quality judge with comprehensive test cases."""
    api_key = os.getenv("LLM_API_KEY") or os.getenv("OPENAI_API_KEY")
    if not api_key:
        logger.error("❌ LLM_API_KEY or OPENAI_API_KEY environment variable not set")
        return False

    logger.info("\n" + "=" * 80)
    logger.info("TESTING QUALITY JUDGE")
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
                    f"count={judge_result.get('sources_count')}, "
                    f"missing={len(judge_result.get('missing_sources', []))} sources"
                )
                evidence = judge_result.get("evidence", "")
                if evidence:
                    logger.info(f"   Evidence: {evidence[:150]}...")
                passed_tests += 1
            else:
                logger.error("❌ FAIL - Judge was inaccurate")
                for error in errors:
                    logger.error(f"   - {error}")
                logger.error(f"   Judge result: {json.dumps(judge_result, indent=2)}")
                failed_tests += 1

        except Exception as e:
            logger.error(f"❌ ERROR - Exception during test: {e}")
            import traceback

            logger.error(traceback.format_exc())
            failed_tests += 1

    # Summary
    logger.info("\n" + "=" * 80)
    logger.info("QUALITY JUDGE SUMMARY")
    logger.info("=" * 80)
    logger.info(f"Total tests: {total_tests}")
    logger.info(f"Passed: {passed_tests} ({passed_tests / total_tests * 100:.1f}%)")
    logger.info(f"Failed: {failed_tests} ({failed_tests / total_tests * 100:.1f}%)")

    return failed_tests == 0


async def run_all_evals():
    """Run all citation validation evals."""
    logger.info("\n" + "=" * 80)
    logger.info("CITATION VALIDATION COMPREHENSIVE EVAL SUITE")
    logger.info("=" * 80)

    results = []

    # Test helper functions
    results.append(("Citation Extraction", await test_citation_extraction()))
    results.append(("Source Counting", await test_source_counting()))

    # Test quality judge
    results.append(("Quality Judge", await test_quality_judge()))

    # Overall summary
    logger.info("\n" + "=" * 80)
    logger.info("OVERALL RESULTS")
    logger.info("=" * 80)

    all_passed = True
    for test_name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        logger.info(f"{status} - {test_name}")
        if not passed:
            all_passed = False

    if all_passed:
        logger.info(
            "\n🎉 ALL EVALS PASSED! Citation validation system is working correctly."
        )
    else:
        logger.warning("\n⚠️  Some evals failed. Review the output above for details.")

    return all_passed


if __name__ == "__main__":
    success = asyncio.run(run_all_evals())
    sys.exit(0 if success else 1)
