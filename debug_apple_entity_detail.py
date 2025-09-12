#!/usr/bin/env python3
"""
Debug script to examine why other Apple documents aren't getting entity boosting
"""

import asyncio
import sys
import os

# Add bot directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "bot"))

from config.settings import Settings
from services.vector_service import create_vector_store
from services.embedding_service import create_embedding_provider

async def debug_apple_entity_detail():
    """Debug Apple document entity boosting in detail"""
    
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
    
    print("🔍 Debugging Apple Document Entity Boosting")
    print("=" * 50)
    
    # Initialize services
    vector_store = create_vector_store(settings.vector)
    await vector_store.initialize()
    
    embedding_service = create_embedding_provider(settings.embedding, settings.llm)
    
    # Get query embedding
    query = "has 8th light worked with apple?"
    query_embedding = await embedding_service.get_embedding(query)
    
    # Search with very broad criteria to see ALL Apple documents
    print("🔍 Searching with broad criteria to find all Apple documents...")
    
    broad_results = await vector_store.search(
        query_embedding=query_embedding,
        limit=100,  # High limit
        similarity_threshold=0.0,  # No threshold
    )
    
    # Find all Apple documents and analyze their scores
    apple_docs = {}
    other_docs = []
    
    for result in broad_results:
        file_name = result.get("metadata", {}).get("file_name", "Unknown")
        similarity = result.get("similarity", 0)
        
        if "apple" in file_name.lower():
            if file_name not in apple_docs:
                apple_docs[file_name] = []
            apple_docs[file_name].append({
                'similarity': similarity,
                'content': result.get("content", "")[:200]
            })
        elif similarity > 0.3:  # Only track high-scoring non-Apple docs
            other_docs.append((file_name, similarity))
    
    print(f"📊 Found {len(apple_docs)} unique Apple documents:")
    print()
    
    for doc_name, chunks in apple_docs.items():
        best_similarity = max(chunk['similarity'] for chunk in chunks)
        print(f"📄 {doc_name}")
        print(f"   - Chunks: {len(chunks)}")
        print(f"   - Best similarity: {best_similarity:.3f}")
        scores_list = [f'{c["similarity"]:.3f}' for c in chunks[:5]]
        print(f"   - All scores: {scores_list}")
        
        # Check if this document would make it into entity boosting range
        threshold = max(0.05, settings.rag.similarity_threshold - 0.25)
        would_qualify = best_similarity >= threshold
        print(f"   - Would qualify for entity boosting (>={threshold:.2f}): {'✅' if would_qualify else '❌'}")
        
        # Show content sample
        print(f"   - Sample content: {chunks[0]['content']}...")
        print()
    
    # Show top non-Apple results for comparison
    print("🔍 Top scoring non-Apple documents for comparison:")
    other_docs.sort(key=lambda x: x[1], reverse=True)
    for doc_name, similarity in other_docs[:5]:
        print(f"   - {doc_name}: {similarity:.3f}")
    
    print()
    print("💡 Analysis:")
    
    # Calculate what threshold would capture all Apple docs
    all_apple_scores = []
    for chunks in apple_docs.values():
        all_apple_scores.extend([c['similarity'] for c in chunks])
    
    if all_apple_scores:
        min_apple_score = min(all_apple_scores)
        current_threshold = max(0.05, settings.rag.similarity_threshold - 0.25)
        
        print(f"   - Current entity boosting threshold: {current_threshold:.3f}")
        print(f"   - Minimum Apple document score: {min_apple_score:.3f}")
        print(f"   - Recommended threshold to capture ALL Apple docs: {min_apple_score - 0.01:.3f}")
        
        if min_apple_score < current_threshold:
            print(f"   ⚠️  Some Apple documents are being filtered out before entity boosting!")
            print(f"   💡 Consider lowering threshold to {min_apple_score - 0.02:.3f}")
        else:
            print(f"   ✅ All Apple documents should qualify for entity boosting")

if __name__ == "__main__":
    asyncio.run(debug_apple_entity_detail())