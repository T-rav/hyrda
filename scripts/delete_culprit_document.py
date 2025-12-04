#!/usr/bin/env python3
"""
Delete the specific culprit document causing false positives.
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path.cwd() / "bot"))

from dotenv import load_dotenv

load_dotenv()

from qdrant_client import QdrantClient


def delete_culprit():
    """Delete the culprit document by ID."""
    client = QdrantClient(
        host=os.getenv("VECTOR_HOST", "localhost"),
        port=int(os.getenv("VECTOR_PORT", 6333)),
        api_key=os.getenv("VECTOR_API_KEY"),
        https=True if os.getenv("VECTOR_HOST") != "localhost" else False,
    )

    collection = os.getenv("VECTOR_COLLECTION_NAME", "insightmesh-knowledge-base")
    culprit_id = "f74b4986-194a-53b9-8b96-827577675866"

    print("=" * 100)
    print("DELETE CULPRIT DOCUMENT")
    print("=" * 100)

    # Check if it exists first
    try:
        docs = client.retrieve(collection, ids=[culprit_id])
        if not docs:
            print(f"\n❌ Document {culprit_id} not found (might already be deleted)")
            return 0

        doc = docs[0]
        print("\nFound document:")
        print(f"  ID: {doc.id}")
        print(f"  Metadata: {doc.payload}")

    except Exception as e:
        print(f"\n❌ Error retrieving document: {e}")
        return 1

    # Delete it
    response = input("\nDelete this document? (yes/no): ")
    if response.lower() != "yes":
        print("Aborted.")
        return 1

    try:
        client.delete(collection_name=collection, points_selector=[culprit_id])
        print(f"\n✅ Deleted document {culprit_id}")
        return 0
    except Exception as e:
        print(f"\n❌ Error deleting document: {e}")
        return 1


if __name__ == "__main__":
    try:
        sys.exit(delete_culprit())
    except KeyboardInterrupt:
        print("\n\nAborted by user")
        sys.exit(1)
