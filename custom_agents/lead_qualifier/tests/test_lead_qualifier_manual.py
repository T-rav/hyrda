"""Manual test script for Lead Qualifier agent.

Run this to verify the Lead Qualifier workflow is working correctly
with real HubSpot-style data.

Usage:
    cd custom_agents/lead_qualifier
    python -m tests.test_lead_qualifier_manual
"""

import asyncio
import logging
import sys
from pathlib import Path

# Load environment variables
from dotenv import load_dotenv

# Load .env from project root
project_root = Path(__file__).parent.parent.parent.parent.parent
load_dotenv(project_root / ".env")

# Add custom_agents to path
sys.path.insert(0, str(project_root))

from custom_agents.lead_qualifier.nodes.graph_builder import build_lead_qualifier
from custom_agents.lead_qualifier.state import QualifierInput

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Sample HubSpot leads for testing
ENTERPRISE_HEALTHCARE_LEAD = {
    "company": {
        "company_name": "MedTech Solutions Inc",
        "company_domain": "medtechsolutions.com",
        "industry": "Healthcare Technology",
        "company_size": "500-1000",
        "location": "Boston, MA",
        "region": "Northeast",
    },
    "contact": {
        "contact_name": "Dr. Sarah Chen",
        "job_title": "Chief Technology Officer",
        "seniority": "C-level",
        "department": "Engineering",
        "lifecycle_stage": "Opportunity",
        "lead_source": "Inbound",
        "original_source": "Website",
        "hubspot_lead_score": 92.0,
    },
    "sequence_identifier": "enterprise_healthcare_2024",
}

FINTECH_SCALEUP_LEAD = {
    "company": {
        "company_name": "PayFlow Systems",
        "company_domain": "payflow.io",
        "industry": "FinTech",
        "company_size": "200-500",
        "location": "New York, NY",
        "region": "Northeast",
    },
    "contact": {
        "contact_name": "Michael Rodriguez",
        "job_title": "VP of Engineering",
        "seniority": "VP",
        "department": "Engineering",
        "lifecycle_stage": "Marketing Qualified Lead",
        "lead_source": "Trade Show",
        "original_source": "Money20/20",
        "hubspot_lead_score": 78.0,
    },
}

EARLY_STAGE_STARTUP = {
    "company": {
        "company_name": "NexGen Analytics",
        "company_domain": "nexgen-analytics.co",
        "industry": "Artificial Intelligence",
        "company_size": "10-50",
        "location": "Austin, TX",
        "region": "South",
    },
    "contact": {
        "contact_name": "Alex Kumar",
        "job_title": "Founder & CEO",
        "seniority": "C-level",
        "department": "Leadership",
        "lifecycle_stage": "Lead",
        "lead_source": "Referral",
        "original_source": "Partner",
        "hubspot_lead_score": 35.0,
    },
}

SMALL_LOCAL_BUSINESS = {
    "company": {
        "company_name": "Main Street Cafe",
        "company_domain": "mainstreetcafe.com",
        "industry": "Food & Beverage",
        "company_size": "1-10",
        "location": "Portland, OR",
        "region": "West",
    },
    "contact": {
        "contact_name": "Jane Smith",
        "job_title": "Owner",
        "seniority": "IC",
        "department": "Leadership",
        "lifecycle_stage": "Subscriber",
        "lead_source": "Organic",
        "original_source": "Blog",
        "hubspot_lead_score": 12.0,
    },
}

MINIMAL_DATA_LEAD = {
    "company": {
        "company_name": "Unknown Corp",
    },
    "contact": {
        "contact_name": "Someone",
    },
}


async def run_qualification(lead_data: dict, test_name: str):
    """Test the Lead Qualifier with sample HubSpot data.

    Args:
        lead_data: HubSpot lead data
        test_name: Name of the test for logging

    """
    print(f"\n{'=' * 80}")
    print(f"TEST: {test_name}")
    print(f"{'=' * 80}")
    print(f"Company: {lead_data.get('company', {}).get('company_name', 'N/A')}")
    print(f"Contact: {lead_data.get('contact', {}).get('contact_name', 'N/A')}")
    print(f"Title: {lead_data.get('contact', {}).get('job_title', 'N/A')}")
    print(f"Industry: {lead_data.get('company', {}).get('industry', 'N/A')}")
    print(f"Size: {lead_data.get('company', {}).get('company_size', 'N/A')}")
    print()

    # Build graph
    graph = build_lead_qualifier()

    # Prepare input
    input_data = QualifierInput(
        company=lead_data.get("company", {}),
        contact=lead_data.get("contact", {}),
        sequence_identifier=lead_data.get("sequence_identifier"),
    )

    # Run qualification
    logger.info(f"Running qualification for {test_name}...")
    result = await graph.ainvoke(input_data)

    # Display results
    print("\n📊 QUALIFICATION RESULTS:")
    print("-" * 80)
    print(f"Score: {result.get('qualification_score', 'N/A')}/100")
    print(f"Tier: {result.get('fit_tier', 'N/A')}")
    print()
    print(f"Recommended Solutions: {result.get('recommended_solution', [])}")
    print(f"Similar Clients: {result.get('similar_client_example', [])}")
    print(f"Primary Initiative: {result.get('primary_initiative', 'N/A')}")
    print(f"Risk Flags: {result.get('risk_flags', [])}")
    print()
    print("Summary:")
    print(result.get('qualification_summary', 'No summary generated'))
    print("-" * 80)

    return result


async def main():
    """Run all manual tests."""
    print("\n🚀 Lead Qualifier Agent - Manual Test Suite")
    print("=" * 80)
    print("Testing with real HubSpot-style lead data")
    print()

    try:
        # Test 1: Enterprise Healthcare (expected: High tier)
        await run_qualification(ENTERPRISE_HEALTHCARE_LEAD, "Enterprise Healthcare (Expected: High)")

        # Test 2: FinTech Scaleup (expected: Medium-High tier)
        await run_qualification(FINTECH_SCALEUP_LEAD, "FinTech Scaleup (Expected: Medium-High)")

        # Test 3: Early Stage Startup (expected: Medium tier)
        await run_qualification(EARLY_STAGE_STARTUP, "Early Stage Startup (Expected: Medium)")

        # Test 4: Small Local Business (expected: Low tier)
        await run_qualification(SMALL_LOCAL_BUSINESS, "Small Local Business (Expected: Low)")

        # Test 5: Minimal Data (edge case)
        await test_qualification(MINIMAL_DATA_LEAD, "Minimal Data (Edge Case)")

        print("\n" + "=" * 80)
        print("✅ All manual tests completed!")
        print("=" * 80)

    except Exception as e:
        logger.error(f"Test failed: {e}", exc_info=True)
        print(f"\n❌ Test failed: {e}")
        return 1

    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
