#!/usr/bin/env python3
"""Test script to check for Vail Resorts false positive in production.

This script can be run on the production server to test if the relationship
verification system is working correctly for the Vail Resorts case.

Usage:
    PYTHONPATH=bot python scripts/test_vail_resorts_production.py

Expected result:
    Relationship status: No prior engagement (no false positive)
"""

import asyncio
import os
import sys
from pathlib import Path

# Add bot directory to path
bot_dir = Path(__file__).parent.parent / "bot"
sys.path.insert(0, str(bot_dir.parent))

# Load environment variables
from dotenv import load_dotenv

load_dotenv()


async def test_vail_resorts_query():
    from bot.agents.company_profile.tools.internal_search import internal_search_tool

    query = "profile Vail Resorts and highlight how our recent case study https://8thlight.com/case-studies/aspenware could be useful for them"

    print("=" * 80)
    print("VAIL RESORTS FALSE POSITIVE TEST")
    print("=" * 80)
    print(f"\nQuery: {query}")
    print("\nEnvironment:")
    print(f"  VECTOR_HOST: {os.getenv('VECTOR_HOST', 'NOT SET')}")
    print(f"  VECTOR_PORT: {os.getenv('VECTOR_PORT', 'NOT SET')}")
    print(f"  VECTOR_COLLECTION_NAME: {os.getenv('VECTOR_COLLECTION_NAME', 'NOT SET')}")
    print(f"  LLM_MODEL: {os.getenv('LLM_MODEL', 'NOT SET')}")
    print()

    try:
        # Initialize tool
        print("Initializing internal search tool...")
        tool = internal_search_tool()

        if not tool.vector_store or not tool.llm:
            print("❌ FAILED: Tool not initialized properly")
            print(f"   vector_store: {tool.vector_store}")
            print(f"   llm: {tool.llm}")
            return False

        print("✓ Tool initialized successfully")
        print()

        # Run the query
        print("Running query (effort=high, may take 30-60 seconds)...")
        result = await tool._arun(query, effort="high")

        print()
        print("=" * 80)
        print("RESULT:")
        print("=" * 80)
        print(result)
        print("=" * 80)
        print()

        # Check for false positive
        if "Relationship status: Existing client" in result:
            print("❌ FALSE POSITIVE DETECTED!")
            print("   The tool is incorrectly claiming Vail Resorts is a client.")
            print("   This is the bug we're trying to fix.")
            return False
        elif "Relationship status: No prior engagement" in result:
            print("✅ CORRECT: No false positive")
            print("   The tool correctly identifies no relationship with Vail Resorts.")
            return True
        else:
            print("⚠️  WARNING: No clear relationship status found in result")
            print("   Expected to see either 'Existing client' or 'No prior engagement'")
            return False

    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback

        traceback.print_exc()
        return False


async def test_internal_search_tool_only():
    from bot.agents.company_profile.tools.internal_search import internal_search_tool

    print("\n" + "=" * 80)
    print("TESTING INTERNAL SEARCH TOOL ONLY")
    print("=" * 80)

    try:
        tool = internal_search_tool()
        result = await tool._arun("profile Vail Resorts", effort="medium")

        print("\nInternal Search Result:")
        print("-" * 80)
        print(result)
        print("-" * 80)

        if "Relationship status: No prior engagement" in result:
            print("\n✅ Internal search tool is working correctly")
            return True
        elif "Relationship status: Existing client" in result:
            print("\n❌ Internal search tool has the false positive bug")
            return False
        else:
            print("\n⚠️  Internal search tool returned unclear status")
            return False

    except Exception as e:
        print(f"\n❌ ERROR in internal search tool: {e}")
        return False


async def main():
    """Run all tests."""
    print("\n🔍 Starting Vail Resorts False Positive Tests\n")

    # Test 1: Internal search tool only
    test1_passed = await test_internal_search_tool_only()

    # Test 2: Full query with Aspenware context
    test2_passed = await test_vail_resorts_query()

    # Summary
    print("\n" + "=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)
    print(f"Test 1 (Internal Search Tool):    {'✅ PASS' if test1_passed else '❌ FAIL'}")
    print(f"Test 2 (Full Query):               {'✅ PASS' if test2_passed else '❌ FAIL'}")
    print("=" * 80)

    if test1_passed and test2_passed:
        print("\n✅ All tests passed! No false positive detected.")
        return 0
    else:
        print(
            "\n❌ Tests failed. False positive bug still present in production."
        )
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
