#!/usr/bin/env python3
"""
Debug script to test Elasticsearch search functionality
"""
import asyncio
import os
import sys
# Change to bot directory so settings can find ../env
os.chdir('bot')
sys.path.insert(0, '.')

from config.settings import Settings
from services.vector_service import create_vector_store
from services.embedding_service import create_embedding_provider

async def debug_elasticsearch():
    """Debug Elasticsearch search issues"""
    # Load .env file explicitly
    from dotenv import load_dotenv
    env_path = os.path.join(os.path.dirname(os.getcwd()), '.env')
    print(f"Loading .env from: {env_path}")
    load_dotenv(env_path)

    # Check what we loaded
    print(f"VECTOR_PROVIDER from env: {os.getenv('VECTOR_PROVIDER')}")

    # Load settings
    settings = Settings()

    print(f"🔍 Debugging Elasticsearch search...")
    print(f"Vector provider: {settings.vector.provider}")
    print(f"Vector URL: {settings.vector.url}")
    print(f"Index name: {settings.vector.collection_name}")
    print(f"Hybrid search enabled: {settings.rag.enable_hybrid_search}")

    try:
        # Create vector store
        vector_store = create_vector_store(settings.vector)
        embedding_provider = create_embedding_provider(settings.embedding, settings.llm)

        # Initialize
        await vector_store.initialize()
        print("✅ Vector store initialized")

        # Get index stats
        stats = await vector_store.get_stats()
        print(f"📊 Index stats: {stats}")

        # Test query
        test_query = "has 8th light worked with apple"
        print(f"\n🔍 Testing query: '{test_query}'")

        # Get embedding
        query_embedding = await embedding_provider.get_embedding(test_query)
        print(f"✅ Query embedding generated: {len(query_embedding)} dimensions")

        # Test 1: Pure vector search (no text)
        print(f"\n1️⃣ Testing pure vector search...")
        results1 = await vector_store.search(
            query_embedding=query_embedding,
            limit=10,
            similarity_threshold=0.1,  # Very low threshold
            query_text=""  # No text query
        )
        print(f"Pure vector results: {len(results1)} hits")
        if results1:
            for i, result in enumerate(results1[:3]):
                print(f"  - Result {i+1}: similarity={result['similarity']:.3f}")
                print(f"    Content preview: {result['content'][:100]}...")
                print(f"    Search type: {result.get('search_type', 'unknown')}")

        # Test 2: BM25 + vector boost
        print(f"\n2️⃣ Testing BM25 + vector boost...")
        results2 = await vector_store.search(
            query_embedding=query_embedding,
            limit=10,
            similarity_threshold=0.1,  # Very low threshold
            query_text=test_query  # With text query
        )
        print(f"BM25 + vector results: {len(results2)} hits")
        if results2:
            for i, result in enumerate(results2[:3]):
                print(f"  - Result {i+1}: similarity={result['similarity']:.3f}")
                print(f"    Content preview: {result['content'][:100]}...")
                print(f"    Search type: {result.get('search_type', 'unknown')}")

        # Test 3: Simple BM25 only
        print(f"\n3️⃣ Testing simple BM25...")
        try:
            results3 = await vector_store.bm25_search(
                query=test_query,
                limit=10,
                similarity_threshold=0.0
            )
            print(f"Simple BM25 results: {len(results3)} hits")
            if results3:
                for i, result in enumerate(results3[:3]):
                    print(f"  - Result {i+1}: similarity={result['similarity']:.3f}")
                    print(f"    Content preview: {result['content'][:100]}...")
        except Exception as e:
            print(f"BM25 search failed: {e}")

        # Test 4: Match all documents (just to see what's in the index)
        print(f"\n4️⃣ Testing match_all to see index contents...")
        try:
            if hasattr(vector_store, 'client') and vector_store.client:
                response = await vector_store.client.search(
                    index=vector_store.index_name,
                    body={
                        "query": {"match_all": {}},
                        "size": 5,
                        "_source": ["content", "metadata"]
                    }
                )
                hits = response["hits"]["hits"]
                print(f"Total documents in index: {response['hits']['total']['value']}")
                print("Sample documents:")
                for i, hit in enumerate(hits):
                    content = hit["_source"].get("content", "")
                    metadata = hit["_source"].get("metadata", {})
                    print(f"  - Doc {i+1}: {content[:100]}...")
                    print(f"    Metadata: {list(metadata.keys())}")
        except Exception as e:
            print(f"Match all failed: {e}")

        await vector_store.close()

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(debug_elasticsearch())
