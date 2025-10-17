"""Clear SEC filings from Qdrant vector database."""

import asyncio
import os
import sys

sys.path.insert(0, "bot")

from qdrant_client import QdrantClient
from qdrant_client.http.exceptions import UnexpectedResponse


async def main():
    """Clear SEC collections from Qdrant."""
    # Get Qdrant settings
    qdrant_host = os.getenv("VECTOR_HOST", "localhost")
    qdrant_port = int(os.getenv("VECTOR_PORT", "6333"))
    qdrant_api_key = os.getenv("QDRANT_API_KEY")

    print(f"\n{'='*60}")
    print("Clearing SEC Collections from Qdrant")
    print(f"{'='*60}\n")
    print(f"Host: {qdrant_host}:{qdrant_port}")

    # Connect to Qdrant
    client = QdrantClient(
        host=qdrant_host,
        port=qdrant_port,
        api_key=qdrant_api_key,
        timeout=30,
        https=False,  # Local Qdrant doesn't use HTTPS
    )

    # List all collections
    try:
        collections = client.get_collections()
        print(f"\nFound {len(collections.collections)} collections:")
        for collection in collections.collections:
            print(f"  - {collection.name}")
    except Exception as e:
        print(f"❌ Error listing collections: {e}")
        return

    # Find and delete SEC-related collections
    sec_collections = [
        "sec_filings",
        "sec_documents",
        "sec",
    ]

    deleted = []
    not_found = []

    for collection_name in sec_collections:
        try:
            # Try to delete the collection
            result = client.delete_collection(collection_name)
            deleted.append(collection_name)
            print(f"✅ Deleted collection: {collection_name}")
        except UnexpectedResponse as e:
            if "doesn't exist" in str(e).lower() or "not found" in str(e).lower():
                not_found.append(collection_name)
                print(f"⚠️  Collection not found: {collection_name}")
            else:
                print(f"❌ Error deleting {collection_name}: {e}")
        except Exception as e:
            print(f"❌ Error deleting {collection_name}: {e}")

    # Also try to delete any SEC-related vectors from main collection
    main_collections = ["documents", "knowledge_base", "insightmesh"]
    for collection_name in main_collections:
        try:
            # Check if collection exists
            client.get_collection(collection_name)

            # Try to delete SEC-related points by metadata filter
            from qdrant_client.models import Filter, FieldCondition, MatchValue

            filter_sec = Filter(
                should=[
                    FieldCondition(
                        key="source",
                        match=MatchValue(value="sec"),
                    ),
                    FieldCondition(
                        key="namespace",
                        match=MatchValue(value="sec_filings"),
                    ),
                    FieldCondition(
                        key="filing_type",
                        match=MatchValue(any=["10-K", "8-K", "10-Q"]),
                    ),
                ]
            )

            # Delete points matching filter
            result = client.delete(
                collection_name=collection_name,
                points_selector=filter_sec,
            )

            print(f"✅ Deleted SEC vectors from: {collection_name}")

        except UnexpectedResponse as e:
            if "doesn't exist" in str(e).lower() or "not found" in str(e).lower():
                continue  # Collection doesn't exist, that's fine
            else:
                print(f"⚠️  Could not clean {collection_name}: {e}")
        except Exception as e:
            print(f"⚠️  Could not clean {collection_name}: {e}")

    print(f"\n{'='*60}")
    print("Summary")
    print(f"{'='*60}\n")
    print(f"Collections deleted: {len(deleted)}")
    if deleted:
        for name in deleted:
            print(f"  ✅ {name}")
    print(f"\nCollections not found: {len(not_found)}")
    if not_found:
        for name in not_found:
            print(f"  ⚠️  {name}")

    print("\n✅ SEC vector cleanup complete!\n")


if __name__ == "__main__":
    asyncio.run(main())
