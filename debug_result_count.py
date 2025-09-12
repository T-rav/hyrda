#!/usr/bin/env python3
"""
Debug script to check result counts for Apple query
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

async def check_result_count():
    """Check how many results are returned for Apple query"""
    
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
    
    print("📊 Result Count Analysis for Apple Query")
    print("=" * 50)
    print(f"RAG Settings:")
    print(f"  - Max results: {settings.rag.max_results}")
    print(f"  - Similarity threshold: {settings.rag.similarity_threshold}")
    print(f"  - Results similarity threshold: {settings.rag.results_similarity_threshold}")
    print(f"  - Hybrid search enabled: {settings.rag.enable_hybrid_search}")
    print(f"  - Entity content boost: {settings.rag.entity_content_boost}")
    print(f"  - Entity title boost: {settings.rag.entity_title_boost}")
    print()
    
    # Initialize services
    vector_store = create_vector_store(settings.vector)
    await vector_store.initialize()
    
    embedding_service = create_embedding_provider(settings.embedding, settings.llm)
    
    query = "has 8th light worked with apple?"
    print(f"🔍 Query: '{query}'")
    print()
    
    # Test with different configurations
    test_configs = [
        {"hybrid": False, "name": "Pure Vector Search"},
        {"hybrid": True, "name": "With Entity Boosting"}
    ]
    
    for config in test_configs:
        print(f"🎯 Testing: {config['name']}")
        print("-" * 30)
        
        # Create retrieval service with specific config
        settings.rag.enable_hybrid_search = config["hybrid"]
        retrieval_service = RetrievalService(settings)
        
        # Get results
        results = await retrieval_service.retrieve_context(
            query, vector_store, embedding_service
        )
        
        print(f"📄 Total results returned: {len(results)}")
        
        # Break down by document type
        apple_count = 0
        other_count = 0
        unique_docs = set()
        
        for i, result in enumerate(results):
            file_name = result.get("metadata", {}).get("file_name", "Unknown")
            similarity = result.get("similarity", 0)
            original_sim = result.get("_original_similarity", similarity)
            entity_boost = result.get("_entity_boost", 0)
            
            unique_docs.add(file_name)
            
            if "apple" in file_name.lower():
                apple_count += 1
                status = "🍎"
            else:
                other_count += 1
                status = "📄"
            
            boost_info = ""
            if entity_boost > 0:
                boost_info = f" (boost: +{entity_boost:.2f})"
            
            print(f"  {status} {i+1}. {file_name[:60]}...")
            print(f"      Similarity: {similarity:.3f}{boost_info}")
        
        print()
        print(f"📈 Summary:")
        print(f"  - Apple documents: {apple_count}")
        print(f"  - Other documents: {other_count}")
        print(f"  - Unique documents: {len(unique_docs)}")
        print()
    
    # Also test with raw vector search (no thresholds)
    print("🔍 Raw Vector Search (No Thresholds)")
    print("-" * 30)
    
    query_embedding = await embedding_service.get_embedding(query)
    raw_results = await vector_store.search(
        query_embedding=query_embedding,
        limit=50,  # Higher limit
        similarity_threshold=0.0,  # No threshold
    )
    
    apple_in_raw = 0
    for result in raw_results:
        file_name = result.get("metadata", {}).get("file_name", "Unknown")
        if "apple" in file_name.lower():
            apple_in_raw += 1
    
    print(f"📄 Raw results (top 50): {len(raw_results)}")
    print(f"🍎 Apple documents in raw results: {apple_in_raw}")
    
    # Show score distribution
    if raw_results:
        scores = [r.get("similarity", 0) for r in raw_results]
        print(f"📊 Score range: {min(scores):.3f} - {max(scores):.3f}")
        print(f"📊 Threshold filters:")
        print(f"  - Above {settings.rag.similarity_threshold}: {len([s for s in scores if s >= settings.rag.similarity_threshold])}")
        print(f"  - Above {settings.rag.results_similarity_threshold}: {len([s for s in scores if s >= settings.rag.results_similarity_threshold])}")

if __name__ == "__main__":
    asyncio.run(check_result_count())