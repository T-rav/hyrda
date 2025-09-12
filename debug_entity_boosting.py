#!/usr/bin/env python3
"""
Debug script to test entity boosting effectiveness
"""

import asyncio
import sys
import os

# Add bot directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "bot"))

from config.settings import Settings
from services.vector_service import create_vector_store
from services.embedding_service import create_embedding_provider
from services.retrieval_service import RetrievalService

async def test_entity_boosting():
    """Test entity boosting with Apple query"""
    
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
    
    print("🎯 Testing Entity Boosting for Apple Query")
    print("=" * 50)
    
    # Force hybrid search to test entity boosting
    settings.rag.enable_hybrid_search = True
    
    # Initialize services
    vector_store = create_vector_store(settings.vector)
    await vector_store.initialize()
    
    embedding_service = create_embedding_provider(settings.embedding, settings.llm)
    retrieval_service = RetrievalService(settings)
    
    # Test query
    query = "has 8th light worked with apple?"
    print(f"Query: '{query}'")
    print()
    
    # Get results with entity boosting
    results = await retrieval_service.retrieve_context(
        query, vector_store, embedding_service
    )
    
    print(f"📊 Retrieved {len(results)} results with entity boosting:")
    print()
    
    # Show all results with Apple documents highlighted
    apple_count = 0
    for i, result in enumerate(results):
        file_name = result.get("metadata", {}).get("file_name", "Unknown")
        similarity = result.get("similarity", 0)
        original_sim = result.get("_original_similarity", similarity)
        entity_boost = result.get("_entity_boost", 0)
        matching_entities = result.get("_matching_entities", 0)
        
        is_apple = "apple" in file_name.lower()
        if is_apple:
            apple_count += 1
            status = "🍎"
        else:
            status = "📄"
        
        boost_info = f"(boost: +{entity_boost:.2f}, entities: {matching_entities})" if entity_boost > 0 else ""
        
        print(f"{status} {i+1:2}. {file_name}")
        print(f"      Similarity: {similarity:.3f} (original: {original_sim:.3f}) {boost_info}")
        
        # Show a preview of content for Apple documents
        if is_apple:
            content = result.get("content", "")
            preview = content.replace('\n', ' ')[:150] + "..." if len(content) > 150 else content
            print(f"      Content: {preview}")
        print()
    
    print(f"🍎 Apple documents found: {apple_count}/{len(results)}")
    
    # Now test without entity boosting for comparison
    print("\n" + "="*60)
    print("🔍 Testing WITHOUT Entity Boosting (Pure Vector Search)")
    print("="*60)
    
    settings.rag.enable_hybrid_search = False
    retrieval_service_pure = RetrievalService(settings)
    
    pure_results = await retrieval_service_pure.retrieve_context(
        query, vector_store, embedding_service
    )
    
    print(f"📊 Pure vector search returned {len(pure_results)} results:")
    print()
    
    apple_count_pure = 0
    for i, result in enumerate(pure_results):
        file_name = result.get("metadata", {}).get("file_name", "Unknown")
        similarity = result.get("similarity", 0)
        
        is_apple = "apple" in file_name.lower()
        if is_apple:
            apple_count_pure += 1
            status = "🍎"
        else:
            status = "📄"
        
        print(f"{status} {i+1:2}. {file_name} (sim: {similarity:.3f})")
    
    print()
    print(f"🍎 Apple documents found without boosting: {apple_count_pure}/{len(pure_results)}")
    
    print("\n📈 COMPARISON:")
    print(f"   - With entity boosting: {apple_count} Apple documents")
    print(f"   - Without entity boosting: {apple_count_pure} Apple documents")
    print(f"   - Improvement: {apple_count - apple_count_pure} additional Apple documents")

if __name__ == "__main__":
    asyncio.run(test_entity_boosting())