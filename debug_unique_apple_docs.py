#!/usr/bin/env python3
"""
Debug script to find all unique Apple documents in the index
"""

import asyncio
import sys
import os

# Add bot directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "bot"))

from config.settings import Settings
from services.vector_service import create_vector_store
from services.embedding_service import create_embedding_provider

async def find_unique_apple_docs():
    """Find all unique Apple documents"""
    
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
    
    print("🔍 Finding All Unique Apple Documents")
    print("=" * 50)
    
    # Initialize services
    vector_store = create_vector_store(settings.vector)
    await vector_store.initialize()
    
    embedding_service = create_embedding_provider(settings.embedding, settings.llm)
    
    # Search with a very broad Apple-related query
    apple_query = await embedding_service.get_embedding("apple company project")
    
    # Get lots of results with no threshold
    results = await vector_store.search(
        query_embedding=apple_query,
        limit=200,  # Large limit
        similarity_threshold=0.0,  # No threshold
    )
    
    # Find all unique Apple documents
    apple_docs = {}
    for result in results:
        file_name = result.get("metadata", {}).get("file_name", "Unknown")
        if "apple" in file_name.lower():
            if file_name not in apple_docs:
                apple_docs[file_name] = []
            apple_docs[file_name].append({
                "similarity": result.get("similarity", 0),
                "content_preview": result.get("content", "")[:100] + "..."
            })
    
    print(f"📊 Found {len(apple_docs)} unique Apple documents:")
    print()
    
    for i, (doc_name, chunks) in enumerate(sorted(apple_docs.items())):
        print(f"{i+1}. **{doc_name}**")
        print(f"   - Chunks: {len(chunks)}")
        print(f"   - Best similarity: {max(chunk['similarity'] for chunk in chunks):.3f}")
        print(f"   - Sample content: {chunks[0]['content_preview']}")
        print()
    
    print("🎯 Test Query: 'has 8th light worked with apple?'")
    print("-" * 50)
    
    # Now test the specific query
    test_query = await embedding_service.get_embedding("has 8th light worked with apple?")
    test_results = await vector_store.search(
        query_embedding=test_query,
        limit=15,
        similarity_threshold=0.0,
    )
    
    print(f"Query returned {len(test_results)} results:")
    print()
    
    # Show unique documents from test query
    seen_docs = set()
    unique_count = 0
    for i, result in enumerate(test_results):
        file_name = result.get("metadata", {}).get("file_name", "Unknown")
        similarity = result.get("similarity", 0)
        is_apple = "apple" in file_name.lower()
        
        if file_name not in seen_docs:
            seen_docs.add(file_name)
            unique_count += 1
            status = "🍎" if is_apple else "📄"
            print(f"{status} {unique_count:2}. {file_name} (sim: {similarity:.3f})")
        else:
            # Show duplicate chunks
            status = "🍎" if is_apple else "📄" 
            print(f"{status}     └─ Additional chunk (sim: {similarity:.3f})")
    
    print()
    print(f"📈 Summary: {len(seen_docs)} unique documents, {len(test_results)} total chunks")

if __name__ == "__main__":
    asyncio.run(find_unique_apple_docs())