"""Evals for MEDDPICC check_input_completeness LLM assessment.

Tests various scenarios to ensure the agent correctly decides when to PROCEED
vs CLARIFY based on information completeness.
"""

import asyncio
import logging
import os
import sys

from dotenv import load_dotenv

# Load .env file
load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Import the actual check_input node
from agents.meddpicc_coach.nodes.check_input import check_input_completeness
from agents.meddpicc_coach.state import MeddpiccAgentState

# Test cases covering various scenarios
TEST_CASES = [
    {
        "name": "Comprehensive notes (full MEDDPICC coverage) - Jane's Equipment",
        "notes": """📝 Sales Call Notes – Jane's Equipment Repair
Date: Oct 13, 2025
👥 Attendees:
Jane – Owner/Founder
Marcus – Lead Field Tech
Alex (you) – Sales Rep, AI/Automation Solutions
Call Type: Intro / Discovery (First Call)
⏱ Duration: 32 min
🧠 Context
Jane's Equipment Repair services and maintains medical diagnostic and lab equipment (mostly small clinics and private hospitals). They're interested in using AI or "agents" to streamline daily operations — currently everything is manual.
🔍 Key Pain Points
High inbound load: Most work orders come by phone and email, no ticketing or intake structure.
Scheduling chaos: Jane or Priya (office admin) manually texts techs and updates spreadsheets.
Documentation gap: Service notes often sit in paper forms or PDFs that aren't searchable or standardized.
Compliance risk: Needs better traceability for device history (for audits or recalls).
Tech time lost: Technicians spend 20–30% of their time chasing parts or confirming addresses.
Jane summed it up: "We're great at fixing machines — terrible at fixing our own process."
🎯 What They Want to Explore
Simple automation or "agent" that can log repair requests from emails/calls.
Auto-assign jobs based on location and skill.
Generate status updates for customers automatically ("Tech en route," "Part ordered," etc.).
Centralize all repair reports in a searchable system.
Keep it HIPAA-compliant — they occasionally handle equipment with patient info labels.
💰 Budget & Timeline
No formal budget yet — Jane wants a "small pilot" first to prove ROI.
Ideally something live before end of Q1 2026.
🤝 Next Steps
Send follow-up email with short proposal (problem summary + 2–3 pilot ideas).
Book demo or workflow-mapping session next week with Jane + Marcus.
Prepare example showing how AI intake agent could auto-triage a service request from an email.
🧩 Notes & Impressions
Jane is practical, cost-conscious but open-minded.
Marcus seemed skeptical of "AI" until we explained it as automating the repetitive handoffs, not replacing techs.
Potential to expand later into parts ordering and compliance report generation, but keep pilot focused on intake → scheduling loop.""",
        "expected_decision": "PROCEED",
        "reason": "Comprehensive structured notes with 5+ pain points, economic buyer (Jane), budget context, timeline (Q1 2026), decision process hints",
    },
    {
        "name": "Sample sales call (medium coverage) - Acme Corp",
        "notes": """Call with Sarah Johnson from Acme Corp today. Really good conversation!

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
full approval process yet.""",
        "expected_decision": "PROCEED",
        "reason": "5+ MEDDPICC elements: Pain (deployment speed), Economic Buyer (CTO Mark), Metrics ($200K, 6 months ROI), Champion (Sarah), Competition (XYZ Solutions), Timeline (Q2)",
    },
    {
        "name": "Minimal notes with context - TechStartup",
        "notes": """Quick call with John at TechStartup. They have scaling issues.
Looking at solutions. John likes our approach.""",
        "expected_decision": "PROCEED",
        "reason": "Has customer name (TechStartup) + contact (John) + pain point (scaling issues) - meets threshold of 2 elements",
    },
    {
        "name": "URL notes with budget context - DataCorp",
        "notes": """Had a great call with Mike from DataCorp. Check out their company info:
https://en.wikipedia.org/wiki/Data_management

They're looking to improve their data pipeline. Budget discussion coming next week.""",
        "expected_decision": "PROCEED",
        "reason": "Customer name + contact + pain point (data pipeline) + budget mention = sufficient context",
    },
    {
        "name": "Comprehensive notes (all 8 MEDDPICC elements) - GlobalTech",
        "notes": """Fantastic call with Jennifer Martinez, VP of Engineering at GlobalTech Solutions.

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
- Jennifer will set up intro call with David (CTO) in 2 weeks""",
        "expected_decision": "PROCEED",
        "reason": "All 8 MEDDPICC elements explicitly covered with extensive detail - perfect case for analysis",
    },
    {
        "name": "Very vague single sentence - should clarify",
        "notes": "bob wants software",
        "expected_decision": "CLARIFY",
        "reason": "< 50 chars, no context, only 1 vague element (person name + generic need)",
    },
    {
        "name": "Minimal but has customer + pain - should proceed",
        "notes": "Jane's Equipment wants AI for scheduling",
        "expected_decision": "PROCEED",
        "reason": "Customer name + specific pain point = meets threshold despite brevity",
    },
    {
        "name": "Name + generic interest - should clarify",
        "notes": "talked to susan, she's interested",
        "expected_decision": "CLARIFY",
        "reason": "Too vague - no customer name, no specific pain, just generic interest",
    },
    {
        "name": "Company + vague problem - should proceed",
        "notes": "Acme Corp is having issues with their system. CEO mentioned budget.",
        "expected_decision": "PROCEED",
        "reason": "Company + problem + economic buyer mention + budget = sufficient for analysis",
    },
    {
        "name": "Vague follow-up - should clarify",
        "notes": "they need better reporting in powerbi",
        "expected_decision": "CLARIFY",
        "reason": "No customer name, no context - just a vague need without any details",
    },
]


