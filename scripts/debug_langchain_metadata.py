#!/usr/bin/env python3
"""
Debug script to compare direct Qdrant queries vs LangChain retrieval.

This helps identify why metadata might be missing when retrieved through LangChain.
"""
import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path.cwd() / "bot"))

from dotenv import load_dotenv

load_dotenv()


async def debug_metadata():
    """Compare direct Qdrant vs LangChain metadata retrieval."""
    from qdrant_client import QdrantClient

    # Get a recent document ID from logs (pass as argument or use default)
    doc_id = sys.argv[1] if len(sys.argv) > 1 else "09187b01-6953-5a1f-82be-7f59e4c5599d"

    print("=" * 100)
    print("COMPARING QDRANT DIRECT vs LANGCHAIN RETRIEVAL")
    print("=" * 100)
    print(f"\nDocument ID: {doc_id}")

    # 1. Direct Qdrant query
    print("\n" + "=" * 100)
    print("1. DIRECT QDRANT QUERY")
    print("=" * 100)

    client = QdrantClient(
        host=os.getenv('VECTOR_HOST'),
        port=int(os.getenv('VECTOR_PORT', 6333)),
        api_key=os.getenv('VECTOR_API_KEY'),
        https=True if os.getenv('VECTOR_HOST') != 'localhost' else False
    )

    collection = os.getenv('VECTOR_COLLECTION_NAME', 'insightmesh-knowledge-base')

    try:
        docs = client.retrieve(
            collection_name=collection,
            ids=[doc_id],
            with_payload=True,
            with_vectors=False
        )

        if docs:
            doc = docs[0]
            print(f"\n✅ Document found in Qdrant")
            print(f"Payload keys: {list(doc.payload.keys())}")
            print(f"\nPayload fields:")
            for key, value in doc.payload.items():
                if key == 'text':
                    print(f"  {key}: {str(value)[:100]}...")
                else:
                    print(f"  {key}: {value}")
        else:
            print("\n❌ Document not found in Qdrant")
            return 1
    except Exception as e:
        print(f"\n❌ Error querying Qdrant: {e}")
        return 1

    # 2. Bot's vector store retrieval
    print("\n" + "=" * 100)
    print("2. BOT'S VECTOR STORE RETRIEVAL")
    print("=" * 100)

    try:
        from services.vector_stores import QdrantVectorStore
        from services.embedding import create_embedding_provider
        from config.settings import Settings

        settings = Settings()

        # Initialize embedding provider
        embedding_provider = create_embedding_provider(settings.embedding)

        # Initialize bot's vector store
        vector_store = QdrantVectorStore(settings.vector)
        await vector_store.initialize()

        # Search for the document by its content
        print("\nSearching for document via bot's vector store...")

        # Get the document content from direct query
        doc_content = doc.payload.get('text', '')[:200]
        print(f"Searching for content: {doc_content[:80]}...")

        # Embed the query
        query_embedding = await embedding_provider.get_embedding(doc_content)

        # Search Qdrant using bot's method
        results = await vector_store.asearch(
            query_embedding=query_embedding,
            k=5
        )

        print(f"\n✅ Found {len(results)} documents via bot's vector store")

        # Check if our document is in the results
        found_target = False
        for i, result in enumerate(results, 1):
            # result structure from bot's vector store
            result_metadata = result.get('metadata', {})
            is_target = result_metadata.get('chunk_id', '') == doc.payload.get('chunk_id', '')
            marker = "👉 TARGET DOCUMENT" if is_target else ""

            print(f"\n{i}. Score: {result.get('score', 'N/A'):.4f} {marker}")
            print(f"   Metadata keys: {list(result_metadata.keys())}")
            print(f"   source: {result_metadata.get('source', 'MISSING')}")
            print(f"   file_name: {result_metadata.get('file_name', 'MISSING')}")
            print(f"   chunk_id: {result_metadata.get('chunk_id', 'MISSING')}")

            if is_target:
                found_target = True
                print("\n   Full metadata from bot's vector store:")
                for key, value in result_metadata.items():
                    if key == 'text':
                        print(f"      {key}: {str(value)[:100]}...")
                    else:
                        print(f"      {key}: {value}")

        if not found_target:
            print("\n⚠️  Target document not in top 5 results")

    except Exception as e:
        print(f"\n❌ Error with bot's vector store retrieval: {e}")
        import traceback
        traceback.print_exc()
        return 1

    # 3. Comparison
    print("\n" + "=" * 100)
    print("3. COMPARISON")
    print("=" * 100)

    if found_target:
        print("\n✅ Document metadata IS preserved through bot's vector store")
        print("If logs show missing metadata, the issue is in the logging code, not the data.")
    else:
        print("\n⚠️  Could not find target document in bot's vector store results")
        print("Try running with a different document ID.")

    return 0


if __name__ == '__main__':
    try:
        sys.exit(asyncio.run(debug_metadata()))
    except KeyboardInterrupt:
        print("\n\nAborted by user")
        sys.exit(1)
