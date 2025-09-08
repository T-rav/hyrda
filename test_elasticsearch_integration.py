#!/usr/bin/env python3
"""
Test script for Elasticsearch vector store integration
"""

import asyncio
import os
import sys
from typing import Any

# Add bot directory to path
sys.path.append(os.path.join(os.path.dirname(__file__), "bot"))

from config.settings import VectorSettings
from services.vector_service import ElasticsearchVectorStore


async def test_elasticsearch_vector_store():
    """Test the Elasticsearch vector store implementation"""

    # Configure for local Elasticsearch
    settings = VectorSettings(
        provider="elasticsearch",
        url="http://localhost:9200",
        collection_name="test_knowledge_base"
    )

    vector_store = ElasticsearchVectorStore(settings)

    try:
        print("🔍 Initializing Elasticsearch connection...")
        await vector_store.initialize()
        print("✅ Successfully connected to Elasticsearch")

        # Sample documents and embeddings (dummy vectors for testing)
        test_texts = [
            "The quick brown fox jumps over the lazy dog.",
            "Elasticsearch is a distributed search and analytics engine.",
            "Vector databases enable semantic search capabilities."
        ]

        # Create dummy embeddings (normally these would come from an embedding model)
        test_embeddings = [
            [0.1] * 1536,  # OpenAI text-embedding-3-small dimension
            [0.2] * 1536,
            [0.3] * 1536
        ]

        test_metadata = [
            {"source": "test1", "category": "animals"},
            {"source": "test2", "category": "technology"},
            {"source": "test3", "category": "technology"}
        ]

        print("📝 Adding test documents...")
        await vector_store.add_documents(
            texts=test_texts,
            embeddings=test_embeddings,
            metadata=test_metadata
        )
        print("✅ Successfully added documents")

        print("🔎 Testing vector search...")
        # Search with a query vector similar to the second document
        query_embedding = [0.25] * 1536  # Similar to second document

        results = await vector_store.search(
            query_embedding=query_embedding,
            limit=3,
            similarity_threshold=0.5
        )

        print(f"📊 Found {len(results)} matching documents:")
        for i, result in enumerate(results, 1):
            print(f"  {i}. Similarity: {result['similarity']:.3f}")
            print(f"     Content: {result['content'][:50]}...")
            print(f"     Metadata: {result['metadata']}")
            print()

        print("🧹 Cleaning up test data...")
        doc_ids = [result['id'] for result in results]
        if doc_ids:
            await vector_store.delete_documents(doc_ids)
            print("✅ Successfully deleted test documents")

        print("✅ All tests completed successfully!")

    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

    finally:
        await vector_store.close()

    return True


if __name__ == "__main__":
    print("🚀 Starting Elasticsearch Vector Store Integration Test")
    print("Make sure Elasticsearch is running on http://localhost:9200")
    print()

    success = asyncio.run(test_elasticsearch_vector_store())

    if success:
        print("\n🎉 Integration test completed successfully!")
        print("Your Elasticsearch vector store is ready to replace Pinecone.")
    else:
        print("\n💥 Integration test failed.")
        print("Please check your Elasticsearch setup and try again.")
        sys.exit(1)
