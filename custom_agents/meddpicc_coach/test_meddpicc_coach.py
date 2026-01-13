"""Test script for MEDDPICC coach agent.

Run this to verify the MEDDPICC coach workflow is working correctly.
"""

import asyncio
import logging
import sys
from pathlib import Path

# Load environment variables
from dotenv import load_dotenv

# Load .env from project root
project_root = Path(__file__).parent.parent.parent.parent
load_dotenv(project_root / ".env")

# Add bot directory to path
bot_dir = Path(__file__).parent.parent.parent
sys.path.insert(0, str(bot_dir))

from agents.meddic_agent import MeddicAgent

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


# Sample sales call notes for testing
SAMPLE_NOTES = """
Call with Sarah Johnson from Acme Corp today. Really good conversation!

They're struggling with deployment speed - currently takes 2 weeks to push updates.
This is causing them to miss market opportunities. Sarah mentioned the CTO (Mark Chen)
is really frustrated about this. They have about 50 engineers on the team.

Budget-wise, she said they have $200K allocated for DevOps improvements this quarter.
They need to see ROI within 6 months.

They're also looking at our competitor XYZ Solutions. Sounds like XYZ is cheaper but
Sarah's concerned about their support quality. She seems really enthusiastic about
our solution and mentioned she'll be championing it internally.

Timeline is end of Q2 - they want something in place before the summer product launch.
Sarah will need to present to the executive team next month. Not sure about the
full approval process yet.
"""

MINIMAL_NOTES = """
Quick call with John at TechStartup. They have scaling issues.
Looking at solutions. John likes our approach.
"""

URL_NOTES = """
Had a great call with Mike from DataCorp. Check out their company info:
https://en.wikipedia.org/wiki/Data_management

They're looking to improve their data pipeline. Budget discussion coming next week.
"""

COMPREHENSIVE_NOTES = """
Fantastic call with Jennifer Martinez, VP of Engineering at GlobalTech Solutions.

PAIN POINTS:
- Their legacy monolith is killing velocity - 3 week release cycles
- Customer complaints about bugs in production are up 40% YoY
- Engineering team morale is low, lots of turnover (lost 5 senior engineers last quarter)
- Cloud costs are out of control - spending $500K/month on AWS

METRICS:
- Want to reduce release cycle to 2 days
- Reduce production incidents by 50%
- Improve engineer retention (currently 15% annual turnover)
- Cut cloud costs by 30%

ECONOMIC BUYER:
- CTO David Park has final say on vendor decisions over $100K
- Jennifer reports to David and has strong influence
- David is presenting to board next month about tech modernization initiative

DECISION CRITERIA:
- Must integrate with their existing AWS infrastructure
- Need proven case studies in fintech (they're heavily regulated)
- Want hands-on training, not just consulting
- Security and compliance are critical (SOC2, PCI-DSS)

DECISION PROCESS:
- Jennifer evaluates and recommends (week 1-2)
- Technical review with architecture team (week 3)
- CTO David approves budget (week 4)
- Legal and procurement review contract (week 5-6)
- Board notification for deals over $250K

PAPER PROCESS:
- Standard vendor onboarding takes 2-3 weeks
- Need insurance certificates and security questionnaire
- Preferred vendor status requires background checks
- Legal will want to negotiate SLA terms

CHAMPION:
- Jennifer is 100% on board - she used our solution at her previous company
- She's already talking to David about us
- She mentioned she'll pull in Mike (Director of DevOps) as an ally

COMPETITION:
- Looking at Cloudify and DevOps Pro Solutions
- Cloudify is cheaper but Jennifer doubts their fintech experience
- DevOps Pro has good references but poor project management reputation
- We have the strongest security compliance story

TIMELINE:
- Want to start pilot in 6 weeks
- Full rollout by Q3
- Budget refresh is in September, so need to decide before then

NEXT STEPS:
- Send case studies (fintech focus) by Friday
- Schedule technical deep-dive with architecture team for next week
- Jennifer will set up intro call with David (CTO) in 2 weeks
"""


async def test_agent(notes: str, test_name: str):
    """Test the MEDDPICC agent with sample notes.

    Args:
        notes: Sales call notes to analyze
        test_name: Name of the test for logging

    """
    print(f"\n{'=' * 80}")
    print(f"TEST: {test_name}")
    print(f"{'=' * 80}\n")

    # Create agent
    agent = MeddicAgent()

    # Prepare mock context
    context = {
        "user_id": "U12345",
        "channel": "C12345",
        "slack_service": None,  # Not needed for basic test
    }

    # Run agent
    logger.info(f"Running {test_name}...")
    result = await agent.run(notes, context)

    # Display results
    print("\n📊 RESULT:")
    print("-" * 80)
    print(result["response"])
    print("-" * 80)

    # Display metadata
    print("\n📈 METADATA:")
    for key, value in result.get("metadata", {}).items():
        print(f"  {key}: {value}")

    return result


async def main():
    """Run all tests."""
    print("\n🚀 MEDDPICC Coach Agent Test Suite")
    print("=" * 80)

    try:
        # Test 1: Sample notes (good coverage)
        await test_agent(SAMPLE_NOTES, "Sample Sales Call (Medium Coverage)")

        # Test 2: Minimal notes (lots of gaps)
        await test_agent(MINIMAL_NOTES, "Minimal Notes (Many Gaps)")

        # Test 3: URL scraping (new feature)
        await test_agent(URL_NOTES, "URL Scraping Test")

        # Test 4: Comprehensive notes (excellent coverage)
        await test_agent(COMPREHENSIVE_NOTES, "Comprehensive Notes (Full Coverage)")

        print("\n" + "=" * 80)
        print("✅ All tests completed successfully!")
        print("=" * 80)

    except Exception as e:
        logger.error(f"Test failed: {e}", exc_info=True)
        print(f"\n❌ Test failed: {e}")
        return 1

    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
