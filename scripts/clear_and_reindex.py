#!/usr/bin/env python3
"""
Clear all documents from Qdrant collection (or delete and recreate it).

This prepares the vector DB for fresh ingestion from Google Drive.
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path.cwd() / "bot"))

from dotenv import load_dotenv

load_dotenv()

from qdrant_client import QdrantClient


def clear_collection():
    """Clear all documents from the collection."""
    client = QdrantClient(
        host=os.getenv("VECTOR_HOST", "localhost"),
        port=int(os.getenv("VECTOR_PORT", 6333)),
        api_key=os.getenv("VECTOR_API_KEY"),
        https=True if os.getenv("VECTOR_HOST") != "localhost" else False,
    )

    collection = os.getenv("VECTOR_COLLECTION_NAME", "insightmesh-knowledge-base")

    print("=" * 100)
    print("CLEAR QDRANT COLLECTION")
    print("=" * 100)

    # Get collection info
    try:
        info = client.get_collection(collection)
        print(f"\nCollection: {collection}")
        print(f"Total documents: {info.points_count}")
        print(f"Vector size: {info.config.params.vectors.size}")
    except Exception as e:
        print(f"\n❌ Collection does not exist or error: {e}")
        print("\nNothing to clear.")
        return 0

    print("\n⚠️  WARNING: This will DELETE ALL DOCUMENTS in the collection!")
    print("You will need to re-ingest from Google Drive after this.")

    response = input(
        f"\nDelete all {info.points_count} documents from '{collection}'? (yes/no): "
    )
    if response.lower() != "yes":
        print("Aborted.")
        return 1

    print("\nDeleting collection...")
    try:
        client.delete_collection(collection)
        print(f"✅ Collection '{collection}' deleted successfully!")
        print("\nNext steps:")
        print("1. The collection will be automatically recreated on next ingestion")
        print("2. Run ingestion to repopulate:")
        print("   cd ingest && python main.py --folder-id YOUR_FOLDER_ID")
        return 0
    except Exception as e:
        print(f"\n❌ Error deleting collection: {e}")
        return 1


if __name__ == "__main__":
    try:
        sys.exit(clear_collection())
    except KeyboardInterrupt:
        print("\n\nAborted by user")
        sys.exit(1)
