#!/usr/bin/env python3
"""
Quick test to see exact similarity scores for Apple documents with entity boosting
"""

import asyncio
import logging
import sys
import os

# Add bot directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "bot"))

from config.settings import Settings
from services.vector_service import create_vector_store
from services.embedding_service import create_embedding_provider
from services.retrieval_service import RetrievalService

# Set up minimal logging
logging.basicConfig(level=logging.INFO)

async def check_apple_scores():
    """Check exact Apple document scores with entity boosting"""
    
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
    query = "has 8th light worked with apple?"
    
    print("🔍 Apple Document Similarity Scores with Entity Boosting")
    print("=" * 60)
    print(f"Query: '{query}'")
    print()
    
    # Initialize services
    vector_store = create_vector_store(settings.vector)
    await vector_store.initialize()
    
    embedding_service = create_embedding_provider(settings.embedding, settings.llm)
    retrieval_service = RetrievalService(settings)
    
    # Get query embedding
    query_embedding = await embedding_service.get_embedding(query)
    
    # Do the entity filtering search (which includes boosting)
    enhanced_results = await retrieval_service._search_with_entity_filtering(
        query=query,
        query_embedding=query_embedding, 
        vector_service=vector_store
    )
    
    print(f"📊 Results from entity-enhanced search:")
    print(f"   Total results: {len(enhanced_results)}")
    print()
    
    apple_results = []
    for i, result in enumerate(enhanced_results[:15]):  # Top 15
        file_name = result.get("metadata", {}).get("file_name", "Unknown")
        similarity = result.get("similarity", 0)
        original_similarity = result.get("_original_similarity", similarity)
        entity_boost = result.get("_entity_boost", 0)
        matching_entities = result.get("_matching_entities", 0)
        
        is_apple = "apple" in file_name.lower()
        if is_apple:
            apple_results.append((file_name, similarity, original_similarity, entity_boost))
        
        status = "🍎 APPLE" if is_apple else "📄"
        print(f"{status} [{i:2}] {file_name[:70]}...")
        print(f"         Similarity: {similarity:.3f} (original: {original_similarity:.3f}, boost: +{entity_boost:.3f})")
        print(f"         Matching entities: {matching_entities}")
        print()
    
    print("🎯 Apple Document Summary:")
    print(f"   Found {len(apple_results)} Apple documents")
    print(f"   Similarity threshold: {settings.rag.similarity_threshold}")
    print(f"   Results threshold: {settings.rag.results_similarity_threshold}")
    print()
    
    for name, sim, orig_sim, boost in apple_results:
        passes_rag = sim >= settings.rag.similarity_threshold
        passes_results = sim >= settings.rag.results_similarity_threshold
        status_rag = "✅" if passes_rag else "❌"
        status_results = "✅" if passes_results else "❌"
        print(f"   • {name[:50]}...")
        print(f"     Score: {sim:.3f} | RAG threshold ({settings.rag.similarity_threshold}): {status_rag} | Results threshold ({settings.rag.results_similarity_threshold}): {status_results}")
        print(f"     Boost: +{boost:.3f} (from {orig_sim:.3f})")
        print()

if __name__ == "__main__":
    asyncio.run(check_apple_scores())