async def run_check_input_assessment(notes: str) -> dict:
    """Run the check_input_completeness assessment."""
    # Create minimal state (just the query field is needed)
    state: MeddpiccAgentState = {
        "query": notes,
    }

    # Run the check
    result = await check_input_completeness(state, config={})

    return {
        "needs_clarification": result.get("needs_clarification", False),
        "decision": "CLARIFY" if result.get("needs_clarification") else "PROCEED",
        "clarification_message": result.get("clarification_message", ""),
    }


async def evaluate_assessment_accuracy(
    test_case: dict, assessment_result: dict
) -> tuple[bool, list[str]]:
    """Evaluate if the assessment was correct.

    Returns:
        (passed, errors) - True if assessment was accurate, list of error messages

    """
    errors = []

    # Check decision accuracy
    expected_decision = test_case["expected_decision"]
    actual_decision = assessment_result["decision"]

    if actual_decision != expected_decision:
        errors.append(
            f"Expected decision={expected_decision}, got {actual_decision}. "
            f"Reason: {test_case['reason']}"
        )

    # If expected CLARIFY, check that clarification message was generated
    if expected_decision == "CLARIFY":
        clarification_msg = assessment_result.get("clarification_message", "")
        if not clarification_msg:
            errors.append(
                "Expected CLARIFY decision but no clarification message was generated"
            )

    return len(errors) == 0, errors


async def run_evals():
    """Run all MEDDPICC clarification evals."""
    api_key = os.getenv("LLM_API_KEY") or os.getenv("OPENAI_API_KEY")
    if not api_key:
        logger.error("❌ LLM_API_KEY or OPENAI_API_KEY environment variable not set")
        return False

    logger.info("=" * 80)
    logger.info("MEDDPICC CLARIFICATION LOGIC EVALS")
    logger.info("=" * 80)

    total_tests = len(TEST_CASES)
    passed_tests = 0
    failed_tests = 0

    for i, test_case in enumerate(TEST_CASES, 1):
        logger.info(f"\n[Test {i}/{total_tests}] {test_case['name']}")
        logger.info(f"Expected: {test_case['expected_decision']}")
        logger.info("-" * 80)

        try:
            # Run assessment
            assessment_result = await run_check_input_assessment(test_case["notes"])

            # Evaluate accuracy
            passed, errors = await evaluate_assessment_accuracy(
                test_case, assessment_result
            )

            if passed:
                logger.info(
                    f"✅ PASS - Decision was correct: {assessment_result['decision']}"
                )
                logger.info(f"   Reason: {test_case['reason']}")
                passed_tests += 1
            else:
                logger.error("❌ FAIL - Decision was incorrect")
                for error in errors:
                    logger.error(f"   - {error}")
                # Show clarification message if generated
                clarification_msg = assessment_result.get("clarification_message", "")
                if clarification_msg:
                    logger.error(
                        f"   Clarification message: {clarification_msg[:200]}..."
                    )
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
        logger.info("\n🎉 ALL TESTS PASSED! MEDDPICC clarification logic is accurate.")
    else:
        logger.warning(f"\n⚠️  {failed_tests} test(s) failed. Logic needs adjustment.")

    return failed_tests == 0


if __name__ == "__main__":
    success = asyncio.run(run_evals())
    sys.exit(0 if success else 1)
