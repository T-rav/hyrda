"""
Integration test for relationship verification in final report generation.

This test validates that the enhanced Langfuse prompt correctly prevents false
positives in the Relationships section by:
1. Only claiming relationships when direct evidence exists
2. Distinguishing between "subject of work" vs "mentioned in passing"
3. Trusting the "Relationship status:" line from internal_search_tool
4. Defaulting to "No prior engagement" when evidence is ambiguous
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
    """Extract the Relationships section from a final report.

    Args:
        report: Full markdown report text

    Returns:
        The Relationships section content or None if not found
    """
    # Find the Relationships section
    match = re.search(
        r"## Relationships via 8th Light Network\s*\n(.*?)(?=\n## |\Z)",
        report,
        re.DOTALL,
    )
    if match:
        return match.group(1).strip()
    return None


def has_false_positive_language(relationship_section: str) -> tuple[bool, list[str]]:
    """Check if the relationship section contains forbidden language that indicates hallucination.

    Args:
        relationship_section: The extracted relationship section text

    Returns:
        Tuple of (has_forbidden_language, list_of_found_phrases)
    """
    forbidden_phrases = [
        "we may have worked",
        "potential relationship",
        "similar to clients",
        "we work with companies in this industry",
        "likely worked with",
        "possibly engaged",
        "appears to be a client",
    ]

    found_phrases = []
    section_lower = relationship_section.lower()

    for phrase in forbidden_phrases:
        if phrase in section_lower:
            found_phrases.append(phrase)

    return len(found_phrases) > 0, found_phrases


def has_explicit_status(relationship_section: str) -> tuple[bool, str | None]:
    """Check if the relationship section has explicit status declaration.

    Args:
        relationship_section: The extracted relationship section text

    Returns:
        Tuple of (has_status, status_value) where status_value is 'existing' or 'none'
    """
    section_lower = relationship_section.lower()

    # Look for explicit status declarations
    if "existing relationship" in section_lower or "has an existing relationship" in section_lower:
        return True, "existing"
    elif "no prior engagement" in section_lower or "no relationship found" in section_lower:
        return True, "none"

    return False, None


@pytest.mark.asyncio
@pytest.mark.integration
@pytest.mark.slow
async def test_vail_resorts_no_false_positive():
    """
    Test that Vail Resorts (company with NO prior relationship) does not get
    falsely identified as a client due to being mentioned in other companies'
    case studies.

    This is the PRIMARY test case for the false positive bug fix.
    """
    # Require env for real integration
    if not os.getenv("VECTOR_HOST"):
        pytest.skip("VECTOR_HOST not configured - skipping integration test")
    if not os.getenv("LLM_API_KEY"):
        pytest.skip("LLM_API_KEY not configured - skipping integration test")
    if not os.getenv("LANGFUSE_PUBLIC_KEY"):
        pytest.skip("LANGFUSE_PUBLIC_KEY not configured - skipping integration test")

    # Import here to avoid import errors when env not configured
    from agents.profile_agent import run_profile_agent

    # Run profile generation for Vail Resorts
    print("\n" + "=" * 80)
    print("TESTING: Vail Resorts Profile Generation (No Relationship Expected)")
    print("=" * 80)

    result = await run_profile_agent(
        query="profile Vail Resorts",
        profile_type="company",
        context={},
    )

    final_report = result.get("final_report", "")
    executive_summary = result.get("executive_summary", "")

    print(f"\n📄 Generated report length: {len(final_report)} characters")
    print(f"📄 Executive summary length: {len(executive_summary)} characters")

    # Extract relationship section
    relationship_section = extract_relationship_section(final_report)

    assert relationship_section is not None, "Report should have a Relationships section"

    print(f"\n🔍 Relationship Section:")
    print("=" * 80)
    print(relationship_section)
    print("=" * 80)

    # Check 1: Should have explicit status
    has_status, status = has_explicit_status(relationship_section)
    assert has_status, (
        "Relationship section must have explicit status declaration "
        "(either 'existing relationship' or 'no prior engagement')"
    )
    print(f"\n✅ Has explicit status: {status}")

    # Check 2: Should NOT have forbidden/speculative language
    has_forbidden, found_phrases = has_false_positive_language(relationship_section)
    assert not has_forbidden, (
        f"Relationship section contains forbidden speculative language: {found_phrases}\n"
        f"Section content: {relationship_section}"
    )
    print(f"✅ No forbidden language found")

    # Check 3: For Vail Resorts specifically, should show NO relationship
    # (unless we actually have a Vail Resorts case study, which would be detected)
    if "vail" in relationship_section.lower() and status == "existing":
        # If claiming relationship, verify there's a Vail case study source
        # Look for source citations in the full report
        sources_section_match = re.search(
            r"## Sources\s*\n(.*?)(?=\Z)", final_report, re.DOTALL
        )
        if sources_section_match:
            sources = sources_section_match.group(1)
            # Check if any source explicitly mentions Vail in the title/filename
            has_vail_source = bool(
                re.search(r"vail.*case study|vail.*project", sources, re.IGNORECASE)
            )
            assert has_vail_source, (
                "If claiming relationship with Vail Resorts, sources should include "
                f"Vail case study or project document. Sources:\n{sources[:1000]}"
            )
            print(f"✅ Vail relationship claim backed by direct source evidence")
    elif status == "none":
        print(f"✅ Correctly identified Vail Resorts as having no prior engagement")
        # Verify it doesn't mention work with Vail in speculative terms
        assert "vail" not in relationship_section.lower() or "no prior engagement" in relationship_section.lower(), (
            "If Vail is mentioned but status is 'none', should explicitly state no engagement"
        )

    print("\n🎉 TEST PASSED: Vail Resorts relationship verification successful")


@pytest.mark.asyncio
@pytest.mark.integration
@pytest.mark.slow
async def test_allcampus_existing_relationship():
    """
    Test that AllCampus (company with KNOWN prior relationship) is correctly
    identified with specific project details.

    This validates the prompt still allows legitimate relationships through.
    """
    # Require env for real integration
    if not os.getenv("VECTOR_HOST"):
        pytest.skip("VECTOR_HOST not configured - skipping integration test")
    if not os.getenv("LLM_API_KEY"):
        pytest.skip("LLM_API_KEY not configured - skipping integration test")
    if not os.getenv("LANGFUSE_PUBLIC_KEY"):
        pytest.skip("LANGFUSE_PUBLIC_KEY not configured - skipping integration test")

    # Import here to avoid import errors when env not configured
    from agents.profile_agent import run_profile_agent

    # Run profile generation for AllCampus
    print("\n" + "=" * 80)
    print("TESTING: AllCampus Profile Generation (Relationship Expected)")
    print("=" * 80)

    result = await run_profile_agent(
        query="profile AllCampus",
        profile_type="company",
        context={},
    )

    final_report = result.get("final_report", "")

    # Extract relationship section
    relationship_section = extract_relationship_section(final_report)

    assert relationship_section is not None, "Report should have a Relationships section"

    print(f"\n🔍 Relationship Section:")
    print("=" * 80)
    print(relationship_section)
    print("=" * 80)

    # Check 1: Should have explicit status
    has_status, status = has_explicit_status(relationship_section)
    assert has_status, "Relationship section must have explicit status declaration"
    print(f"\n✅ Has explicit status: {status}")

    # Check 2: Should NOT have forbidden language
    has_forbidden, found_phrases = has_false_positive_language(relationship_section)
    assert not has_forbidden, (
        f"Relationship section contains forbidden language: {found_phrases}"
    )
    print(f"✅ No forbidden language found")

    # Check 3: For AllCampus, should show EXISTING relationship
    assert status == "existing", (
        "AllCampus is a known client (has case study in KB), should show existing relationship"
    )
    print(f"✅ Correctly identified AllCampus as existing client")

    # Check 4: Should mention specific projects/deliverables
    section_lower = relationship_section.lower()
    project_indicators = [
        "partner hub",
        "archa",
        "case study",
        "project",
        "built",
        "delivered",
    ]
    found_indicators = [ind for ind in project_indicators if ind in section_lower]
    assert len(found_indicators) > 0, (
        f"Relationship section should mention specific projects/deliverables. "
        f"Found: {found_indicators}"
    )
    print(f"✅ Mentions specific project details: {found_indicators}")

    print("\n🎉 TEST PASSED: AllCampus relationship verification successful")


@pytest.mark.asyncio
@pytest.mark.integration
@pytest.mark.slow
async def test_generic_company_no_relationship():
    """
    Test a generic Fortune 500 company (e.g., Target, McDonald's) that definitely
    has NO relationship with 8th Light.

    This ensures the prompt properly handles companies that may be mentioned
    in various contexts but never as direct clients.
    """
    # Require env for real integration
    if not os.getenv("VECTOR_HOST"):
        pytest.skip("VECTOR_HOST not configured - skipping integration test")
    if not os.getenv("LLM_API_KEY"):
        pytest.skip("LLM_API_KEY not configured - skipping integration test")
    if not os.getenv("LANGFUSE_PUBLIC_KEY"):
        pytest.skip("LANGFUSE_PUBLIC_KEY not configured - skipping integration test")

    # Import here to avoid import errors when env not configured
    from agents.profile_agent import run_profile_agent

    # Test with McDonald's (very unlikely to have relationship)
    print("\n" + "=" * 80)
    print("TESTING: McDonald's Profile Generation (No Relationship Expected)")
    print("=" * 80)

    result = await run_profile_agent(
        query="profile McDonald's",
        profile_type="company",
        context={},
    )

    final_report = result.get("final_report", "")

    # Extract relationship section
    relationship_section = extract_relationship_section(final_report)

    assert relationship_section is not None, "Report should have a Relationships section"

    print(f"\n🔍 Relationship Section:")
    print("=" * 80)
    print(relationship_section)
    print("=" * 80)

    # Check 1: Should have explicit status
    has_status, status = has_explicit_status(relationship_section)
    assert has_status, "Relationship section must have explicit status declaration"
    print(f"\n✅ Has explicit status: {status}")

    # Check 2: Should NOT have forbidden language
    has_forbidden, found_phrases = has_false_positive_language(relationship_section)
    assert not has_forbidden, (
        f"Relationship section contains forbidden language: {found_phrases}"
    )
    print(f"✅ No forbidden language found")

    # Check 3: Should show NO relationship
    assert status == "none", (
        "McDonald's should show no relationship (unless we actually have a case study)"
    )
    print(f"✅ Correctly identified McDonald's as having no prior engagement")

    print("\n🎉 TEST PASSED: Generic company relationship verification successful")


if __name__ == "__main__":
    # Allow running individual tests directly
    import asyncio
    import sys

    async def run_tests():
        print("=" * 80)
        print("RELATIONSHIP VERIFICATION INTEGRATION TESTS")
        print("=" * 80)

        # Test 1: Vail Resorts (false positive case)
        try:
            await test_vail_resorts_no_false_positive()
        except Exception as e:
            print(f"\n❌ Vail Resorts test failed: {e}")
            return 1

        # Test 2: AllCampus (true positive case)
        try:
            await test_allcampus_existing_relationship()
        except Exception as e:
            print(f"\n❌ AllCampus test failed: {e}")
            return 1

        # Test 3: Generic company (no relationship)
        try:
            await test_generic_company_no_relationship()
        except Exception as e:
            print(f"\n❌ Generic company test failed: {e}")
            return 1

        print("\n" + "=" * 80)
        print("✅ ALL TESTS PASSED")
        print("=" * 80)
        return 0

    sys.exit(asyncio.run(run_tests()))
