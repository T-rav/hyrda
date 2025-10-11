"""Evals for the NEW programmatic quality control system.

Tests the quality_control_node function with its programmatic validation.
"""

import asyncio
import logging
import sys

from dotenv import load_dotenv

# Load .env file
load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Import the actual quality control function
from agents.company_profile.nodes.quality_control import quality_control_node
from agents.company_profile.state import ProfileAgentState

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
    },
    {
        "name": "Missing sources - 10 citations, 5 sources",
        "report": """# Company Profile

## Overview
Citations [1] [2] [3] [4] [5] [6] [7] [8] [9] [10].

## Priorities
Strategic focus.

## News
Recent updates.

## Executive Team
Leadership team.

## Sources

1. https://example.com/1 - Source 1
2. https://example.com/2 - Source 2
3. https://example.com/3 - Source 3
4. https://example.com/4 - Source 4
5. https://example.com/5 - Source 5
""",
        "expected_pass": False,
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
    },
    {
        "name": "🐛 BUG FIX TEST - 25 citations with all 25 sources present (multi-line URLs)",
        "report": """# Company Profile: Tesla

## Overview
Tesla's AI initiatives [1] are revolutionizing autonomous driving [2] with significant investments [3] in chip development [4] and strategic partnerships [5].

## Priorities
The company's AI strategy [6] includes partnerships [7] with Samsung [8] for chip manufacturing [9]. Executive changes [10] have impacted the leadership team [11] according to recent reports [12]. The AI strategy [13] continues to evolve with restructuring [14] and new collaborations [15].

## News
Supply chain innovations [16] and partnerships [17] are critical, with significant deals [18] enhancing capabilities [19]. Tesla is working to electrify [20] its supply chain and leverage AI [21] for inventory management.

## Executive Team
The company's autonomous vehicle strategy [22] differs from competitors [23] while using cutting-edge technology [24] and ranking among top companies [25].

## Sources

1. https://www.folio3.ai/ai-pulse/tesla-releases-master-plan-part-4-ai-powered-sustainable-abundance/ - Article on Tesla's Master Plan Part 4 emphasizing AI and robotics.
2. https://digitaldefynd.com/IQ/tesla-using-ai-case-study/ - Case study on Tesla's use of AI in real-world driving and fleet intelligence.
3. https://www.ainvest.com/news/tesla-2025-digital-transformation-paving-future-autonomous-mobility-ai-driven-manufacturing-2509/ - Overview of Tesla's digital transformation focusing on AI-driven manufacturing.
4. https://carboncredits.com/teslas-ai5-chip-challenges-nvidias-dominance-in-ai-hardware-innovation/ - Discussion on Tesla's AI chip development and its impact on AI hardware innovation.
5. https://www.roic.ai/news/teslas-strategic-pivot-ai-and-energy-take-center-stage-as-ev-challenges-mount-07-31-2025 - Insight on Tesla's strategic shift towards AI and energy.
6. https://www.tesla.com/sites/default/files/downloads/TSLA-Q2-2025-Update.pdf - Tesla's Q2 2025 update on AI infrastructure expansion
7. https://www.ainvest.com/news/tesla-ai-pivot-vertical-integration-strategic-alliances-means-semiconductor-giants-2508/ - AInvest article on Tesla's partnership with Samsung
8. https://manufacturingdigital.com/news/tesla-secures-us-16-5bn-samsung-chip-manufacturing-deal - Manufacturing Digital report on Tesla and Samsung's chip deal
9. https://americanbazaaronline.com/2025/07/16/another-shakeup-at-tesla-as-top-sales-executive-exits-465144/ - American Bazaar article on Tesla's executive departure
10. https://www.businessinsider.com/tesla-org-chart-executives-elon-musk-2025-9 - Business Insider article on Tesla's executive structure
11. https://digitaldefynd.com/IQ/who-makes-up-the-csuite-team-of-tesla-meet-the-tesla-executive-team/ - Overview of Tesla's executive leadership team on DigitalDefynd
12. https://sustainabletechpartner.com/topics/ai/tesla-ai-strategy-elon-musk-on-fsd-optimus-robots-dojo-supercomputer/ - Article on Tesla's AI strategy and initiatives
13. https://www.usatoday.com/story/cars/news/2025/08/08/tesla-restructures-ai-chip-strategy/85573858007/ - USA Today article on Tesla's AI chip strategy restructuring
14. https://www.ainvest.com/news/tesla-ai-reckoning-vertical-integration-external-collaboration-rise-densityai-2508/ - Article on Tesla's AI strategy and partnerships with external companies like NVIDIA and Samsung.
15. https://www.gartner.com/en/supply-chain/insights/beyond-supply-chain-blog/tesla-21st-century-supply-chain - Gartner blog discussing Tesla's supply chain and AI partnerships.
16. https://farzadmesbahi.substack.com/p/teslas-supply-chain-power-play-securing - Analysis of Tesla's $16.5B deal with Samsung for AI chips.
17. https://www.allthingssupplychain.com/teslas-supply-chain-in-detail-innovation-challenges-and-lessons/ - Detailed look at Tesla's supply chain challenges and innovation.
18. https://www.teslarati.com/tesla-executive-electrify-supply-chain/ - News on Tesla's efforts to electrify its supply chain.
19. https://www.teslarati.com/ex-tesla-supply-chain-ai-inventory/ - Article on former Tesla supply chain managers starting an AI inventory firm.
20. https://www.klover.ai/tesla-ai-supremacy-analytical-report-ai-dominance/ - Analytical report on Tesla's AI strategies.
21. https://subscriber.politicopro.com/article/eenews/2025/07/31/tesla-signs-4-3b-battery-supply-pact-with-lg-energy-00485029 - Report on Tesla's $4.3B battery supply deal with LG Energy.
22. https://www.analyticsvidhya.com/blog/2025/07/tesla-ai-cars-and-manufacturing/ - Analytics Vidhya article on Tesla AI challenges
23. https://www.acvauctions.com/blog/best-self-driving-cars - Overview of Tesla's Autopilot and Full Self-Driving capabilities
24. https://www.thinkautonomous.ai/blog/tesla-vs-waymo-two-opposite-visions - Analysis of Tesla versus Waymo's approach to autonomous driving
25. https://evmagazine.com/top10/top-10-autonomous-vehicle-companies - EV Magazine's ranking of autonomous vehicle companies
""",
        "expected_pass": True,
    },
]


