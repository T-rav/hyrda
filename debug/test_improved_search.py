#!/usr/bin/env python3
"""
Test script for the improved hybrid search functionality
"""

import asyncio
import os
import sys
from typing import Any

# Load environment variables from .env file
from dotenv import load_dotenv
load_dotenv()

# Add bot directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'bot'))

from config.settings import Settings
from services.rag_service import RAGService


async def test_improved_search():
    """Test the improved hybrid search with IDEO query"""

    # Load settings
    settings = Settings()

    if not settings.vector.enabled:
        print("❌ Vector search is not enabled in settings")
        return

    print(f"🔧 Testing improved hybrid search")
    print(f"🔧 Similarity Threshold: {settings.rag.similarity_threshold}")
    print(f"🔧 Max Chunks: {settings.rag.max_chunks}")
    print()

    # Initialize RAG service
    rag_service = RAGService(settings)
    await rag_service.initialize()

    try:
        # Test queries with entities that actually exist in the corpus
        test_queries = [
            "has 8th light worked with Apple?",
            "Apple partnership",
            "work with Google",
            "Microsoft integration"
        ]

        for test_query in test_queries:
            print(f"🔍 Testing query: '{test_query}'")
            print("-" * 60)

            # Use the improved retrieve_context method with debug info
            print(f"   Current similarity threshold: {settings.rag.similarity_threshold}")
            print(f"   Candidate threshold: 0.05")
            print(f"   Candidates retrieved: 100")
            print()

            results = await rag_service.retrieve_context(test_query)

            if not results:
                print("   No results found")
            else:
                print(f"   Found {len(results)} results with hybrid search:")
                for i, result in enumerate(results):
                    similarity = result.get("similarity", 0)
                    content_preview = result.get("content", "")[:100].replace("\n", " ")
                    metadata = result.get("metadata", {})

                    file_name = metadata.get("file_name", "Unknown")
                    folder_path = metadata.get("folder_path", "")

                    print(f"   {i+1}. Similarity: {similarity:.3f}")
                    print(f"      File: {file_name}")
                    if folder_path:
                        print(f"      Path: {folder_path}")

                    # Show boost info if available
                    boost_info = result.get("boost_info")
                    if boost_info:
                        original_sim = boost_info.get("original_similarity", similarity)
                        boost_factor = boost_info.get("boost_factor", 1.0)
                        matches = boost_info.get("matches", [])
                        print(f"      🚀 BOOSTED: {original_sim:.3f} → {similarity:.3f} (×{boost_factor:.2f}) - {matches}")

                    print(f"      Content: {content_preview}...")
                    print()

            print()

            # Check if we got entity documents
            entity_name = ""
            if "apple" in test_query.lower():
                entity_name = "apple"
            elif "google" in test_query.lower():
                entity_name = "google"
            elif "microsoft" in test_query.lower():
                entity_name = "microsoft"

            if entity_name:
                entity_count = 0
                total_count = len(results)

                for result in results:
                    metadata = result.get("metadata", {})
                    content = result.get("content", "")
                    file_name = metadata.get("file_name", "")

                    text_to_check = f"{file_name} {content}".lower()
                    if entity_name in text_to_check:
                        entity_count += 1

                print(f"📊 Results summary for '{entity_name}':")
                print(f"   - {entity_name.capitalize()}-related documents: {entity_count}/{total_count}")
                print(f"   - Success rate: {(entity_count/total_count*100):.1f}%" if total_count > 0 else "   - No results to analyze")

                if entity_count > 0:
                    print(f"✅ SUCCESS: {entity_name.capitalize()} documents are appearing in search results!")
                else:
                    print(f"❌ ISSUE: Still no {entity_name.capitalize()} documents in top results")

            print("\n" + "="*80 + "\n")

    except Exception as e:
        print(f"❌ Error during test: {e}")
        import traceback
        traceback.print_exc()

    finally:
        await rag_service.close()


if __name__ == "__main__":
    asyncio.run(test_improved_search())
