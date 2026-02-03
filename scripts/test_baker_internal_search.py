#!/usr/bin/env python3
"""Test internal search tool for Baker College to debug false positive."""

import asyncio
import os
import sys
from pathlib import Path

# Load environment variables
from dotenv import load_dotenv

load_dotenv()

# Add bot to path
sys.path.insert(0, str(Path(__file__).parent.parent / "bot"))

from agents.company_profile.tools.internal_search import InternalSearchTool


async def main():
    tool = InternalSearchTool()

    print("=" * 80)
    print("Testing Internal Search Tool for Baker College")
    print("=" * 80)

    # Test query that the agent would use
    query = "Baker College existing client relationship projects case studies"

    print(f"\nQuery: {query}")
    print("\nExecuting search...\n")

    result = await tool._arun(query=query, effort="high")

    print("=" * 80)
    print("RESULT:")
    print("=" * 80)
    print(result)
    print("\n" + "=" * 80)

    # Check for relationship status line
    if "Relationship status:" in result:
        print("\n✅ Found explicit relationship status line:")
        for line in result.split("\n"):
            if "Relationship status:" in line:
                print(f"   {line}")
    else:
        print("\n⚠️  WARNING: No explicit 'Relationship status:' line found!")
        print("   This could cause the LLM to infer relationships from weak matches.")

    # Check for Baker College mentions
    print("\n" + "=" * 80)
    print("ANALYSIS:")
    print("=" * 80)

    baker_count = result.lower().count("baker college")
    baker_only = result.lower().count("baker") - baker_count

    print(f"'Baker College' mentions: {baker_count}")
    print(f"'Baker' (without College) mentions: {baker_only}")

    if baker_count > 0:
        print("\n📄 Document excerpts mentioning 'Baker College':")
        lines = result.split("\n")
        for i, line in enumerate(lines):
            if "baker college" in line.lower():
                # Print with context
                start = max(0, i - 1)
                end = min(len(lines), i + 2)
                print(f"\n   Context (lines {start}-{end}):")
                for j in range(start, end):
                    marker = ">>>" if j == i else "   "
                    print(f"   {marker} {lines[j][:120]}")


if __name__ == "__main__":
    asyncio.run(main())
