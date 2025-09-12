#!/usr/bin/env python3
"""
Compare Apple document retrieval for different queries
"""

import asyncio
import sys
import os

# Add bot directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "bot"))

from config.settings import Settings
from services.vector_service import create_vector_store
from services.embedding_service import create_embedding_provider

async def compare_apple_queries():
    """Compare Apple document retrieval for different queries"""
    
    # Load environment 
    env_file = os.path.join(os.path.dirname(__file__), '.env')
    if os.path.exists(env_file):
        with open(env_file, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    value = value.split('#')[0].strip()
                    os.environ.setdefault(key.strip(), value)
    
    settings = Settings()
    
    # Initialize services
    vector_store = create_vector_store(settings.vector)
    await vector_store.initialize()
    
    embedding_service = create_embedding_provider(settings.embedding, settings.llm)
    
    queries = [
        "apple",
        "apple company project",
        "has 8th light worked with apple?",
        "8th light apple",
    ]
    
    for query in queries:
        print(f"🔍 Query: '{query}'")
        print("=" * 50)
        
        query_embedding = await embedding_service.get_embedding(query)
        
        results = await vector_store.search(
            query_embedding=query_embedding,
            limit=100,
            similarity_threshold=0.0,
        )
        
        # Find Apple documents
        apple_docs = {}
        for result in results:
            file_name = result.get("metadata", {}).get("file_name", "Unknown")
            if "apple" in file_name.lower():
                similarity = result.get("similarity", 0)
                if file_name not in apple_docs:
                    apple_docs[file_name] = []
                apple_docs[file_name].append(similarity)
        
        print(f"📊 Found {len(apple_docs)} unique Apple documents:")
        for doc_name, similarities in apple_docs.items():
            best_sim = max(similarities)
            print(f"   🍎 {doc_name}: {best_sim:.3f} (chunks: {len(similarities)})")
        
        # Show overall ranking
        apple_in_top_10 = 0
        for i, result in enumerate(results[:10]):
            file_name = result.get("metadata", {}).get("file_name", "Unknown")
            similarity = result.get("similarity", 0)
            if "apple" in file_name.lower():
                apple_in_top_10 += 1
                print(f"   🍎 #{i+1}: {file_name} ({similarity:.3f})")
        
        print(f"📈 Apple docs in top 10: {apple_in_top_10}")
        print()

if __name__ == "__main__":
    asyncio.run(compare_apple_queries())