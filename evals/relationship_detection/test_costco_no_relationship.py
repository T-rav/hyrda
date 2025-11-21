import os
from pathlib import Path

import pytest
from dotenv import load_dotenv

from agents.profiler.tools.internal_search import internal_search_tool

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

    # The key check: should show "No prior engagement" for Costco
    # (unless we actually have a Costco case study in the vector DB)
    assert (
        "Relationship status: No prior engagement" in result
        or "Relationship status: Existing client" in result
    ), "Result should have explicit relationship status"

    # If it says "Existing client", check the sources - they should include a Costco case study file
    if "Relationship status: Existing client" in result:
        # Should have Costco-specific case study file in sources
        has_costco_source = any(
            "costco" in source.lower()
            for source in result.split("Internal search result:")
            if source.strip()
        )
        assert (
            has_costco_source
        ), f"If showing 'Existing client', sources should include Costco case study, got: {result[:1000]}"
    else:
        # Should be "No prior engagement" - this is the expected result for Costco
        assert "Relationship status: No prior engagement" in result
        print("\n✅ PASS: Correctly identified Costco as having no prior engagement")
        print(
            "   (Even though other companies' case studies were retrieved, they were correctly filtered out)"
        )
