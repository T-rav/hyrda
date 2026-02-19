"""QdrantVectorStore integration tests - wrapper class round-trip.

Tests exercise the QdrantVectorStore wrapper against a real Qdrant instance,
covering async executor wrapping, namespace filtering, diversification,
batch upsert, deterministic UUIDs, delete, and stats.

Run with: pytest -v -m integration bot/tests/test_integration_qdrant_store.py
"""

import hashlib
import os
import uuid
from contextlib import suppress

import pytest

from config.settings import VectorSettings
from services.vector_stores.qdrant_store import QdrantVectorStore

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]

TEST_COLLECTION = "integration_test_qdrant_store"
VECTOR_DIM = 1536  # Matches QdrantVectorStore's hardcoded dimension


def make_embedding(seed: float = 0.1) -> list[float]:
    """Generate a 1536-dim test embedding."""
    return [seed] * VECTOR_DIM


@pytest.fixture
async def qdrant_vector_store():
    """Create QdrantVectorStore with a test collection, clean up after."""
    host = os.getenv("VECTOR_HOST", "localhost")
    port = int(os.getenv("VECTOR_PORT", "6333"))
    api_key = os.getenv("VECTOR_API_KEY")

    settings = VectorSettings(
        provider="qdrant",
        host=host,
        port=port,
        collection_name=TEST_COLLECTION,
        api_key=api_key,
    )

    store = QdrantVectorStore(settings)
    try:
        await store.initialize()
    except Exception as e:
        error_str = str(e).lower()
        if "401" in str(e) or "unauthorized" in error_str:
            pytest.skip("Qdrant authentication failed")
        if (
            "connection refused" in error_str
            or "connect" in error_str
            or "timeout" in error_str
        ):
            pytest.skip("Qdrant not available")
        raise

    try:
        yield store
    finally:
        if store.client:
            with suppress(Exception):
                store.client.delete_collection(TEST_COLLECTION)
            await store.close()


async def test_initialize_creates_collection(qdrant_vector_store: QdrantVectorStore):
    """Verify initialize() creates the collection in Qdrant.

    Given: QdrantVectorStore with test settings
    When: initialize() is called by fixture
    Then: Collection exists in Qdrant
    """
    collections = qdrant_vector_store.client.get_collections()
    names = [c.name for c in collections.collections]
    assert TEST_COLLECTION in names


async def test_add_and_search_round_trip(qdrant_vector_store: QdrantVectorStore):
    """Add documents via add_documents(), search, verify content returned.

    Given: QdrantVectorStore with initialized collection
    When: Documents are added and searched with a matching embedding
    Then: Added documents appear in search results with correct content
    """
    texts = ["The quick brown fox", "Jumped over the lazy dog"]
    embeddings = [make_embedding(0.1), make_embedding(0.2)]
    metadata = [
        {"file_name": "doc1.txt", "source": "test"},
        {"file_name": "doc2.txt", "source": "test"},
    ]

    await qdrant_vector_store.add_documents(texts, embeddings, metadata)

    results = await qdrant_vector_store.search(
        query_embedding=make_embedding(0.1),
        limit=5,
        similarity_threshold=0.0,
    )

    assert len(results) >= 1
    contents = [r["content"] for r in results]
    assert "The quick brown fox" in contents


async def test_namespace_filtering(qdrant_vector_store: QdrantVectorStore):
    """Documents in 'metric' namespace AND default namespace both returned.

    Given: Documents added with and without namespace metadata
    When: search() is called
    Then: Both metric and default namespace documents appear in results
    """
    await qdrant_vector_store.add_documents(
        texts=["Revenue grew 20% YoY"],
        embeddings=[make_embedding(0.3)],
        metadata=[{"file_name": "metrics.csv", "namespace": "metric"}],
    )
    await qdrant_vector_store.add_documents(
        texts=["Company overview document"],
        embeddings=[make_embedding(0.31)],
        metadata=[{"file_name": "overview.txt"}],
    )

    results = await qdrant_vector_store.search(
        query_embedding=make_embedding(0.3),
        limit=10,
        similarity_threshold=0.0,
    )

    namespaces_found = {r["namespace"] for r in results}
    assert "metric" in namespaces_found
    assert "default" in namespaces_found


