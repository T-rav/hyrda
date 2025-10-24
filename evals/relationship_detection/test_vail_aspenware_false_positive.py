"""
Critical test case: Vail Resorts with Aspenware case study context.

This tests the EXACT false positive scenario where:
- Vail Resorts has NO prior relationship with 8th Light
- Aspenware case study exists (work with a DIFFERENT ski/resort company)
- The prompt must NOT claim we worked with Vail just because Aspenware is in same industry

User query: "profile Vail Resorts and highlight how our recent case study
            https://8thlight.com/case-studies/aspenware could be useful for them"
"""

import os
import re
from pathlib import Path

import pytest
from dotenv import load_dotenv

# Load root-level .env
ROOT_DIR = Path(__file__).resolve().parents[2]
load_dotenv(ROOT_DIR / ".env")


def extract_relationship_section(report: str) -> str | None:
    """Extract the Relationships section from a final report."""
    match = re.search(
        r"## Relationships via 8th Light Network\s*\n(.*?)(?=\n## |\Z)",
        report,
        re.DOTALL,
    )
    if match:
        return match.group(1).strip()
    return None


@pytest.mark.asyncio
@pytest.mark.integration
@pytest.mark.slow
async def test_vail_resorts_with_aspenware_context():
    """
    CRITICAL TEST: Vail Resorts with Aspenware case study in context.

    This is the exact scenario that was causing false positives:
    - User asks about Vail Resorts (NO relationship)
    - Mentions Aspenware case study (DIFFERENT company, YES relationship)
    - Bot must NOT confuse the two and claim we worked with Vail

    Expected behavior:
    - Relationships section should say "No prior engagement" for Vail
    - Should mention Aspenware as relevant example/comparison
    - Should NOT claim we worked with Vail Resorts directly
    """
    # Require env for real integration
    if not os.getenv("VECTOR_HOST"):
        pytest.skip("VECTOR_HOST not configured - skipping integration test")
    if not os.getenv("LLM_API_KEY"):
        pytest.skip("LLM_API_KEY not configured - skipping integration test")

    # Import here to avoid import errors
    from unittest.mock import AsyncMock, MagicMock

    from agents.profile_agent import ProfileAgent

    # The exact user query that exposed the bug
    user_query = (
        "profile Vail Resorts and highlight how our recent case study "
        "https://8thlight.com/case-studies/aspenware could be useful for them"
    )

    print("\n" + "=" * 80)
    print("CRITICAL TEST: Vail Resorts with Aspenware Context")
    print("=" * 80)
    print(f"Query: {user_query}")
    print("=" * 80)

    # Create mock slack service for testing
    mock_slack_service = MagicMock()
    mock_slack_service.send_message = AsyncMock()
    mock_slack_service.upload_file = AsyncMock()

    # Initialize and run profile agent
    agent = ProfileAgent()
    result = await agent.run(
        query=user_query,
        context={
            "user_id": "test_user",
            "channel": "test_channel",
            "slack_service": mock_slack_service,
        },
    )

    final_report = result.get("final_report", "")
    executive_summary = result.get("executive_summary", "")

    print(f"\n📄 Generated report length: {len(final_report)} characters")

    # Extract relationship section
    relationship_section = extract_relationship_section(final_report)

    assert relationship_section is not None, "Report should have a Relationships section"

    print(f"\n🔍 Relationship Section:")
    print("=" * 80)
    print(relationship_section)
    print("=" * 80)

    # CRITICAL CHECK 1: Should NOT claim direct relationship with Vail
    section_lower = relationship_section.lower()

    # Forbidden patterns that indicate false positive
    false_positive_patterns = [
        r"8th light.*(?:worked with|built.*for|delivered.*to|engaged with|partnered with).*vail",
        r"vail.*(?:is|was).*(?:client|customer|engagement)",
        r"our work (?:with|for) vail",
        r"vail.*case study",  # Unless it's explicitly saying "no case study exists"
    ]

    found_false_positives = []
    for pattern in false_positive_patterns:
        matches = re.findall(pattern, section_lower, re.IGNORECASE)
        if matches:
            # Check if it's in a negative context (e.g., "no case study for Vail")
            for match in matches:
                context = section_lower[max(0, section_lower.find(match) - 50):section_lower.find(match) + len(match) + 50]
                if not any(neg in context for neg in ["no ", "not ", "without ", "never "]):
                    found_false_positives.append(match)

    assert len(found_false_positives) == 0, (
        f"❌ FALSE POSITIVE DETECTED: Claimed relationship with Vail Resorts!\n"
        f"Found patterns: {found_false_positives}\n"
        f"Relationship section:\n{relationship_section}"
    )
    print("✅ No false positive claims about Vail Resorts relationship")

    # CRITICAL CHECK 2: Should explicitly state "No prior engagement"
    has_no_engagement = any([
        "no prior engagement" in section_lower,
        "no relationship" in section_lower,
        "no documented" in section_lower and "collaboration" in section_lower,
        "not identified any past projects" in section_lower,
    ])

    assert has_no_engagement, (
        f"❌ AMBIGUOUS STATUS: Relationship section should explicitly state 'No prior engagement' for Vail\n"
        f"Relationship section:\n{relationship_section}"
    )
    print("✅ Explicitly states no prior engagement with Vail")

    # CHECK 3: May reference Aspenware as relevant example (this is GOOD)
    # The report should be able to mention Aspenware as a comparison/example
    # But only in appropriate context (e.g., Solutions section, not Relationships)
    if "aspenware" in final_report.lower():
        # Check WHERE Aspenware is mentioned
        aspenware_in_relationships = "aspenware" in section_lower

        if aspenware_in_relationships:
            # It's OK to mention Aspenware in Relationships section IF it's clear
            # it's a different company being used as an example/comparison
            comparison_indicators = [
                "similar to",
                "like our work with",
                "comparable to",
                "for example",
                "such as",
                "including",
            ]
            has_comparison_context = any(ind in section_lower for ind in comparison_indicators)

            if not has_comparison_context:
                # Mentioned Aspenware without comparison context - potential confusion
                pytest.fail(
                    f"⚠️ Aspenware mentioned in Relationships section without clear comparison context. "
                    f"This could be confusing. Consider moving to Solutions section instead.\n"
                    f"Relationship section:\n{relationship_section}"
                )

        print("✅ Aspenware mentioned appropriately (if at all)")

    # CHECK 4: Should NOT have speculative language
    speculative_phrases = [
        "may have worked",
        "likely worked",
        "potential relationship",
        "appears to be",
        "possibly engaged",
    ]

    found_speculative = [phrase for phrase in speculative_phrases if phrase in section_lower]

    assert len(found_speculative) == 0, (
        f"❌ SPECULATIVE LANGUAGE: Found forbidden speculative phrases: {found_speculative}\n"
        f"Relationship section:\n{relationship_section}"
    )
    print("✅ No speculative language")

    print("\n" + "=" * 80)
    print("🎉 TEST PASSED: Vail Resorts false positive prevention successful!")
    print("=" * 80)
    print("\nSummary:")
    print("- ✅ No false claim of relationship with Vail Resorts")
    print("- ✅ Explicitly states 'No prior engagement'")
    print("- ✅ No speculative language")
    print("- ✅ Aspenware referenced appropriately (if mentioned)")
    print("\nThe enhanced prompt successfully prevents false positives!")


if __name__ == "__main__":
    import asyncio
    import sys

    sys.exit(asyncio.run(test_vail_resorts_with_aspenware_context()))
