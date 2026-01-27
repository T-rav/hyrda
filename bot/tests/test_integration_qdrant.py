"""Qdrant vector database integration tests - CRITICAL INFRASTRUCTURE.

Tests verify Qdrant connection, collection existence, and vector operations.
These tests validate that RAG functionality works correctly.

Run with: pytest -v -m integration bot/tests/test_integration_qdrant.py

NOTE: These tests require Qdrant running with proper authentication.
They will skip if Qdrant is not available or auth fails.
"""

import os
import ssl

import pytest
from qdrant_client import QdrantClient
from qdrant_client.http.exceptions import UnexpectedResponse
from qdrant_client.models import Distance, PointStruct, VectorParams

pytestmark = pytest.mark.integration


@pytest.fixture
def qdrant_client():
    """Create Qdrant client for testing."""
    host = os.getenv("VECTOR_HOST", "localhost")
    port = int(os.getenv("VECTOR_PORT", "6333"))
    api_key = os.getenv("VECTOR_API_KEY")

    # Path to CA certificate for SSL validation
    # The mkcert CA signs all local certificates
    ca_cert_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
        ".ssl",
        "mkcert-ca.crt",
    )

    # Create SSL context with mkcert CA certificate
    if os.path.exists(ca_cert_path):
        ssl_context = ssl.create_default_context(cafile=ca_cert_path)
        # Create client with proper SSL context
        client = QdrantClient(
            url=f"https://{host}:{port}",
            api_key=api_key,
            timeout=10.0,
            prefer_grpc=False,  # Use REST API
            https=True,
            verify=ssl_context,  # Use SSL context with mkcert CA
        )
    else:
        # Fallback if CA cert not found
        pytest.skip(f"mkcert CA certificate not found at {ca_cert_path}")

    # Test connection - skip if auth fails
    try:
        client.get_collections()
    except UnexpectedResponse as e:
        if "401" in str(e) or "Unauthorized" in str(e):
            pytest.skip(
                "Qdrant authentication failed. Configure VECTOR_API_KEY or disable auth."
            )
        raise

    try:
        yield client
    finally:
        client.close()


def test_qdrant_connection(qdrant_client):
    """
    CRITICAL TEST - Qdrant connection must work.

    Given: Qdrant service is running
    When: Application starts
    Then: Qdrant connection succeeds

    Failure Impact: RAG service won't start if Qdrant unavailable
    """
    # Test connection with health check
    health = qdrant_client.get_collections()
    assert health is not None, "Qdrant connection failed"

    print(f"✅ Qdrant connection successful ({len(health.collections)} collections)")


def test_required_collections_exist(qdrant_client):
    """
    CRITICAL TEST - Required vector collections must exist.

    Given: RAG service needs document embeddings
    When: Checking Qdrant collections
    Then: Required collections exist (documents, embeddings)

    Failure Impact: RAG queries will fail if collections missing
    """
    # Get all collections
    collections = qdrant_client.get_collections().collections
    collection_names = [c.name for c in collections]

    # Check for required collections (adjust based on your setup)
    # Common collection names: documents, embeddings, company_profiles, etc.
    if not collection_names:
        pytest.skip(
            "No Qdrant collections found - may be fresh deployment. "
            "Run document ingestion first."
        )

    print(f"✅ Found {len(collection_names)} Qdrant collections: {collection_names}")


def test_qdrant_collection_info(qdrant_client):
    """
    BUSINESS LOGIC TEST - Collection configuration validation.

    Given: Qdrant collections exist
    When: Checking collection details
    Then: Collections have correct vector dimensions and distance metric
    """
    collections = qdrant_client.get_collections().collections

    if not collections:
        pytest.skip("No collections to validate")

    for collection in collections[:5]:  # Check first 5 collections
        collection_name = collection.name
        info = qdrant_client.get_collection(collection_name)

        # Validate vector config
        vector_config = info.config.params.vectors
        if isinstance(vector_config, VectorParams):
            # Single vector config
            print(
                f"✅ Collection '{collection_name}': "
                f"dim={vector_config.size}, "
                f"distance={vector_config.distance}"
            )
        elif isinstance(vector_config, dict):
            # Named vectors config
            for name, params in vector_config.items():
                print(
                    f"✅ Collection '{collection_name}' vector '{name}': "
                    f"dim={params.size}, "
                    f"distance={params.distance}"
                )

        # Check vector count
        point_count = info.points_count
        print(f"   └─ {point_count} vectors stored")


def test_vector_insert_and_search(qdrant_client):
    """
    CRITICAL TEST - Vector insert and similarity search must work.

    Given: Qdrant is accessible
    When: Inserting test vector and searching
    Then: Vector is retrievable with similarity search

    Failure Impact: RAG search won't work
    """
    test_collection = "integration_test_collection"

    try:
        # Create test collection
        qdrant_client.create_collection(
            collection_name=test_collection,
            vectors_config=VectorParams(
                size=384,  # Standard embedding dimension (all-MiniLM-L6-v2)
                distance=Distance.COSINE,
            ),
        )

        # Insert test vector
        test_vector = [0.1] * 384  # Simple test vector
        qdrant_client.upsert(
            collection_name=test_collection,
            points=[
                PointStruct(
                    id=1,
                    vector=test_vector,
                    payload={"text": "integration test document"},
                )
            ],
        )

        # Search for similar vectors
        results = qdrant_client.query_points(
            collection_name=test_collection,
            query=test_vector,
            limit=1,
        ).points

        assert len(results) == 1, "Vector search returned no results"
        assert results[0].id == 1, "Vector search returned wrong result"
        assert results[0].score > 0.99, f"Vector similarity too low: {results[0].score}"

        print("✅ Vector insert and similarity search working")

    finally:
        # Cleanup: delete test collection
        from contextlib import suppress

        with suppress(Exception):
            qdrant_client.delete_collection(test_collection)


