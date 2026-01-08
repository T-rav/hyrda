"""Evals for intelligent source selection.

Tests the LLM's ability to select the top N most relevant sources from a larger set.
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

# Test cases with different source scenarios
TEST_CASES = [
    {
        "name": "Mix of official and news sources (should prefer official)",
        "sources": [
            ("https://example.com/blog", "Random blog post"),
            ("https://sec.gov/edgar/10k", "SEC 10-K filing with financial data"),
            ("https://company.com/about", "Official company website about page"),
            ("https://techcrunch.com/article", "TechCrunch news article"),
            ("https://twitter.com/user/status", "Twitter post"),
        ],
        "max_sources": 3,
        "expected_top_3": [2, 3, 4],  # SEC filing, company site, reputable news
        "description": "Should prioritize SEC filing, official site, and reputable news over blog and Twitter",
    },
    {
        "name": "Duplicate/redundant sources (should deduplicate)",
        "sources": [
            ("https://reuters.com/tesla-earnings", "Reuters article on Tesla earnings"),
            (
                "https://bloomberg.com/tesla-earnings",
                "Bloomberg article on Tesla earnings (same topic)",
            ),
            ("https://tesla.com/investor", "Tesla investor relations page"),
            ("https://cnbc.com/tesla-earnings", "CNBC coverage of Tesla earnings"),
            ("https://sec.gov/tesla-10k", "Tesla SEC 10-K filing"),
        ],
        "max_sources": 3,
        "expected_top_3": [3, 5, 1],  # Official site, SEC filing, one news source
        "description": "Should prefer official site and SEC filing, then pick best news source (not all 3 redundant ones)",
    },
    {
        "name": "Technical depth indicators (should prefer detailed sources)",
        "sources": [
            ("https://company.com/whitepaper.pdf", "Detailed technical whitepaper"),
            ("https://medium.com/quick-intro", "Brief intro article"),
            (
                "https://docs.company.com/architecture",
                "Comprehensive architecture documentation",
            ),
            ("https://twitter.com/ceo", "CEO tweet"),
            (
                "https://youtube.com/interview",
                "YouTube interview with detailed product discussion",
            ),
        ],
        "max_sources": 3,
        "expected_top_3": [1, 3, 5],  # Whitepaper, docs, detailed interview
        "description": "Should prefer sources with detailed content over brief/surface-level ones",
    },
    {
        "name": "Authority hierarchy (official > reputable > random)",
        "sources": [
            ("https://randomsite.com/article", "Random website article"),
            ("https://forbes.com/analysis", "Forbes industry analysis"),
            ("https://company.com/press", "Official company press release"),
            ("https://blog.randomuser.com/opinion", "Personal blog opinion"),
            ("https://wsj.com/report", "Wall Street Journal investigative report"),
        ],
        "max_sources": 3,
        "expected_top_3": [3, 5, 2],  # Official site, WSJ, Forbes
        "description": "Should rank: official > tier-1 news (WSJ) > tier-2 news (Forbes) > random",
    },
    {
        "name": "Diversity of source types (should balance variety)",
        "sources": [
            ("https://company.com/about", "Official company website"),
            ("https://reuters.com/news1", "Reuters news article 1"),
            ("https://sec.gov/filing1", "SEC filing"),
            ("https://reuters.com/news2", "Reuters news article 2 (different topic)"),
            ("https://reuters.com/news3", "Reuters news article 3 (different topic)"),
            ("https://glassdoor.com/reviews", "Glassdoor employee reviews"),
            ("https://linkedin.com/company", "LinkedIn company page"),
        ],
        "max_sources": 5,
        "expected_diversity": {
            "official": 1,  # Should include official site
            "news": 1,  # Should include some news (not all 3 Reuters)
            "financial": 1,  # Should include SEC filing
            "reviews": 1,  # Should include employee perspective
        },
        "description": "Should balance different source types rather than overloading one type",
    },
]


async def run_source_selection(
    sources: list[tuple[str, str]], max_sources: int, api_key: str
) -> dict:
    """Run the intelligent source selection.

    Args:
        sources: List of (url, description) tuples
        max_sources: Maximum number of sources to select
        api_key: OpenAI API key

    Returns:
        Dict with selected_indices and reasoning

    """
    import re

    # Build source list text
    sources_text = "\n".join(
        [
            f"{i}. {url} - {desc}" if desc else f"{i}. {url}"
            for i, (url, desc) in enumerate(sources, 1)
        ]
    )

    selection_prompt = f"""You are selecting the top {max_sources} most relevant and important sources from a list of {len(sources)} sources for a company profile report.

