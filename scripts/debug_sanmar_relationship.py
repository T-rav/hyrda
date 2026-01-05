#!/usr/bin/env python
"""
Diagnostic script to debug SanMar false positive in staging.

Usage:
    PYTHONPATH=bot python scripts/debug_sanmar_relationship.py > /tmp/sanmar_debug.log 2>&1

This script:
1. Connects to the REAL vector DB (staging/production)
2. Runs the exact query causing the false positive
3. Captures ALL internal logs including relationship_evidence flag
4. Shows which documents triggered the relationship detection
"""

import asyncio
import logging
import os
import sys
from pathlib import Path

# Setup detailed logging BEFORE any imports
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    stream=sys.stdout,
)

# Add bot to path
ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR / "bot"))

from dotenv import load_dotenv

load_dotenv(ROOT_DIR / ".env")


async def main():
    print("=" * 100)
    print("SANMAR RELATIONSHIP FALSE POSITIVE DIAGNOSTIC")
    print("=" * 100)
    print(f"\nEnvironment:")
    print(f"  VECTOR_HOST: {os.getenv('VECTOR_HOST')}")
    print(f"  VECTOR_PORT: {os.getenv('VECTOR_PORT')}")
    print(f"  VECTOR_COLLECTION: {os.getenv('VECTOR_COLLECTION_NAME', 'insightmesh-knowledge-base')}")
    print(f"  LLM_MODEL: {os.getenv('LLM_MODEL', 'gpt-4o-mini')}")
    print("=" * 100)

    # Import after logging is configured
    from agents.company_profile.tools.internal_search import internal_search_tool

    # Get the tool
    tool = internal_search_tool()

    if not tool:
        print("\n❌ ERROR: internal_search_tool failed to initialize")
        return

    print(f"\nTool initialized:")
    print(f"  Has qdrant_client: {tool.qdrant_client is not None}")
    print(f"  Has llm: {tool.llm is not None}")
    print(f"  Has embeddings: {tool.embeddings is not None}")
    print(f"  Collection: {tool.vector_collection}")
    print("=" * 100)

    # The problematic query
    query = "profile SanMar and opportunities to help support their growth"

    print(f"\n\nRUNNING QUERY:")
    print(f"  '{query}'")
    print("=" * 100)
    print("\nSTARTING SEARCH... (this may take 10-30 seconds)\n")
    print("-" * 100)

    try:
        result = await tool._arun(query, effort="low")

        print("-" * 100)
        print("\n" + "=" * 100)
        print("FINAL RESULT:")
        print("=" * 100)
        print(result)
        print("=" * 100)

        # Parse the result
        if "Relationship status: Existing client" in result:
            print("\n🚨 FALSE POSITIVE CONFIRMED!")
            print("   SanMar incorrectly identified as existing client")
            print("\n   Check the logs above for:")
            print("   - 'relationship_evidence' flag value")
            print("   - 'CULPRIT FOUND' warning (which doc triggered it)")
            print("   - 'company_with_signals' value")
            print("   - Which documents were retrieved")
        elif "Relationship status: No prior engagement" in result:
            print("\n✅ CORRECT: No prior engagement")
            print("   (False positive may have been fixed)")
        else:
            print("\n⚠️  UNEXPECTED: No clear relationship status")

    except Exception as e:
        print(f"\n❌ ERROR during search: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
