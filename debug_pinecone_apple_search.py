#!/usr/bin/env python3
"""
Debug script to test Pinecone search for Apple-related documents

Tests the specific query "has 8th light worked with apple?" to verify
that documents with "Apple" in the title are being found and boosted properly.
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

# Set up detailed logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def debug_pinecone_search():
    """Debug Pinecone search for Apple documents"""
    
    # Test query that should find Apple documents
    test_query = "has 8th light worked with apple?"
    
    print("🔍 Debugging Pinecone Apple Search")
    print("=" * 50)
    print(f"Query: '{test_query}'")
    print()
    
    try:
        # Try to load from actual .env file if it exists
        env_file = os.path.join(os.path.dirname(__file__), '.env')
        if os.path.exists(env_file):
            print(f"📁 Loading environment from: {env_file}")
            with open(env_file, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and '=' in line:
                        key, value = line.split('=', 1)
                        # Remove comments from value
                        value = value.split('#')[0].strip()
                        os.environ.setdefault(key.strip(), value)
        else:
            # Fallback minimal settings for testing
            print("⚠️  No .env file found, using test settings")
            os.environ.setdefault('SLACK_BOT_TOKEN', 'xoxb-test-token')  
            os.environ.setdefault('SLACK_APP_TOKEN', 'xapp-test-token')
            os.environ.setdefault('LLM_API_KEY', 'test-key')
            os.environ.setdefault('DATABASE_URL', 'postgresql://test:test@localhost:5432/test')
        
        # Load settings
        settings = Settings()
        print(f"Vector provider: {settings.vector.provider}")
        print(f"Vector URL: {settings.vector.url}")
        print(f"Collection: {settings.vector.collection_name}")
        print(f"RAG settings:")
        print(f"  - Max results: {settings.rag.max_results}")
        print(f"  - Similarity threshold: {settings.rag.similarity_threshold}")
        print(f"  - Results threshold: {settings.rag.results_similarity_threshold}")
        print(f"  - Hybrid search: {settings.rag.enable_hybrid_search}")
        print()
        
        # Force Pinecone for this test
        if settings.vector.provider.lower() != "pinecone":
            print("⚠️  Warning: Vector provider is not Pinecone")
            print(f"Current provider: {settings.vector.provider}")
            print("This debug script is specifically for testing Pinecone")
            return
        
        # Initialize services
        print("🔧 Initializing services...")
        vector_store = create_vector_store(settings.vector)
        await vector_store.initialize()
        
        embedding_service = create_embedding_provider(settings.embedding, settings.llm)
        # Embedding service doesn't need explicit initialization
        
        retrieval_service = RetrievalService(settings)
        
        # Get Pinecone index stats
        print("\n📊 Pinecone Index Statistics:")
        stats = await vector_store.get_stats()
        for key, value in stats.items():
            print(f"  - {key}: {value}")
        print()
        
        # Test 1: Direct Pinecone search with raw query embedding
        print("🎯 Test 1: Direct Pinecone Vector Search")
        print("-" * 40)
        
        query_embedding = await embedding_service.get_embedding(test_query)
        print(f"Query embedding dimension: {len(query_embedding)}")
        
        # Search with different limits and thresholds
        for limit in [10, 25, 50]:
            for threshold in [0.0, 0.1, 0.3, 0.5]:
                print(f"\n  Limit: {limit}, Threshold: {threshold}")
                raw_results = await vector_store.search(
                    query_embedding=query_embedding,
                    limit=limit,
                    similarity_threshold=threshold,
                )
                
                print(f"    Found {len(raw_results)} results")
                
                # Check for Apple documents
                apple_docs = []
                for i, result in enumerate(raw_results[:5]):  # Show top 5
                    file_name = result.get("metadata", {}).get("file_name", "Unknown")
                    similarity = result.get("similarity", 0)
                    content_preview = result.get("content", "")[:100] + "..."
                    
                    if "apple" in file_name.lower():
                        apple_docs.append(file_name)
                        print(f"    ✅ [{i}] APPLE: {file_name} (sim: {similarity:.3f})")
                    else:
                        print(f"    📄 [{i}] {file_name} (sim: {similarity:.3f})")
                    
                    print(f"         Content: {content_preview}")
                
                if apple_docs:
                    print(f"    🍎 Found {len(apple_docs)} Apple documents!")
                    unique_apple_docs = set(apple_docs)
                    print(f"    📝 Unique Apple docs: {len(unique_apple_docs)}")
                    for doc in sorted(unique_apple_docs):
                        print(f"         - {doc}")
                else:
                    print(f"    ❌ No Apple documents found with limit={limit}, threshold={threshold}")
        
        # Test 2: Entity extraction and boosting
        print("\n\n🎯 Test 2: Entity Extraction and Boosting")
        print("-" * 40)
        
        # Test entity extraction  
        retrieval = RetrievalService(settings)
        entities = retrieval._extract_entities_simple(test_query)
        print(f"Extracted entities: {entities}")
        
        # Expected to find "Apple" as a capitalized entity
        if "Apple" not in entities:
            print("❌ 'Apple' not extracted as an entity - this is a problem!")
            print("   Entity extraction should find capitalized words as potential proper nouns")
        else:
            print("✅ 'Apple' correctly extracted as an entity")
        
        # Test 3: Full retrieval service (with entity boosting if enabled)
        print("\n\n🎯 Test 3: Full Retrieval Service Pipeline")
        print("-" * 40)
        
        final_results = await retrieval_service.retrieve_context(
            query=test_query,
            vector_service=vector_store,
            embedding_service=embedding_service,
        )
        
        print(f"Final results: {len(final_results)} documents")
        
        apple_count = 0
        unique_apple_files = set()
        
        for i, result in enumerate(final_results):
            file_name = result.get("metadata", {}).get("file_name", "Unknown")
            similarity = result.get("similarity", 0)
            
            # Check for debug info from entity boosting
            entity_boost = result.get("_entity_boost", 0)
            matching_entities = result.get("_matching_entities", 0)
            original_similarity = result.get("_original_similarity")
            
            if "apple" in file_name.lower():
                apple_count += 1
                unique_apple_files.add(file_name)
                print(f"✅ [{i}] APPLE: {file_name}")
                print(f"     Similarity: {similarity:.3f}", end="")
                if original_similarity is not None:
                    print(f" (original: {original_similarity:.3f}, boost: +{entity_boost:.3f})")
                else:
                    print()
                if matching_entities > 0:
                    print(f"     Matching entities: {matching_entities}")
            else:
                print(f"📄 [{i}] {file_name} (sim: {similarity:.3f})")
        
        print(f"\n📈 Summary:")
        print(f"   Total results: {len(final_results)}")
        print(f"   Apple documents: {apple_count}")
        print(f"   Unique Apple files: {len(unique_apple_files)}")
        
        # Expected Apple documents (from the test)
        expected_apple_docs = {
            "Apple - Project Details File",
            "Apple - Accelerating Experimentation with Automation and Self-Service Tools - Kristin Kaeding",
            "Apple - Frontend Engineering: Strategic Interface Design in Services-First Ecosystems",
            "Apple - Scaling Experimentation in a Fortune 100 Company: Lessons in Automation and Developer Efficiency",
        }
        
        print(f"\n🎯 Expected vs Found:")
        print(f"   Expected 4 Apple documents:")
        for doc in sorted(expected_apple_docs):
            found = doc in unique_apple_files
            status = "✅ FOUND" if found else "❌ MISSING"
            print(f"     {status}: {doc}")
        
        missing_docs = expected_apple_docs - unique_apple_files
        extra_docs = unique_apple_files - expected_apple_docs
        
        if missing_docs:
            print(f"\n❌ Missing Apple documents ({len(missing_docs)}):")
            for doc in sorted(missing_docs):
                print(f"     - {doc}")
        
        if extra_docs:
            print(f"\n➕ Extra Apple documents found ({len(extra_docs)}):")
            for doc in sorted(extra_docs):
                print(f"     - {doc}")
        
        # Test 4: Check if documents even exist in the index
        print("\n\n🎯 Test 4: Verify Apple Documents Exist in Index")
        print("-" * 50)
        
        # Search with very broad parameters to see all Apple-related content
        print("Searching with very low threshold (0.0) and high limit (100)...")
        broad_results = await vector_store.search(
            query_embedding=query_embedding,
            limit=100,
            similarity_threshold=0.0,
        )
        
        all_apple_docs = set()
        for result in broad_results:
            file_name = result.get("metadata", {}).get("file_name", "")
            if "apple" in file_name.lower():
                all_apple_docs.add(file_name)
        
        print(f"Found {len(all_apple_docs)} unique Apple documents in index:")
        for doc in sorted(all_apple_docs):
            print(f"  - {doc}")
        
        if not all_apple_docs:
            print("❌ NO APPLE DOCUMENTS FOUND IN INDEX!")
            print("   This suggests the documents were never ingested properly.")
            print("   Check your ingestion process.")
        elif len(all_apple_docs) < 4:
            print(f"⚠️  Only {len(all_apple_docs)} Apple documents in index, expected 4+")
            print("   Some Apple documents may not have been ingested.")
        else:
            print("✅ Apple documents are present in the index")
            
            # If documents exist but aren't found with reasonable similarity, it's an embedding/query issue
            apple_similarities = []
            for result in broad_results:
                file_name = result.get("metadata", {}).get("file_name", "")
                if "apple" in file_name.lower():
                    apple_similarities.append(result.get("similarity", 0))
            
            if apple_similarities:
                max_sim = max(apple_similarities)
                min_sim = min(apple_similarities)
                avg_sim = sum(apple_similarities) / len(apple_similarities)
                
                print(f"\n📊 Apple Document Similarities:")
                print(f"   Max: {max_sim:.3f}")
                print(f"   Min: {min_sim:.3f}")  
                print(f"   Avg: {avg_sim:.3f}")
                
                if max_sim < 0.5:
                    print("⚠️  Low similarity scores suggest embedding/query mismatch")
                    print("   Consider checking:")
                    print("     - Embedding model consistency")
                    print("     - Title injection in document content")
                    print("     - Query preprocessing")
        
    except Exception as e:
        logger.error(f"Error in debug script: {e}", exc_info=True)
        print(f"\n❌ Error: {e}")

if __name__ == "__main__":
    asyncio.run(debug_pinecone_search())