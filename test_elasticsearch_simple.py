#!/usr/bin/env python3
"""
Simple test to debug Elasticsearch search issues
"""
import asyncio
import os
import sys
os.chdir('bot')
sys.path.insert(0, '.')

from dotenv import load_dotenv
load_dotenv('../.env')

from config.settings import Settings
from services.vector_service import create_vector_store

async def test_elasticsearch():
    """Test basic Elasticsearch functionality"""
    settings = Settings()
    
    print(f"🔍 Testing Elasticsearch...")
    print(f"Provider: {settings.vector.provider}")
    print(f"URL: {settings.vector.url}")
    print(f"Index: {settings.vector.collection_name}")
    
    try:
        # Create vector store
        vector_store = create_vector_store(settings.vector)
        await vector_store.initialize()
        print("✅ Vector store initialized")
        
        # Test 1: Check if index exists and has documents
        stats = await vector_store.get_stats()
        print(f"📊 Index stats: {stats}")
        
        if stats['document_count'] == 0:
            print("❌ Index is empty! No documents to search.")
            return
        
        # Test 2: Simple match_all query to see if we can get any documents
        print(f"\n1️⃣ Testing basic match_all query...")
        if hasattr(vector_store, 'client'):
            response = await vector_store.client.search(
                index=vector_store.index_name,
                body={
                    "query": {"match_all": {}},
                    "size": 3,
                    "_source": ["content", "metadata"]
                }
            )
            print(f"Match all results: {response['hits']['total']['value']} documents")
            for i, hit in enumerate(response['hits']['hits'][:2]):
                content = hit["_source"].get("content", "")[:100]
                metadata = hit["_source"].get("metadata", {})
                file_name = metadata.get("file_name", "Unknown")
                print(f"  Doc {i+1}: {file_name} - {content}...")
        
        # Test 3: Simple term search for "apple"
        print(f"\n2️⃣ Testing simple term search for 'apple'...")
        if hasattr(vector_store, 'client'):
            response = await vector_store.client.search(
                index=vector_store.index_name,
                body={
                    "query": {
                        "multi_match": {
                            "query": "apple",
                            "fields": ["content", "metadata.file_name"]
                        }
                    },
                    "size": 5,
                    "_source": ["content", "metadata"]
                }
            )
            print(f"Apple search results: {response['hits']['total']['value']} documents")
            for i, hit in enumerate(response['hits']['hits']):
                content = hit["_source"].get("content", "")[:100]
                metadata = hit["_source"].get("metadata", {})
                file_name = metadata.get("file_name", "Unknown")
                score = hit["_score"]
                print(f"  Result {i+1}: {file_name} (score: {score:.2f}) - {content}...")
                
        # Test 4: Test the actual method we're using
        print(f"\n3️⃣ Testing our actual search method...")
        # Create dummy embedding
        dummy_embedding = [0.0] * 3072
        results = await vector_store.search(
            query_embedding=dummy_embedding,
            query_text="apple",
            limit=5,
            similarity_threshold=0.0
        )
        print(f"Our search method results: {len(results)} documents")
        for i, result in enumerate(results):
            print(f"  Result {i+1}: similarity={result['similarity']:.3f} - {result['content'][:100]}...")
        
        await vector_store.close()
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_elasticsearch())