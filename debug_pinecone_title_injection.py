#!/usr/bin/env python3
"""
Debug script to check if Pinecone documents have title injection

Searches for documents and examines their content to see if they contain
[FILENAME] tags indicating proper title injection during ingestion.
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

# Set up detailed logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def check_title_injection():
    """Check if Pinecone documents have title injection"""

    try:
        # Set minimal required environment variables for testing
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

        # Load settings
        settings = Settings()

        print("🔍 Checking Title Injection in Pinecone Documents")
        print("=" * 55)
        print(f"Vector provider: {settings.vector.provider}")
        print(f"Collection: {settings.vector.collection_name}")
        hybrid_enabled = getattr(settings, 'hybrid', None)
        if hybrid_enabled:
            print(f"Hybrid enabled: {hybrid_enabled.enabled}")
            print(f"Title injection enabled: {getattr(hybrid_enabled, 'title_injection_enabled', 'Not configured')}")
        else:
            print("Hybrid settings: Not configured")
        print()

        # Force Pinecone for this test
        if settings.vector.provider.lower() != "pinecone":
            print("⚠️  Warning: Vector provider is not Pinecone")
            return

        # Initialize services
        print("🔧 Initializing services...")
        vector_store = create_vector_store(settings.vector)
        await vector_store.initialize()

        embedding_service = create_embedding_provider(settings.embedding, settings.llm)

        print("📊 Pinecone Index Statistics:")
        stats = await vector_store.get_stats()
        for key, value in stats.items():
            print(f"  - {key}: {value}")
        print()

        # Test queries to check for title injection
        test_queries = [
            "apple",
            "8th light apple",
            "project details"
        ]

        for query in test_queries:
            print(f"🔍 Testing query: '{query}'")
            print("-" * 40)

            query_embedding = await embedding_service.get_embedding(query)

            # Search with low threshold to get more results
            results = await vector_store.search(
                query_embedding=query_embedding,
                limit=20,
                similarity_threshold=0.0,
            )

            print(f"Found {len(results)} results")

            # Check if any results contain title injection
            title_injection_count = 0
            filename_tag_count = 0
            apple_docs = []

            for i, result in enumerate(results[:10]):  # Check first 10
                content = result.get("content", "")
                file_name = result.get("metadata", {}).get("file_name", "Unknown")
                similarity = result.get("similarity", 0)

                # Check for title injection patterns
                has_filename_tag = "[FILENAME]" in content and "[/FILENAME]" in content
                has_title_injection = has_filename_tag

                if has_title_injection:
                    title_injection_count += 1

                if has_filename_tag:
                    filename_tag_count += 1

                if "apple" in file_name.lower():
                    apple_docs.append((file_name, has_title_injection, similarity))

                print(f"  [{i}] {file_name} (sim: {similarity:.3f})")
                print(f"      Has [FILENAME] tags: {'✅' if has_filename_tag else '❌'}")

                if has_filename_tag:
                    # Extract and show the injected title
                    start = content.find("[FILENAME]")
                    end = content.find("[/FILENAME]", start)
                    if start != -1 and end != -1:
                        injected_title = content[start+10:end].strip()
                        print(f"      Injected title: '{injected_title}'")

                # Show first 150 chars of content
                content_preview = content.replace('\n', ' ').strip()[:150] + ("..." if len(content) > 150 else "")
                print(f"      Content: {content_preview}")
                print()

            print(f"📊 Summary for query '{query}':")
            print(f"   - Total results: {len(results)}")
            print(f"   - With [FILENAME] tags: {filename_tag_count}")
            print(f"   - With title injection: {title_injection_count}")
            print(f"   - Apple documents: {len(apple_docs)}")

            if apple_docs:
                print("   🍎 Apple documents found:")
                for name, has_injection, sim in apple_docs:
                    status = "✅ WITH" if has_injection else "❌ WITHOUT"
                    print(f"      {status} injection: {name} (sim: {sim:.3f})")

            print("\n" + "="*60 + "\n")

        # Final analysis
        print("🎯 OVERALL ANALYSIS")
        print("=" * 20)

        # Search all Apple documents with broad query
        print("Searching for all Apple documents...")
        apple_query = await embedding_service.get_embedding("Apple company project")
        all_results = await vector_store.search(
            query_embedding=apple_query,
            limit=100,
            similarity_threshold=0.0,
        )

        all_apple_docs = []
        total_with_injection = 0
        total_without_injection = 0

        for result in all_results:
            file_name = result.get("metadata", {}).get("file_name", "")
            content = result.get("content", "")

            if "apple" in file_name.lower():
                has_injection = "[FILENAME]" in content and "[/FILENAME]" in content
                all_apple_docs.append((file_name, has_injection, result.get("similarity", 0)))

                if has_injection:
                    total_with_injection += 1
                else:
                    total_without_injection += 1

        print(f"📈 Apple Documents Analysis:")
        print(f"   - Total unique Apple documents found: {len(set(doc[0] for doc in all_apple_docs))}")
        print(f"   - Apple chunks with title injection: {total_with_injection}")
        print(f"   - Apple chunks without title injection: {total_without_injection}")

        if total_without_injection > 0:
            print("\n❌ ISSUE IDENTIFIED:")
            print("   Apple documents are missing title injection!")
            print("   This explains why title-based searches are failing.")
            print("\n💡 SOLUTIONS:")
            print("   1. Re-ingest documents with hybrid RAG service enabled")
            print("   2. Or enable HYBRID_ENABLED=true and re-run ingestion")
            print("   3. Or add title injection to single Pinecone ingestion path")
        else:
            print("\n✅ Title injection appears to be working correctly!")

        # Show some examples of documents without injection
        if total_without_injection > 0:
            print("\n📄 Examples of documents WITHOUT title injection:")
            shown = 0
            for name, has_injection, sim in all_apple_docs:
                if not has_injection and shown < 3:
                    print(f"   - {name}")
                    shown += 1

    except Exception as e:
        logger.error(f"Error in debug script: {e}", exc_info=True)
        print(f"\n❌ Error: {e}")

if __name__ == "__main__":
    asyncio.run(check_title_injection())
