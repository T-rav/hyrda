#!/usr/bin/env python3
"""Standalone test script for Vail Resorts false positive (no agent imports).

This bypasses the full agent system and directly tests the internal_search_tool
to avoid WeasyPrint and other heavy dependencies.

Usage:
    PYTHONPATH=bot python scripts/test_vail_standalone.py
"""

import asyncio
import os
import sys
from pathlib import Path

# Add bot directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Load environment variables
from dotenv import load_dotenv

load_dotenv()


async def create_internal_search_tool():
    # Direct imports to avoid loading the full agent system
    from langchain_openai import ChatOpenAI, OpenAIEmbeddings
    from langchain_qdrant import QdrantVectorStore
    from qdrant_client import QdrantClient

    # Import only the tool class, not the factory function
    import sys
    import importlib.util

    # Load the module without triggering bot.agents.__init__
    spec = importlib.util.spec_from_file_location(
        "internal_search",
        Path(__file__).parent.parent
        / "bot/agents/company_profile/tools/internal_search.py",
    )
    internal_search = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(internal_search)

    # Get credentials from environment
    llm_api_key = os.getenv("LLM_API_KEY")
    llm_model = os.getenv("LLM_MODEL", "gpt-4o-mini")

    embedding_api_key = os.getenv("EMBEDDING_API_KEY", llm_api_key)
    embedding_model = os.getenv("EMBEDDING_MODEL", "text-embedding-3-large")

    vector_host = os.getenv("VECTOR_HOST", "localhost")
    vector_port = os.getenv("VECTOR_PORT", "6333")
    vector_api_key = os.getenv("VECTOR_API_KEY")
    vector_collection = os.getenv(
        "VECTOR_COLLECTION_NAME", "insightmesh-knowledge-base"
    )

    # Initialize components
    llm = ChatOpenAI(model=llm_model, api_key=llm_api_key, temperature=0)

    embeddings = OpenAIEmbeddings(model=embedding_model, api_key=embedding_api_key)

    # Initialize Qdrant client
    if vector_api_key:
        client = QdrantClient(
            host=vector_host, port=int(vector_port), api_key=vector_api_key, https=False
        )
    else:
        client = QdrantClient(host=vector_host, port=int(vector_port))

    vector_store = QdrantVectorStore(
        client=client,
        collection_name=vector_collection,
        embedding=embeddings,
        content_payload_key="text",
        metadata_payload_key="metadata",
    )

    # Create tool instance
    tool = internal_search.InternalSearchTool(
        vector_store=vector_store, llm=llm, embeddings=embeddings
    )

    return tool


async def test_vail_resorts():
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
        print("Initializing internal search tool...")
        tool = await create_internal_search_tool()
        print("✓ Tool initialized successfully")
        print()

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
            return False
        elif "Relationship status: No prior engagement" in result:
            print("✅ CORRECT: No false positive")
            print("   The tool correctly identifies no relationship with Vail Resorts.")
            return True
        else:
            print("⚠️  WARNING: No clear relationship status found in result")
            return False

    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback

        traceback.print_exc()
        return False


async def test_simple_query():
    print("\n" + "=" * 80)
    print("SIMPLE VAIL RESORTS TEST")
    print("=" * 80)

    try:
        tool = await create_internal_search_tool()
        result = await tool._arun("profile Vail Resorts", effort="medium")

        print("\nResult:")
        print("-" * 80)
        print(result)
        print("-" * 80)

        if "Relationship status: No prior engagement" in result:
            print("\n✅ Simple query test passed")
            return True
        elif "Relationship status: Existing client" in result:
            print("\n❌ Simple query has false positive")
            return False
        else:
            print("\n⚠️  Simple query returned unclear status")
            return False

    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        return False


async def main():
    print("\n🔍 Starting Vail Resorts False Positive Tests (Standalone)\n")

    # Test 1: Simple query
    test1_passed = await test_simple_query()

    # Test 2: Full query with Aspenware context
    test2_passed = await test_vail_resorts()

    # Summary
    print("\n" + "=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)
    print(f"Test 1 (Simple Query):    {'✅ PASS' if test1_passed else '❌ FAIL'}")
    print(f"Test 2 (Full Query):      {'✅ PASS' if test2_passed else '❌ FAIL'}")
    print("=" * 80)

    if test1_passed and test2_passed:
        print("\n✅ All tests passed! No false positive detected.")
        return 0
    else:
        print("\n❌ Tests failed. False positive bug present.")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
