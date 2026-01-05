#!/usr/bin/env python3
"""
Debug script to check Apple documents in the vector database
"""

import asyncio
import os
import sys

# Load environment variables from .env file
from dotenv import load_dotenv

load_dotenv()

# Add bot directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "bot"))

from config.settings import Settings

from services.embedding_service import create_embedding_provider
from services.vector_service import create_vector_store


async def check_apple_documents():
    """Check Apple documents in the vector database"""

    # Load settings
    settings = Settings()

    if not settings.vector.enabled:
        print("❌ Vector search is not enabled in settings")
        return

    print("🔍 Checking Apple documents in vector database")
    print(f"🔧 Vector Provider: {settings.vector.provider}")
    print(f"🔧 Collection: {settings.vector.collection_name}")
    print()

    # Initialize services
    vector_store = create_vector_store(settings.vector)
    embedding_provider = create_embedding_provider(settings.embedding, settings.llm)

    await vector_store.initialize()

    try:
        # Search for Apple using text search instead of vector search
        query_embedding = await embedding_provider.get_embedding("Apple")

        results = await vector_store.search(
            query_embedding=query_embedding,
            query_text="Apple",  # Use text search for better compatibility
            limit=100,  # Get many results
            similarity_threshold=0.01,  # Very low threshold
        )

        print(f"Found {len(results)} total chunks mentioning Apple")
        print()

        # Group by document title and analyze
        documents = {}
        apple_chunks = []

        for result in results:
            metadata = result.get("metadata", {})
            content = result.get("content", "")
            file_name = metadata.get("file_name", "Unknown")

            # Check if this chunk contains "apple" (case insensitive)
            text_to_check = f"{file_name} {content}".lower()
            if "apple" in text_to_check:
                apple_chunks.append(result)

                # Group by document
                if file_name not in documents:
                    documents[file_name] = []
                documents[file_name].append(
                    {
                        "similarity": result.get("similarity", 0),
                        "content_preview": content[:100].replace("\n", " "),
                        "chunk_metadata": metadata,
                    }
                )

        print(f"🍎 Found {len(apple_chunks)} chunks containing 'Apple'")
        print(f"📄 Across {len(documents)} unique documents:")
        print()

        for doc_name, chunks in documents.items():
            print(f"📄 {doc_name}")
            print(f"   Chunks: {len(chunks)}")

            # Check if Apple is in the title
            apple_in_title = "apple" in doc_name.lower()
            print(f"   Apple in title: {'✅ YES' if apple_in_title else '❌ NO'}")

            # Show chunk details
            for i, chunk in enumerate(chunks[:3]):  # Show first 3 chunks
                similarity = chunk["similarity"]
                content_preview = chunk["content_preview"]
                print(
                    f"   Chunk {i+1}: Similarity {similarity:.3f} - {content_preview}..."
                )

            if len(chunks) > 3:
                print(f"   ... and {len(chunks) - 3} more chunks")
            print()

        print("🎯 Analysis:")
        apple_title_docs = [doc for doc in documents.keys() if "apple" in doc.lower()]
        print(f"   - Documents with 'Apple' in title: {len(apple_title_docs)}")
        for doc in apple_title_docs:
            chunk_count = len(documents[doc])
            print(f"     • {doc} ({chunk_count} chunks)")

        print(
            f"   - Total chunks from title documents: {sum(len(documents[doc]) for doc in apple_title_docs)}"
        )
        print(
            f"   - Other documents mentioning Apple: {len(documents) - len(apple_title_docs)}"
        )

    except Exception as e:
        print(f"❌ Error during check: {e}")
        import traceback

        traceback.print_exc()

    finally:
        await vector_store.close()


if __name__ == "__main__":
    asyncio.run(check_apple_documents())
