"""Qdrant vector store smoke tests.

Verifies Qdrant is accessible and operational for vector search.
"""

import os
import uuid

import pytest
from qdrant_client import QdrantClient

QDRANT_HOST = os.getenv("VECTOR_HOST", "qdrant")
QDRANT_PORT = int(os.getenv("VECTOR_PORT", "6333"))
QDRANT_API_KEY = os.getenv("VECTOR_API_KEY", None)
COLLECTION_NAME = os.getenv("VECTOR_COLLECTION_NAME", "insightmesh-knowledge-base")


@pytest.fixture
def qdrant_client():
    """Create Qdrant client."""
    return QdrantClient(
        host=QDRANT_HOST,
        port=QDRANT_PORT,
        api_key=QDRANT_API_KEY,
        https=False,
    )


@pytest.mark.smoke
class TestQdrantConnection:
    """Verify Qdrant connectivity."""

    def test_qdrant_connection(self, qdrant_client):
        """Can connect to Qdrant and get cluster info."""
        # Get collections list to verify connection
        collections = qdrant_client.get_collections()
        assert collections is not None

    def test_collection_exists(self, qdrant_client):
        """Knowledge base collection exists."""
        collections = qdrant_client.get_collections()
        collection_names = [c.name for c in collections.collections]
        assert COLLECTION_NAME in collection_names


@pytest.mark.smoke
class TestVectorOperations:
    """Verify vector operations work."""

    def test_vector_upsert_and_search(self, qdrant_client):
        """Can insert vectors and perform similarity search."""
        # Generate random test vector (1536 dimensions for OpenAI embeddings)
        test_id = str(uuid.uuid4())
        test_vector = [0.1] * 1536

        # Upsert test point
        qdrant_client.upsert(
            collection_name=COLLECTION_NAME,
            points=[
                {
                    "id": test_id,
                    "vector": test_vector,
                    "payload": {"test": True, "source": "smoke_test"},
                }
            ],
        )

        # Search for similar vectors
        results = qdrant_client.search(
            collection_name=COLLECTION_NAME,
            query_vector=test_vector,
            limit=1,
            query_filter={
                "must": [
                    {"key": "test", "match": {"value": True}},
                    {"key": "source", "match": {"value": "smoke_test"}},
                ]
            },
        )

        assert len(results) > 0
        assert results[0].id == test_id

        # Clean up
        qdrant_client.delete(
            collection_name=COLLECTION_NAME,
            points_selector=[test_id],
        )

    def test_collection_info(self, qdrant_client):
        """Can retrieve collection information."""
        info = qdrant_client.get_collection(COLLECTION_NAME)
        assert info is not None
        assert info.config.params.vectors.size == 1536
