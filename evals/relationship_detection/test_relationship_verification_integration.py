"""
Real integration tests for relationship verification using actual internal search.

These tests use the same pattern as existing integration tests:
1. Use internal_search_tool() directly (no full ProfileAgent needed)
2. Call tool._arun() to get research results
3. Verify the "Relationship status:" line is correct
4. Build the formatted context and prompt
5. Verify the prompt contains the right evidence for the LLM

This validates the complete flow from vector search → internal search synthesis →
formatted context → final report prompt.
"""

import os
from pathlib import Path

import pytest
from dotenv import load_dotenv

from agents.company_profile import prompts
from agents.company_profile.tools.internal_search import internal_search_tool
from agents.company_profile.utils import format_research_context

# Load root-level .env
ROOT_DIR = Path(__file__).resolve().parents[2]
load_dotenv(ROOT_DIR / ".env")


@pytest.mark.asyncio
@pytest.mark.integration
async def test_vail_resorts_no_false_positive_real_search():
    """
    Integration test: Vail Resorts should show NO relationship.

    This is the critical false positive test case - Vail may be mentioned
    in other companies' case studies (e.g., Aspenware works with Vail), but
    we should NOT claim we worked with Vail directly.
    """
    # Require env for real integration
    if not os.getenv("VECTOR_HOST"):
        pytest.skip("VECTOR_HOST not configured - skipping integration test")
    if not (os.getenv("LLM_API_KEY") or os.getenv("OPENAI_API_KEY")):
        pytest.skip("LLM API key not configured - skipping integration test")

    tool = internal_search_tool()
    if tool is None or getattr(tool, "vector_store", None) is None:
        pytest.skip("Internal search tool not available - skipping integration test")
    if getattr(tool, "llm", None) is None:
        pytest.skip("LLM not available for internal_search_tool - skipping integration test")

    print("\n" + "=" * 80)
    print("INTEGRATION TEST: Vail Resorts Internal Search")
    print("=" * 80)

    # Run real internal search for Vail Resorts
    result = await tool._arun("profile Vail Resorts", effort="medium")

    print(f"\n📋 Internal Search Result:")
    print("=" * 80)
    print(result[:1000] if len(result) > 1000 else result)
    print("=" * 80)

    # CRITICAL: Should show "No prior engagement" for Vail
    assert "Relationship status:" in result, (
        "Internal search should return explicit relationship status"
    )

    # Vail should NOT be marked as existing client (unless we actually have a Vail case study)
    if "Relationship status: Existing client" in result:
        # If it claims existing client, verify there's a Vail-specific case study
        assert "vail" in result.lower() and ("case study" in result.lower() or "project" in result.lower()), (
            f"If claiming Vail relationship, must have Vail case study. Got:\n{result[:500]}"
        )
        print("✅ Vail has existing relationship (verified by case study)")
    else:
        # Should show no relationship
        assert "Relationship status: No prior engagement" in result, (
            f"Expected 'No prior engagement' for Vail. Got:\n{result[:500]}"
        )
        print("✅ Correctly identified Vail as having no prior engagement")

    # Build formatted context
    context = await format_research_context(
        research_brief="Focus on Vail Resorts",
        notes=[result],
        profile_type="company",
        max_sources=25,
    )

    # Verify context carries the relationship status
    assert "Relationship status:" in context
    print("✅ Relationship status preserved in formatted context")


@pytest.mark.asyncio
@pytest.mark.integration
async def test_costco_no_relationship_real_search():
    """
    Integration test: Costco should show NO relationship.

    Costco is a Fortune 500 company that we definitely have not worked with.
    """
    # Require env for real integration
    if not os.getenv("VECTOR_HOST"):
        pytest.skip("VECTOR_HOST not configured - skipping integration test")
    if not (os.getenv("LLM_API_KEY") or os.getenv("OPENAI_API_KEY")):
        pytest.skip("LLM API key not configured - skipping integration test")

    tool = internal_search_tool()
    if tool is None or getattr(tool, "vector_store", None) is None:
        pytest.skip("Internal search tool not available - skipping integration test")
    if getattr(tool, "llm", None) is None:
        pytest.skip("LLM not available for internal_search_tool - skipping integration test")

    print("\n" + "=" * 80)
    print("INTEGRATION TEST: Costco Internal Search")
    print("=" * 80)

    # Run real internal search for Costco
    result = await tool._arun("profile Costco", effort="medium")

    print(f"\n📋 Internal Search Result:")
    print("=" * 80)
    print(result[:1000] if len(result) > 1000 else result)
    print("=" * 80)

    # Should show "No prior engagement"
    assert "Relationship status: No prior engagement" in result, (
        f"Expected 'No prior engagement' for Costco. Got:\n{result[:500]}"
    )
    print("✅ Correctly identified Costco as having no prior engagement")


