#!/usr/bin/env python3
"""
Debug script to investigate IDEO vs viedo vector search issue
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
from services.embedding_service import create_embedding_provider
from services.vector_service import create_vector_store


async def debug_vector_search():
    """Debug the vector search issue with IDEO vs viedo"""

    # Load settings
    settings = Settings()

    if not settings.vector.enabled:
        print("❌ Vector search is not enabled in settings")
        return

    print(f"🔧 Vector Provider: {settings.vector.provider}")
    print(f"🔧 Collection: {settings.vector.collection_name}")
    print(f"🔧 Similarity Threshold: {settings.rag.similarity_threshold}")
    print(f"🔧 Embedding Model: {settings.embedding.model}")
    print()

    # Initialize services
    vector_store = create_vector_store(settings.vector)
    embedding_provider = create_embedding_provider(settings.embedding, settings.llm)

    await vector_store.initialize()

    try:
        # Test queries
        queries = [
            "has 8th light worked with ideo?",
            "ideo",
            "IDEO",
            "viedo",
        ]

        for query in queries:
            print(f"🔍 Searching for: '{query}'")
            print("-" * 50)

            # Get embedding for query
            query_embedding = await embedding_provider.get_embedding(query)

            # Search with high limit and low threshold to see all potential matches
            results = await vector_store.search(
                query_embedding=query_embedding,
                limit=20,  # Get more results
                similarity_threshold=0.1,  # Very low threshold to see everything
            )

            if not results:
                print("   No results found")
            else:
                print(f"   Found {len(results)} results:")
                for i, result in enumerate(results[:10]):  # Show top 10
                    similarity = result.get("similarity", 0)
                    content_preview = result.get("content", "")[:100].replace("\n", " ")
                    metadata = result.get("metadata", {})

                    file_name = metadata.get("file_name", "Unknown")
                    folder_path = metadata.get("folder_path", "")

                    print(f"   {i+1:2d}. Similarity: {similarity:.3f}")
                    print(f"       File: {file_name}")
                    if folder_path:
                        print(f"       Path: {folder_path}")
                    print(f"       Content: {content_preview}...")
                    print()

            print()

        # Test embedding similarity between specific terms
        print("🧪 Testing embedding similarity between terms:")
        print("-" * 50)

        terms = ["ideo", "IDEO", "viedo", "video", "ideas"]
        embeddings = {}

        for term in terms:
            embeddings[term] = await embedding_provider.get_embedding(term)

        def cosine_similarity(a, b):
            """Calculate cosine similarity between two vectors"""
            import math
            dot_product = sum(x * y for x, y in zip(a, b))
            norm_a = math.sqrt(sum(x * x for x in a))
            norm_b = math.sqrt(sum(x * x for x in b))
            return dot_product / (norm_a * norm_b)

        # Compare similarities
        for i, term1 in enumerate(terms):
            for term2 in terms[i+1:]:
                similarity = cosine_similarity(embeddings[term1], embeddings[term2])
                print(f"'{term1}' vs '{term2}': {similarity:.4f}")

        print()

        # Search for documents containing specific terms in metadata or content
        print("🔎 Searching for documents containing 'IDEO' in title/name:")
        print("-" * 50)

        # This is a manual search through the database - we'll need to implement this
        # For now, let's search with a very broad query
        broad_query_embedding = await embedding_provider.get_embedding("IDEO company design")
        broad_results = await vector_store.search(
            query_embedding=broad_query_embedding,
            limit=50,
            similarity_threshold=0.05,  # Very low threshold
        )

        ideo_docs = []
        viedo_docs = []

        for result in broad_results:
            metadata = result.get("metadata", {})
            content = result.get("content", "")
            file_name = metadata.get("file_name", "")

            # Check for IDEO in various places
            text_to_check = f"{file_name} {content}".lower()

            if "ideo" in text_to_check and "viedo" not in text_to_check:
                ideo_docs.append(result)
            elif "viedo" in text_to_check:
                viedo_docs.append(result)

        print(f"Documents mentioning 'IDEO' (excluding viedo): {len(ideo_docs)}")
        for doc in ideo_docs[:5]:  # Show first 5
            metadata = doc.get("metadata", {})
            content_preview = doc.get("content", "")[:100].replace("\n", " ")
            print(f"  - {metadata.get('file_name', 'Unknown')}: {content_preview}...")

        print(f"\nDocuments mentioning 'viedo': {len(viedo_docs)}")
        for doc in viedo_docs[:5]:  # Show first 5
            metadata = doc.get("metadata", {})
            content_preview = doc.get("content", "")[:100].replace("\n", " ")
            print(f"  - {metadata.get('file_name', 'Unknown')}: {content_preview}...")

    except Exception as e:
        print(f"❌ Error during debug: {e}")
        import traceback
        traceback.print_exc()

    finally:
        await vector_store.close()


if __name__ == "__main__":
    asyncio.run(debug_vector_search())
