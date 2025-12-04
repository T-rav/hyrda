#!/usr/bin/env python3
"""
Delete all documents with file_name='unknown' from Qdrant.

These are corrupted/incomplete documents without proper metadata
that cause false positives in relationship detection.
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path.cwd() / "bot"))

from dotenv import load_dotenv

load_dotenv()

from qdrant_client import QdrantClient


def delete_unknown_documents():
    """Delete all documents with file_name='unknown' from Qdrant."""
    client = QdrantClient(
        host=os.getenv("VECTOR_HOST", "localhost"),
        port=int(os.getenv("VECTOR_PORT", 6333)),
        api_key=os.getenv("VECTOR_API_KEY"),
        https=True if os.getenv("VECTOR_HOST") != "localhost" else False,
    )

    collection = os.getenv("VECTOR_COLLECTION_NAME", "insightmesh-knowledge-base")

    print("=" * 100)
    print("DELETE DOCUMENTS WITH UNKNOWN FILE_NAME")
    print("=" * 100)

    # Get collection info
    info = client.get_collection(collection)
    print(f"\nCollection: {collection}")
    print(f"Total documents BEFORE deletion: {info.points_count}")

    # Find documents without proper file_name
    print("\nSearching for documents with file_name='unknown'...")

    offset = None
    unknown_point_ids = []
    batch_size = 100

    while True:
        points, offset = client.scroll(
            collection, limit=batch_size, offset=offset, with_payload=True
        )

        if not points:
            break

        for point in points:
            file_name = point.payload.get("file_name", "unknown")
            # Check if file_name is missing, empty, or explicitly 'unknown'
            if not file_name or file_name == "unknown" or file_name.strip() == "":
                unknown_point_ids.append(point.id)
                if len(unknown_point_ids) <= 10:
                    content_preview = point.payload.get("page_content", "")[:100]
                    print(
                        f"  Found: file_name='{file_name}', content: {content_preview}..."
                    )

        if offset is None:
            break

    if not unknown_point_ids:
        print("\n✅ No documents with unknown file_name found")
        return 0

    print(
        f"\n🚨 Found {len(unknown_point_ids)} documents with unknown/missing file_name"
    )
    print("\nThese are corrupted documents without proper metadata.")
    print("They cause false positives in relationship detection.")

    response = input(f"\nDelete {len(unknown_point_ids)} documents? (yes/no): ")
    if response.lower() != "yes":
        print("Aborted.")
        return 1

    # Delete in batches
    print(f"\nDeleting {len(unknown_point_ids)} documents...")
    batch_size = 100
    for i in range(0, len(unknown_point_ids), batch_size):
        batch = unknown_point_ids[i : i + batch_size]
        client.delete(collection_name=collection, points_selector=batch)
        print(
            f"  Deleted batch {i // batch_size + 1}/{(len(unknown_point_ids) + batch_size - 1) // batch_size}"
        )

    # Get updated count
    info = client.get_collection(collection)
    print("\n✅ Deletion complete!")
    print(f"Total documents AFTER deletion: {info.points_count}")
    print(f"Deleted: {len(unknown_point_ids)} documents")

    return 0


if __name__ == "__main__":
    try:
        sys.exit(delete_unknown_documents())
    except KeyboardInterrupt:
        print("\n\nAborted by user")
        sys.exit(1)
