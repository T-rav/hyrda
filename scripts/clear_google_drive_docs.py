#!/usr/bin/env python3
"""
Clear only google_drive documents from Qdrant collection.

Keeps metric documents intact.
This prepares the vector DB for fresh ingestion from Google Drive without losing metric data.
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path.cwd() / "bot"))

from dotenv import load_dotenv

load_dotenv()

from qdrant_client import QdrantClient


def clear_google_drive_docs():
    client = QdrantClient(
        host=os.getenv('VECTOR_HOST', 'localhost'),
        port=int(os.getenv('VECTOR_PORT', 6333)),
        api_key=os.getenv('VECTOR_API_KEY'),
        https=True if os.getenv('VECTOR_HOST') != 'localhost' else False
    )

    collection = os.getenv('VECTOR_COLLECTION_NAME', 'insightmesh-knowledge-base')

    print("=" * 100)
    print("CLEAR GOOGLE DRIVE DOCUMENTS (KEEP METRIC DOCS)")
    print("=" * 100)

    # Get collection info
    try:
        info = client.get_collection(collection)
        print(f"\nCollection: {collection}")
        print(f"Total documents: {info.points_count}")
    except Exception as e:
        print(f"\n❌ Collection does not exist or error: {e}")
        return 1

    # Find google_drive documents to delete
    print("\nScanning for google_drive documents...")
    offset = None
    batch_size = 100
    google_drive_ids = []
    metric_count = 0
    other_count = 0

    while True:
        points, offset = client.scroll(
            collection,
            limit=batch_size,
            offset=offset,
            with_payload=True
        )

        if not points:
            break

        for point in points:
            source = point.payload.get('source', 'MISSING')
            if source == 'google_drive':
                google_drive_ids.append(point.id)
            elif source == 'metric':
                metric_count += 1
            else:
                other_count += 1

        if offset is None:
            break

    print(f"\n✅ Scan complete:")
    print(f"  google_drive documents to DELETE: {len(google_drive_ids)}")
    print(f"  metric documents to KEEP: {metric_count}")
    print(f"  other documents: {other_count}")

    if not google_drive_ids:
        print("\n✅ No google_drive documents to delete")
        return 0

    print("\n⚠️  WARNING: This will DELETE ALL google_drive documents!")
    print("Metric documents will remain intact.")
    print("You will need to re-ingest from Google Drive after this.")

    response = input(f"\nDelete {len(google_drive_ids)} google_drive documents? (yes/no): ")
    if response.lower() != 'yes':
        print("Aborted.")
        return 1

    # Delete in batches
    print(f"\nDeleting {len(google_drive_ids)} google_drive documents...")
    batch_size = 100
    for i in range(0, len(google_drive_ids), batch_size):
        batch = google_drive_ids[i:i + batch_size]
        client.delete(
            collection_name=collection,
            points_selector=batch
        )
        print(f"  Deleted batch {i // batch_size + 1}/{(len(google_drive_ids) + batch_size - 1) // batch_size}")

    # Get updated count
    info = client.get_collection(collection)
    print(f"\n✅ Deletion complete!")
    print(f"Total documents remaining: {info.points_count}")
    print(f"  (should be ~{metric_count} metric docs + {other_count} other docs)")

    print("\nNext steps:")
    print("1. Run ingestion to repopulate google_drive documents:")
    print(f"   cd ingest && python main.py --folder-id YOUR_FOLDER_ID")

    return 0


if __name__ == '__main__':
    try:
        sys.exit(clear_google_drive_docs())
    except KeyboardInterrupt:
        print("\n\nAborted by user")
        sys.exit(1)