async def run_quality_control_test(report: str) -> tuple[bool, str]:
    """Run the actual quality_control_node function.

    Returns:
        (passes_quality, evidence_or_error)
    """
    # Create a minimal state
    state = ProfileAgentState(
        final_report=report,
        revision_count=0,
    )

    # Run the quality control node
    result = await quality_control_node(state, config={})

    # Check if it passed (goes to END) or failed (goes to revision)
    passes = result.goto == "__end__"

    # Extract evidence from logs (in production this would be in logger)
    return passes, f"goto={result.goto}"


async def run_evals():
    """Run all quality judge evals."""
    logger.info("=" * 80)
    logger.info("QUALITY CONTROL V2 EVALS (Programmatic Validation)")
    logger.info("=" * 80)

    total_tests = len(TEST_CASES)
    passed_tests = 0
    failed_tests = 0

    for i, test_case in enumerate(TEST_CASES, 1):
        logger.info(f"\n[Test {i}/{total_tests}] {test_case['name']}")
        logger.info("-" * 80)

        try:
            # Run quality control
            passes, evidence = await run_quality_control_test(test_case["report"])

            if passes == test_case["expected_pass"]:
                logger.info("✅ PASS - Quality control behaved correctly")
                logger.info(
                    f"   Expected pass={test_case['expected_pass']}, got pass={passes}"
                )
                logger.info(f"   {evidence}")
                passed_tests += 1
            else:
                logger.error("❌ FAIL - Quality control behaved incorrectly")
                logger.error(
                    f"   Expected pass={test_case['expected_pass']}, got pass={passes}"
                )
                logger.error(f"   {evidence}")
                failed_tests += 1

        except Exception as e:
            logger.error(f"❌ ERROR - Exception during test: {e}")
            import traceback

            traceback.print_exc()
            failed_tests += 1

    # Summary
    logger.info("\n" + "=" * 80)
    logger.info("SUMMARY")
    logger.info("=" * 80)
    logger.info(f"Total tests: {total_tests}")
    logger.info(f"Passed: {passed_tests} ({passed_tests / total_tests * 100:.1f}%)")
    logger.info(f"Failed: {failed_tests} ({failed_tests / total_tests * 100:.1f}%)")

    if failed_tests == 0:
        logger.info("\n🎉 ALL TESTS PASSED! Quality control is accurate.")
    else:
        logger.warning(f"\n⚠️  {failed_tests} test(s) failed.")

    return failed_tests == 0


if __name__ == "__main__":
    success = asyncio.run(run_evals())
    sys.exit(0 if success else 1)