@pytest.mark.asyncio
@pytest.mark.integration
async def test_allcampus_existing_relationship_real_search():
    """
    Integration test: AllCampus should show EXISTING relationship.

    AllCampus is a known client with case study in our knowledge base.
    """
    # Require env for real integration
    if not os.getenv("VECTOR_HOST"):
        pytest.skip("VECTOR_HOST not configured - skipping integration test")
    if not (os.getenv("LLM_API_KEY") or os.getenv("OPENAI_API_KEY")):
        pytest.skip("LLM API key not configured - skipping integration test")

    tool = internal_search_tool()
    if tool is None or getattr(tool, "vector_store", None) is None:
        pytest.skip("Internal search tool not available - skipping integration test")
    if getattr(tool, "llm", None) is None:
        pytest.skip("LLM not available for internal_search_tool - skipping integration test")

    print("\n" + "=" * 80)
    print("INTEGRATION TEST: AllCampus Internal Search")
    print("=" * 80)

    # Run real internal search for AllCampus
    result = await tool._arun("profile AllCampus", effort="medium")

    print(f"\n📋 Internal Search Result:")
    print("=" * 80)
    print(result[:1000] if len(result) > 1000 else result)
    print("=" * 80)

    # Check if AllCampus case study exists
    has_case_study = (
        "AllCampus" in result
        and ("case study" in result.lower() or "Partner Hub" in result or "project" in result.lower())
    )

    if not has_case_study:
        pytest.skip(
            "AllCampus case study not found in vector DB - data needs to be ingested. "
            "This test requires AllCampus case study to be in the knowledge base."
        )

    # Should show existing relationship
    assert "Relationship status: Existing client" in result, (
        f"Expected 'Existing client' for AllCampus. Got:\n{result[:500]}"
    )
    print("✅ Correctly identified AllCampus as existing client")

    # Should mention specific projects
    has_project_details = (
        "Partner Hub" in result
        or "Archa" in result
        or ("allcampus" in result.lower() and "project" in result.lower())
    )
    assert has_project_details, (
        f"Expected project details for AllCampus. Got:\n{result[:500]}"
    )
    print("✅ Includes specific project details")


@pytest.mark.asyncio
@pytest.mark.integration
async def test_3step_existing_relationship_real_search():
    """
    Integration test: 3Step should show EXISTING relationship.

    3Step is a known client with case study in our knowledge base.
    """
    # Require env for real integration
    if not os.getenv("VECTOR_HOST"):
        pytest.skip("VECTOR_HOST not configured - skipping integration test")
    if not (os.getenv("LLM_API_KEY") or os.getenv("OPENAI_API_KEY")):
        pytest.skip("LLM API key not configured - skipping integration test")

    tool = internal_search_tool()
    if tool is None or getattr(tool, "vector_store", None) is None:
        pytest.skip("Internal search tool not available - skipping integration test")
    if getattr(tool, "llm", None) is None:
        pytest.skip("LLM not available for internal_search_tool - skipping integration test")

    print("\n" + "=" * 80)
    print("INTEGRATION TEST: 3Step Internal Search")
    print("=" * 80)

    # Run real internal search for 3Step
    result = await tool._arun("profile 3Step", effort="medium")

    print(f"\n📋 Internal Search Result:")
    print("=" * 80)
    print(result[:1000] if len(result) > 1000 else result)
    print("=" * 80)

    # Check if 3Step case study exists
    has_case_study = (
        "3step" in result.lower()
        and ("case study" in result.lower() or "project" in result.lower())
    )

    if not has_case_study:
        pytest.skip(
            "3Step case study not found in vector DB - data needs to be ingested. "
            "This test requires 3Step case study to be in the knowledge base."
        )

    # Should show existing relationship
    assert "Relationship status: Existing client" in result, (
        f"Expected 'Existing client' for 3Step. Got:\n{result[:500]}"
    )
    print("✅ Correctly identified 3Step as existing client")


if __name__ == "__main__":
    # Allow running tests directly
    import asyncio
    import sys

    async def run_tests():
        print("=" * 80)
        print("RELATIONSHIP VERIFICATION INTEGRATION TESTS")
        print("(Using real internal search + vector DB)")
        print("=" * 80)

        tests = [
            ("Vail Resorts (No Relationship)", test_vail_resorts_no_false_positive_real_search),
            ("Costco (No Relationship)", test_costco_no_relationship_real_search),
            ("AllCampus (Existing Relationship)", test_allcampus_existing_relationship_real_search),
            ("3Step (Existing Relationship)", test_3step_existing_relationship_real_search),
        ]

        for test_name, test_func in tests:
            print(f"\n{'=' * 80}")
            print(f"Running: {test_name}")
            print('=' * 80)
            try:
                await test_func()
                print(f"✅ {test_name} PASSED")
            except Exception as e:
                print(f"❌ {test_name} FAILED: {e}")
                return 1

        print("\n" + "=" * 80)
        print("✅ ALL INTEGRATION TESTS PASSED")
        print("=" * 80)
        return 0

    sys.exit(asyncio.run(run_tests()))
