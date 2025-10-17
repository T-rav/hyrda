import os
from pathlib import Path

import pytest
from dotenv import load_dotenv

from agents.company_profile.tools.internal_search import internal_search_tool

# Load root-level .env so VECTOR_* and LLM keys are available
ROOT_DIR = Path(__file__).resolve().parents[2]
load_dotenv(ROOT_DIR / ".env")


@pytest.mark.asyncio
@pytest.mark.integration
async def test_costco_no_relationship_integration():
    """
    Test that Costco (a company with no prior relationship) is correctly identified
    as having no prior engagement, preventing false positives from other companies'
    case studies.

    This test verifies the fix for the fallback retrieval false positive bug where
    generic "case study" searches would return OTHER companies' case studies and
    incorrectly infer a relationship.
    """

    # Require env for real integration; otherwise skip
    if not os.getenv("VECTOR_HOST"):
        pytest.skip("VECTOR_HOST not configured - skipping integration test")
    if not (os.getenv("LLM_API_KEY") or os.getenv("OPENAI_API_KEY")):
        pytest.skip("LLM API key not configured - skipping integration test")

    tool = internal_search_tool()
    if tool is None or getattr(tool, "vector_store", None) is None:
        pytest.skip("Internal search tool not available - skipping integration test")
    if getattr(tool, "llm", None) is None:
        pytest.skip(
            "LLM not available for internal_search_tool - skipping integration test"
        )

    # Run the real internal search for Costco
    result = await tool._arun("profile Costco", effort="low")

    print("\n" + "=" * 60)
    print("COSTCO SEARCH RESULT:")
    print("=" * 60)
    print(result)
    print("=" * 60)

    # Check if Costco is mentioned in the results
    # If Costco is not mentioned, the search found nothing specific
    if "costco" not in result.lower():
        # No Costco-specific content found - should show no relationship
        assert (
            "No prior engagement" in result or "No relevant information found" in result
        ), f"Expected 'No prior engagement' or 'No relevant information found' when Costco not mentioned, got: {result[:500]}"
    else:
        # Costco IS mentioned - check what kind of content it is
        # If it's just research notes (not case study/project), should still be no relationship
        has_costco_case_study = (
            "costco" in result.lower()
            and (
                "case study" in result.lower()
                or "project" in result.lower()
                or "engagement" in result.lower()
                or "partner hub" in result.lower()
            )
        )

        if has_costco_case_study:
            # If we actually have a Costco case study in the vector DB, relationship is expected
            assert (
                "Relationship status: Existing client" in result
            ), "If Costco case study exists, should show existing client"
        else:
            # Costco mentioned but only in research/analysis context - no relationship
            assert (
                "No prior engagement" in result
            ), f"Expected 'No prior engagement' for Costco research notes (not case studies), got: {result[:500]}"

    # CRITICAL: Should NOT show existing client relationship unless Costco is actually mentioned
    # and there's evidence of case study/project work
    if "costco" not in result.lower():
        assert (
            "Existing client" not in result
        ), f"FALSE POSITIVE: Shows 'Existing client' without mentioning Costco! Result: {result[:500]}"
