#!/usr/bin/env python3
"""Test Apple search to see what documents are returned vs what Slack gets"""

import asyncio
import sys
import os

# Load environment variables from .env file
from dotenv import load_dotenv
load_dotenv()

# Add bot directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'bot'))

from services.rag_service import RAGService
from config.settings import Settings

async def test_apple_search():
    print("🔍 Testing Apple search...")

    # Initialize settings
    settings = Settings()

    # Initialize RAG service (it creates its own components internally)
    rag_service = RAGService(settings)

    # Initialize the RAG service
    await rag_service.initialize()

    try:
        # Test the same query that Slack gets
        query = "has 8th light worked with apple?"
        print(f"Query: '{query}'")
        print()

        results = await rag_service.retrieve_context(query)

        print(f"📊 RESULTS: Found {len(results)} documents")
        print(f"⚙️  Settings: max_chunks={settings.rag.max_chunks}, threshold={settings.rag.similarity_threshold}")
        print()

        for i, result in enumerate(results, 1):
            metadata = result.get("metadata", {})
            file_name = metadata.get("file_name", "unknown")
            folder_path = metadata.get("folder_path", "")
            similarity = result.get("similarity", 0)
            content_preview = result.get("content", "")[:150]

            print(f"{i}. {file_name}")
            print(f"   📁 Path: {folder_path}")
            print(f"   📈 Similarity: {similarity:.3f} ({similarity*100:.1f}%)")
            print(f"   📄 Content: {content_preview}...")
            print()

        print("=" * 60)
        print("EXPECTED: Should see 'Apple - Frontend Engineering' document")
        print(f"ACTUAL: {len(results)} results returned")

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_apple_search())