**All Available Sources:**
{sources_text}

**Selection Criteria:**
- Prioritize authoritative sources (official company sites, SEC filings, reputable news)
- Include diverse source types (company site, news, financial data, industry analysis)
- Prefer sources with detailed descriptions (indicates rich content)
- Balance recency with authority
- Avoid duplicate or redundant sources

**Your Task:**
1. Select exactly {max_sources} sources
2. Return a JSON object with:
   - "selected": array of source numbers you selected (e.g., [1, 3, 5])
   - "reasoning": brief explanation of your selection strategy

Example response format:
```json
{{
  "selected": [2, 3, 5],
  "reasoning": "Selected SEC filing for authority, official site for primary info, and WSJ for third-party analysis. Avoided redundant news sources and low-authority blogs."
}}
```

Return ONLY the JSON object, no other text."""

    llm = ChatOpenAI(
        model="gpt-4o-mini",
        api_key=api_key,
        temperature=0.0,
        max_completion_tokens=300,
    )

    response = await llm.ainvoke(selection_prompt)
    response_text = response.content.strip()

    # Parse JSON response
    json_match = re.search(r"```json\s*(\{.*?\})\s*```", response_text, re.DOTALL)
    if json_match:
        result = json.loads(json_match.group(1))
    else:
        # Try to parse directly
        result = json.loads(response_text)

    return result


async def evaluate_selection(
    test_case: dict, selection_result: dict
) -> tuple[bool, list[str], dict]:
    """Evaluate if the source selection was good.

    Args:
        test_case: Test case with sources and expectations
        selection_result: Result from LLM selection

    Returns:
        (passed, errors, metrics) tuple

    """
    errors = []
    metrics = {}

    selected = selection_result.get("selected", [])
    reasoning = selection_result.get("reasoning", "")

    # Check count
    expected_count = test_case["max_sources"]
    if len(selected) != expected_count:
        errors.append(f"Expected {expected_count} sources, got {len(selected)}")

    metrics["count"] = len(selected)
    metrics["reasoning_length"] = len(reasoning)

    # Check if expected sources are included (if specified)
    if "expected_top_3" in test_case:
        expected = set(test_case["expected_top_3"])
        actual = set(selected)

        # Allow flexibility: as long as at least 2/3 match
        overlap = len(expected & actual)
        metrics["expected_overlap"] = overlap
        metrics["expected_overlap_pct"] = (overlap / len(expected)) * 100

        if overlap < len(expected) * 0.67:  # At least 67% overlap
            errors.append(
                f"Expected sources {expected}, got {actual}. Only {overlap}/{len(expected)} match"
            )

    # Check diversity (if specified)
    if "expected_diversity" in test_case:
        sources = test_case["sources"]
        selected_sources = [sources[i - 1] for i in selected]

        diversity_counts = {
            "official": sum(
                1
                for url, _ in selected_sources
                if "company.com" in url
                or "/about" in url
                or "/press" in url
                or "/investor" in url
            ),
            "news": sum(
                1
                for url, _ in selected_sources
                if any(
                    news in url
                    for news in [
                        "reuters",
                        "bloomberg",
                        "wsj",
                        "forbes",
                        "cnbc",
                        "techcrunch",
                    ]
                )
            ),
            "financial": sum(
                1
                for url, _ in selected_sources
                if "sec.gov" in url or "edgar" in url or "10-k" in url.lower()
            ),
            "reviews": sum(
                1
                for url, _ in selected_sources
                if "glassdoor" in url or "indeed" in url
            ),
        }

        metrics["diversity"] = diversity_counts

        expected_diversity = test_case["expected_diversity"]
        for source_type, expected_min in expected_diversity.items():
            actual_count = diversity_counts.get(source_type, 0)
            if actual_count < expected_min:
                errors.append(
                    f"Expected at least {expected_min} {source_type} source(s), got {actual_count}"
                )

    return len(errors) == 0, errors, metrics


async def run_evals():
    """Run all source selection evals."""
    api_key = os.getenv("LLM_API_KEY") or os.getenv("OPENAI_API_KEY")
    if not api_key:
        logger.error("❌ LLM_API_KEY or OPENAI_API_KEY environment variable not set")
        return False

    logger.info("=" * 80)
    logger.info("SOURCE SELECTION EVALS")
    logger.info("=" * 80)

    total_tests = len(TEST_CASES)
    passed_tests = 0
    failed_tests = 0
    all_results = []

    for i, test_case in enumerate(TEST_CASES, 1):
        logger.info(f"\n[Test {i}/{total_tests}] {test_case['name']}")
        logger.info("-" * 80)
        logger.info(f"Description: {test_case['description']}")
        logger.info(
            f"Sources: {len(test_case['sources'])}, Max: {test_case['max_sources']}"
        )

        try:
            # Run selection
            selection_result = await run_source_selection(
                test_case["sources"], test_case["max_sources"], api_key
            )

            # Evaluate
            passed, errors, metrics = await evaluate_selection(
                test_case, selection_result
            )

            result = {
                "test_name": test_case["name"],
                "passed": passed,
                "selected": selection_result.get("selected", []),
                "reasoning": selection_result.get("reasoning", ""),
                "metrics": metrics,
                "errors": errors,
            }
            all_results.append(result)

            if passed:
                logger.info("✅ PASS")
                logger.info(f"   Selected: {selection_result.get('selected')}")
                logger.info(f"   Reasoning: {selection_result.get('reasoning')}")
                logger.info(f"   Metrics: {json.dumps(metrics, indent=2)}")
                passed_tests += 1
            else:
                logger.error("❌ FAIL")
                for error in errors:
                    logger.error(f"   - {error}")
                logger.error(f"   Selected: {selection_result.get('selected')}")
                logger.error(f"   Reasoning: {selection_result.get('reasoning')}")
                logger.error(f"   Metrics: {json.dumps(metrics, indent=2)}")
                failed_tests += 1

        except Exception as e:
            logger.error(f"❌ ERROR - Exception during test: {e}")
            all_results.append(
                {
                    "test_name": test_case["name"],
                    "passed": False,
                    "error": str(e),
                }
            )
            failed_tests += 1

    # Summary
    logger.info("\n" + "=" * 80)
    logger.info("SUMMARY")
    logger.info("=" * 80)
    logger.info(f"Total tests: {total_tests}")
    logger.info(f"Passed: {passed_tests} ({passed_tests / total_tests * 100:.1f}%)")
    logger.info(f"Failed: {failed_tests} ({failed_tests / total_tests * 100:.1f}%)")

    # Export results as JSON
    results_file = "evals/results_source_selection.json"
    with open(results_file, "w") as f:
        json.dump(
            {
                "total": total_tests,
                "passed": passed_tests,
                "failed": failed_tests,
                "results": all_results,
            },
            f,
            indent=2,
        )
    logger.info(f"\n📊 Results exported to: {results_file}")

    if failed_tests == 0:
        logger.info("\n🎉 ALL TESTS PASSED! Source selection is working well.")
    else:
        logger.warning(
            f"\n⚠️  {failed_tests} test(s) failed. Review selection criteria."
        )

    return failed_tests == 0


if __name__ == "__main__":
    success = asyncio.run(run_evals())
    sys.exit(0 if success else 1)
