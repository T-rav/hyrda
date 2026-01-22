"""Test script to verify QdrantClient.upsert_with_namespace works correctly.

This script tests the vector upsert functionality that was fixed in youtube_ingest.py
"""

import asyncio
import sys

from services.openai_embeddings import OpenAIEmbeddings
from services.qdrant_client import QdrantClient


async def test_vector_upsert():
    """Test the upsert_with_namespace method with YouTube-like data."""
    print("🧪 Testing vector database upsert...")

    # Initialize services
    print("1️⃣ Initializing Qdrant client...")
    vector_store = QdrantClient()
    await vector_store.initialize()
    print(f"   ✅ Qdrant initialized")

    print("2️⃣ Initializing embedding provider...")
    embedding_provider = OpenAIEmbeddings()
    print(f"   ✅ Embedding provider initialized")

    # Create test data similar to YouTube ingest
    print("3️⃣ Creating test data...")
    test_chunks = [
        "This is a test transcript chunk from a YouTube video about software engineering.",
        "This is the second chunk discussing best practices and methodologies.",
    ]

    test_metadata = [
        {
            "chunk_id": "test_uuid_0",
            "video_id": "test_video_123",
            "video_title": "Test Video Title",
            "channel_id": "test_channel",
            "channel_name": "Test Channel",
            "video_type": "video",
            "chunk_index": 0,
            "chunk_count": 2,
            "video_url": "https://www.youtube.com/watch?v=test",
            "namespace": "youtube",
        },
        {
            "chunk_id": "test_uuid_1",
            "video_id": "test_video_123",
            "video_title": "Test Video Title",
            "channel_id": "test_channel",
            "channel_name": "Test Channel",
            "video_type": "video",
            "chunk_index": 1,
            "chunk_count": 2,
            "video_url": "https://www.youtube.com/watch?v=test",
            "namespace": "youtube",
        },
    ]
    print(f"   ✅ Created {len(test_chunks)} test chunks")

    # Test embedding
    print("4️⃣ Testing embedding generation...")
    try:
        embeddings = await embedding_provider.embed_texts(test_chunks)
        print(f"   ✅ Generated {len(embeddings)} embeddings")
        print(f"   📊 Embedding dimension: {len(embeddings[0])}")
    except Exception as e:
        print(f"   ❌ Embedding failed: {e}")
        return False

    # Test upsert
    print("5️⃣ Testing vector upsert_with_namespace...")
    try:
        await vector_store.upsert_with_namespace(
            texts=test_chunks,
            embeddings=embeddings,
            metadata=test_metadata,
            namespace="youtube",
        )
        print(f"   ✅ Upsert successful!")
    except Exception as e:
        print(f"   ❌ Upsert failed: {e}")
        import traceback

        traceback.print_exc()
        return False

    print("\n✅ All tests passed! Vector upsert is working correctly.")
    return True


if __name__ == "__main__":
    result = asyncio.run(test_vector_upsert())
    sys.exit(0 if result else 1)