async def test_diversify_results(qdrant_vector_store: QdrantVectorStore):
    """Verify _diversify_results produces round-robin across file sources.

    Given: Multiple chunks from two files with similar embeddings
    When: search() is called
    Then: First two results are from different files (round-robin interleaving)
    """
    texts: list[str] = []
    embeddings: list[list[float]] = []
    metadata: list[dict] = []

    for i in range(3):
        texts.append(f"file_a chunk {i}")
        embeddings.append(make_embedding(0.5 + i * 0.001))
        metadata.append({"file_name": "file_a.pdf"})

    for i in range(3):
        texts.append(f"file_b chunk {i}")
        embeddings.append(make_embedding(0.5 + i * 0.001))
        metadata.append({"file_name": "file_b.pdf"})

    await qdrant_vector_store.add_documents(texts, embeddings, metadata)

    results = await qdrant_vector_store.search(
        query_embedding=make_embedding(0.5),
        limit=6,
        similarity_threshold=0.0,
    )

    file_names = [r["metadata"].get("file_name") for r in results]
    if len(file_names) >= 2:
        assert file_names[0] != file_names[1], (
            f"Expected round-robin diversification, got: {file_names}"
        )


async def test_batch_upsert_over_100(qdrant_vector_store: QdrantVectorStore):
    """Add >100 documents to exercise batch splitting logic.

    Given: QdrantVectorStore with batch_size=100
    When: 150 documents are added at once
    Then: All 150 documents are stored in Qdrant
    """
    n = 150
    texts = [f"batch document {i}" for i in range(n)]
    embeddings = [make_embedding(0.1 + i * 0.0001) for i in range(n)]
    metadata = [{"file_name": f"batch_{i}.txt"} for i in range(n)]

    await qdrant_vector_store.add_documents(texts, embeddings, metadata)

    stats = await qdrant_vector_store.get_stats()
    assert stats["total_vector_count"] >= n


async def test_deterministic_uuids_no_duplicates(
    qdrant_vector_store: QdrantVectorStore,
):
    """Adding the same documents twice should not create duplicates.

    Given: The same text and embedding added twice via add_documents()
    When: Stats are checked after both upserts
    Then: Only one document exists (upsert semantics via deterministic UUIDs)
    """
    texts = ["Deterministic UUID test"]
    embeddings = [make_embedding(0.7)]
    metadata = [{"file_name": "uuid_test.txt"}]

    await qdrant_vector_store.add_documents(texts, embeddings, metadata)
    await qdrant_vector_store.add_documents(texts, embeddings, metadata)

    stats = await qdrant_vector_store.get_stats()
    assert stats["total_vector_count"] == 1


async def test_delete_documents(qdrant_vector_store: QdrantVectorStore):
    """Add documents, delete by ID, verify no longer stored.

    Given: A document added to Qdrant
    When: delete_documents() is called with its deterministic UUID
    Then: Document count is 0
    """
    text = "Delete me please"
    embedding = make_embedding(0.8)

    await qdrant_vector_store.add_documents(
        [text], [embedding], [{"file_name": "delete.txt"}]
    )

    # Compute deterministic UUID matching QdrantVectorStore.add_documents() logic
    text_hash = hashlib.md5(f"{text}_0".encode(), usedforsecurity=False).hexdigest()
    doc_id = str(uuid.UUID(text_hash))

    await qdrant_vector_store.delete_documents([doc_id])

    stats = await qdrant_vector_store.get_stats()
    assert stats["total_vector_count"] == 0


async def test_get_stats(qdrant_vector_store: QdrantVectorStore):
    """Add documents, call get_stats(), verify point_count matches.

    Given: 3 documents added to Qdrant
    When: get_stats() is called
    Then: total_vector_count is 3 and expected stat keys are present
    """
    texts = ["Stats doc A", "Stats doc B", "Stats doc C"]
    embeddings = [make_embedding(0.4), make_embedding(0.41), make_embedding(0.42)]
    metadata = [{"file_name": f"stats_{i}.txt"} for i in range(3)]

    await qdrant_vector_store.add_documents(texts, embeddings, metadata)

    stats = await qdrant_vector_store.get_stats()
    assert stats["total_vector_count"] == 3
    assert "vectors_count" in stats
    assert "status" in stats


async def test_initialize_idempotent(qdrant_vector_store: QdrantVectorStore):
    """Calling initialize() twice should not raise.

    Given: QdrantVectorStore already initialized by fixture
    When: initialize() is called a second time
    Then: No exception is raised (collection-already-exists case handled gracefully)
    """
    await qdrant_vector_store.initialize()
    # No assertion needed -- reaching here without exception is the pass condition
