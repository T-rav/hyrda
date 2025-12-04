#!/usr/bin/env python3
"""Test if edge cases cause actual false positives in production."""

import asyncio
from dotenv import load_dotenv

load_dotenv()

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "bot"))

from agents.company_profile.tools.internal_search import InternalSearchTool


async def test_real_world():
    """Test edge cases with actual vector database."""
    tool = InternalSearchTool()

    edge_cases = [
        # Punctuation edge case
        (
            "J.P. Morgan case studies",
            "j.p. morgan or j.p morgan - should work either way",
        ),
        # URL in parentheses (after Slack URL cleaning)
        (
            "Baker College (baker.edu) existing client",
            "baker.edu included but shouldn't cause issue",
        ),
        # Company with stop word in name (rare but possible)
        (
            "Past Perfect Software projects",
            "Will extract nothing - but unlikely real company",
        ),
    ]

    print("=" * 80)
    print("Testing Real-World Edge Cases Against Vector Database")
    print("=" * 80)

    issues = []

    for query, explanation in edge_cases:
        print(f"\n{'=' * 80}")
        print(f"Query: {query}")
        print(f"Note: {explanation}")
        print(f"{'=' * 80}")

        try:
            result = await tool._arun(query=query, effort="low")

            if "Relationship status: Existing client" in result:
                print("❌ FALSE POSITIVE - Shows existing client when shouldn't")
                issues.append(query)
            elif "Relationship status: No prior engagement" in result:
                print("✅ Correctly shows no relationship")
            else:
                print("⚠️  Unclear relationship status")

            print("\nFirst 300 chars:")
            print(result[:300])

        except Exception as e:
            print(f"❌ ERROR: {e}")
            issues.append(query)

    print("\n" + "=" * 80)
    if issues:
        print(f"⚠️  {len(issues)} edge cases need attention:")
        for issue in issues:
            print(f"  - {issue}")
        return 1
    else:
        print("✅ All edge cases handled correctly!")
        return 0


if __name__ == "__main__":
    exit_code = asyncio.run(test_real_world())
    sys.exit(exit_code)