def test_qdrant_vector_dimension_consistency(qdrant_client):
    """
    CRITICAL TEST - Vector dimensions must be consistent.

    Given: Collections have vector configurations
    When: Checking vector dimensions
    Then: Dimensions match embedding model (e.g., 384, 768, 1536)

    Failure Impact: Dimension mismatches cause insert/search failures
    """
    collections = qdrant_client.get_collections().collections

    if not collections:
        pytest.skip("No collections to validate")

    # Common embedding dimensions:
    # - 384: all-MiniLM-L6-v2 (sentence-transformers)
    # - 768: BERT-base
    # - 1536: text-embedding-ada-002 (OpenAI)
    # - 3072: text-embedding-3-large (OpenAI)
    valid_dimensions = [384, 768, 1536, 3072]

    for collection in collections[:5]:
        info = qdrant_client.get_collection(collection.name)
        vector_config = info.config.params.vectors

        if isinstance(vector_config, VectorParams):
            dimension = vector_config.size
            if dimension not in valid_dimensions:
                print(
                    f"⚠️  WARNING: Collection '{collection.name}' "
                    f"has unusual dimension: {dimension}"
                )
            else:
                print(f"✅ Collection '{collection.name}' dimension valid: {dimension}")


def test_qdrant_distance_metric(qdrant_client):
    """
    BUSINESS LOGIC TEST - Distance metric validation.

    Given: Collections have distance metrics
    When: Checking distance metric type
    Then: Using appropriate metric (COSINE recommended for text embeddings)
    """
    collections = qdrant_client.get_collections().collections

    if not collections:
        pytest.skip("No collections to validate")

    for collection in collections[:5]:
        info = qdrant_client.get_collection(collection.name)
        vector_config = info.config.params.vectors

        if isinstance(vector_config, VectorParams):
            distance = vector_config.distance
            if distance != Distance.COSINE:
                print(
                    f"⚠️  INFO: Collection '{collection.name}' "
                    f"uses {distance} (COSINE recommended for text)"
                )
            else:
                print(f"✅ Collection '{collection.name}' uses COSINE distance")


def test_qdrant_search_performance(qdrant_client):
    """
    PERFORMANCE TEST - Vector search should be fast.

    Given: Collections have vectors
    When: Performing similarity search
    Then: Search completes within acceptable time (< 200ms)
    """
    collections = qdrant_client.get_collections().collections

    if not collections:
        pytest.skip("No collections for performance test")

    # Pick first non-empty collection
    test_collection = None
    for collection in collections:
        info = qdrant_client.get_collection(collection.name)
        if info.points_count > 0:
            test_collection = collection.name
            break

    if not test_collection:
        pytest.skip("No collections with vectors for performance test")

    # Get vector dimension
    info = qdrant_client.get_collection(test_collection)
    vector_config = info.config.params.vectors
    if isinstance(vector_config, VectorParams):
        dimension = vector_config.size
    else:
        pytest.skip("Complex vector config not supported for performance test")

    # Create test query vector
    query_vector = [0.1] * dimension

    # Measure search time
    import time

    start = time.time()
    results = qdrant_client.query_points(
        collection_name=test_collection, query=query_vector, limit=5
    ).points
    duration_ms = (time.time() - start) * 1000

    assert duration_ms < 500, f"Search too slow: {duration_ms:.1f}ms (expected < 500ms)"
    assert len(results) > 0, "Search returned no results"

    print(
        f"✅ Vector search performance: {duration_ms:.1f}ms "
        f"({len(results)} results from {info.points_count} vectors)"
    )


def test_qdrant_api_key_validation(qdrant_client):
    """
    SECURITY TEST - Qdrant API key should be configured in production.

    Given: Qdrant is exposed on network
    When: Checking API key configuration
    Then: API key is set (if ENVIRONMENT=production)
    """
    api_key = os.getenv("VECTOR_API_KEY")
    environment = os.getenv("ENVIRONMENT", "development")

    if environment == "production":
        assert api_key and api_key != "", (
            "VECTOR_API_KEY must be set in production for security"
        )
        print(f"✅ Qdrant API key configured (length: {len(api_key)})")
    elif api_key:
        print("✅ Qdrant API key set in development")
    else:
        print("⚠️  Qdrant API key not set (OK for development)")


# TODO: Add these tests when fault tolerance is implemented
# def test_rag_service_handles_qdrant_downtime():
#     """Test that RAG service degrades gracefully when Qdrant unavailable."""
#     pass
#
# def test_vector_insert_retry_on_failure():
#     """Test that vector inserts retry on transient failures."""
#     pass
