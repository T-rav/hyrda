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
async def test_sanmar_false_positive_investigation():
    """
    Test to investigate the false positive where SanMar is incorrectly identified
    as an existing client when running:
    "profile SanMar and opportunities to help support their growth"

    This test is designed to:
    1. Reproduce the false positive
    2. Capture the culprit document(s) that trigger it
    3. Identify why the internal_search_tool is seeing relationship signals

    Expected: "Relationship status: No prior engagement"
    Actual (bug): "Relationship status: Existing client"
    """

    # Require env for real integration; otherwise skip
    if not os.getenv("VECTOR_HOST"):
        pytest.skip("VECTOR_HOST not configured - skipping integration test")
    if not (os.getenv("LLM_API_KEY") or os.getenv("OPENAI_API_KEY")):
        pytest.skip("LLM API key not configured - skipping integration test")

    tool = internal_search_tool()
    if tool is None or getattr(tool, "qdrant_client", None) is None:
        pytest.skip("Internal search tool not available - skipping integration test")
    if getattr(tool, "llm", None) is None:
        pytest.skip(
            "LLM not available for internal_search_tool - skipping integration test"
        )

    # Run the exact query that's causing the false positive
    query = "profile SanMar and opportunities to help support their growth"
    result = await tool._arun(query, effort="low")

    print("\n" + "=" * 80)
    print("SANMAR FALSE POSITIVE INVESTIGATION")
    print("=" * 80)
    print(f"Query: {query}")
    print("=" * 80)
    print("RESULT:")
    print(result)
    print("=" * 80)

    # The test expects "No prior engagement" as the correct result
    if "Relationship status: No prior engagement" in result:
        print("\n✅ PASS: Correctly identified SanMar as having no prior engagement")
        print("   The fix prevents Samaritan Ministries CRM records from causing false positives")
    elif "Relationship status: Existing client" in result:
        print("\n🚨 FALSE POSITIVE DETECTED (BUG REGRESSION)!")
        print("-" * 80)
        print("SanMar is being incorrectly identified as an existing client.")
        print("The bug may have regressed - check metric/CRM record filtering.")
        print("-" * 80)

        # Extract sources from result
        if "Sources:" in result or "**Found in" in result:
            sources_section = (
                result.split("Sources:")[1]
                if "Sources:" in result
                else result.split("**Found in")[1]
            )
            print("\nSOURCES RETURNED:")
            print(sources_section[:1000])
            print("-" * 80)

        pytest.fail(
            f"❌ FALSE POSITIVE REGRESSION: SanMar incorrectly identified as existing client.\n"
            f"   Query: '{query}'\n"
            f"   Expected: 'Relationship status: No prior engagement'\n"
            f"   Got: 'Relationship status: Existing client'\n\n"
            f"   The fix for metric/CRM record filtering may have regressed.\n"
            f"   Check internal_search.py lines 869-900 for the company name check.\n\n"
            f"   Full result:\n{result[:2000]}"
        )
    else:
        pytest.fail(
            f"Result missing explicit relationship status. Got:\n{result[:1000]}"
        )
