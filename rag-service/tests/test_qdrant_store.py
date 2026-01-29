"""
Comprehensive tests for Qdrant vector store implementation.

Tests initialization, document operations, search, filters, and error handling.
"""

import hashlib
import uuid
from unittest.mock import Mock, patch

import pytest

from config.settings import VectorSettings
from vector_stores.qdrant_store import (
    DEFAULT_BATCH_SIZE,
    DEFAULT_QDRANT_TIMEOUT,
    DEFAULT_SEARCH_LIMIT,
    OPENAI_EMBEDDING_DIMENSION,
    QdrantVectorStore,
)


class MockQdrantClient:
    """Mock Qdrant client for testing."""

    def __init__(self, *args, **kwargs):
        self.collections = Mock()
        self.get_collections_called = False
        self.create_collection_called = False
        self.upsert_called = False
        self.query_points_called = False
        self.delete_called = False
        self.close_called = False

    def get_collections(self):
        """Mock get collections."""
        self.get_collections_called = True
        mock_collection = Mock()
        mock_collection.name = "existing_collection"
        result = Mock()
        result.collections = [mock_collection]
        return result

    def create_collection(self, collection_name, vectors_config):
        """Mock create collection."""
        self.create_collection_called = True
        self.created_collection_name = collection_name
        self.created_vectors_config = vectors_config

    def upsert(self, collection_name, points):
        """Mock upsert."""
        self.upsert_called = True
        self.upserted_collection = collection_name
        self.upserted_points = points
        return Mock()

    def query_points(
        self,
        collection_name,
        query,
        limit,
        query_filter=None,
        with_payload=True,
        with_vectors=False,
    ):
        """Mock query points."""
        self.query_points_called = True
        self.queried_collection = collection_name
        self.query = query
        self.query_limit = limit
        self.query_filter = query_filter

        # Return mock search results
        mock_point1 = Mock()
        mock_point1.id = "test-id-1"
        mock_point1.score = 0.9
        mock_point1.payload = {
            "text": "Test document 1",
            "file_name": "doc1.pdf",
        }

        mock_point2 = Mock()
        mock_point2.id = "test-id-2"
        mock_point2.score = 0.8
        mock_point2.payload = {
            "text": "Test document 2",
            "file_name": "doc2.pdf",
        }

        result = Mock()
        result.points = [mock_point1, mock_point2]
        return result

    def delete(self, collection_name, points_selector):
        """Mock delete."""
        self.delete_called = True
        self.deleted_collection = collection_name
        self.deleted_points = points_selector

    def close(self):
        """Mock close."""
        self.close_called = True

    def get_collection(self, collection_name):
        """Mock get collection info."""
        result = Mock()
        result.points_count = 100
        result.vectors_count = 100
        result.status = "green"
        return result


class TestQdrantVectorStoreInitialization:
    """Test Qdrant vector store initialization."""

    def test_init_with_basic_settings(self):
        """Test initialization with basic settings."""
        settings = VectorSettings(
            enabled=True,
            provider="qdrant",
            host="localhost",
            port=6333,
            collection_name="test_collection",
        )

        store = QdrantVectorStore(settings)

        assert store.client is None  # Not initialized yet
        assert store.host == "localhost"
        assert store.port == 6333
        assert store.collection_name == "test_collection"
        assert store.api_key is None

    def test_init_with_api_key(self):
        """Test initialization with API key."""
        settings = VectorSettings(
            enabled=True,
            provider="qdrant",
            host="localhost",
            port=6333,
            collection_name="test_collection",
            api_key="test-api-key",
        )

        store = QdrantVectorStore(settings)

        assert store.api_key == "test-api-key"

    @pytest.mark.asyncio
    async def test_initialize_creates_client_without_api_key(self):
        """Test initialize creates Qdrant client without API key."""
        settings = VectorSettings(
            enabled=True,
            provider="qdrant",
            host="localhost",
            port=6333,
            collection_name="new_collection",
        )

        store = QdrantVectorStore(settings)

        with patch("vector_stores.qdrant_store.QdrantClient", return_value=MockQdrantClient()):
            await store.initialize()

            assert store.client is not None

    @pytest.mark.asyncio
    async def test_initialize_creates_client_with_api_key(self):
        """Test initialize creates Qdrant client with API key."""
        settings = VectorSettings(
            enabled=True,
            provider="qdrant",
            host="localhost",
            port=6333,
            collection_name="new_collection",
            api_key="test-api-key",
        )

        store = QdrantVectorStore(settings)
        mock_client = MockQdrantClient()

        with patch(
            "vector_stores.qdrant_store.QdrantClient", return_value=mock_client
        ) as mock_qdrant:
            await store.initialize()

            # Should use http:// URL when API key is present
            mock_qdrant.assert_called_once()
            call_kwargs = mock_qdrant.call_args[1]
            assert call_kwargs.get("api_key") == "test-api-key"
            assert call_kwargs.get("timeout") == DEFAULT_QDRANT_TIMEOUT

    @pytest.mark.asyncio
    async def test_initialize_creates_collection_if_not_exists(self):
        """Test initialize creates collection if it doesn't exist."""
        settings = VectorSettings(
            enabled=True,
            provider="qdrant",
            host="localhost",
            port=6333,
            collection_name="new_collection",
        )

        store = QdrantVectorStore(settings)
        mock_client = MockQdrantClient()

        with patch("vector_stores.qdrant_store.QdrantClient", return_value=mock_client):
            with patch("vector_stores.qdrant_store.VectorParams"):
                with patch("vector_stores.qdrant_store.Distance"):
                    await store.initialize()

                    assert mock_client.create_collection_called
                    assert mock_client.created_collection_name == "new_collection"

    @pytest.mark.asyncio
    async def test_initialize_skips_collection_creation_if_exists(self):
        """Test initialize skips collection creation if it already exists."""
        settings = VectorSettings(
            enabled=True,
            provider="qdrant",
            host="localhost",
            port=6333,
            collection_name="existing_collection",
        )

        store = QdrantVectorStore(settings)
        mock_client = MockQdrantClient()

        with patch("vector_stores.qdrant_store.QdrantClient", return_value=mock_client):
            await store.initialize()

            assert not mock_client.create_collection_called

    @pytest.mark.asyncio
    async def test_initialize_raises_on_import_error(self):
        """Test initialize raises ImportError when qdrant-client not installed."""
        settings = VectorSettings(
            enabled=True,
            provider="qdrant",
            host="localhost",
            port=6333,
            collection_name="test_collection",
        )

        store = QdrantVectorStore(settings)

        with patch("vector_stores.qdrant_store.QdrantClient", None):
            with pytest.raises(ImportError, match="qdrant-client package not installed"):
                await store.initialize()


class TestQdrantVectorStoreAddDocuments:
    """Test adding documents to Qdrant."""

    @pytest.mark.asyncio
    async def test_add_documents_single_document(self):
        """Test adding a single document."""
        settings = VectorSettings(
            enabled=True,
            provider="qdrant",
            host="localhost",
            port=6333,
            collection_name="test_collection",
        )

        store = QdrantVectorStore(settings)
        mock_client = MockQdrantClient()
        store.client = mock_client

        texts = ["Test document content"]
        embeddings = [[0.1, 0.2, 0.3]]
        metadata = [{"file_name": "test.pdf"}]

        with patch("vector_stores.qdrant_store.PointStruct"):
            await store.add_documents(texts, embeddings, metadata)

            assert mock_client.upsert_called
            assert mock_client.upserted_collection == "test_collection"

    @pytest.mark.asyncio
    async def test_add_documents_generates_deterministic_ids(self):
        """Test that document IDs are deterministic based on content."""
        settings = VectorSettings(
            enabled=True,
            provider="qdrant",
            host="localhost",
            port=6333,
            collection_name="test_collection",
        )

        store = QdrantVectorStore(settings)
        mock_client = MockQdrantClient()
        store.client = mock_client

        texts = ["Test document"]
        embeddings = [[0.1, 0.2, 0.3]]

        # Calculate expected ID
        text_hash = hashlib.md5(f"{texts[0]}_0".encode(), usedforsecurity=False).hexdigest()
        expected_id = str(uuid.UUID(text_hash))

        captured_points = []

        def capture_upsert(collection_name, points):
            captured_points.extend(points)

        mock_client.upsert = capture_upsert

        with patch("vector_stores.qdrant_store.PointStruct", side_effect=lambda **kwargs: kwargs):
            await store.add_documents(texts, embeddings)

            assert len(captured_points) == 1
            assert captured_points[0]["id"] == expected_id

    @pytest.mark.asyncio
    async def test_add_documents_includes_metadata(self):
        """Test that metadata is included in document payload."""
        settings = VectorSettings(
            enabled=True,
            provider="qdrant",
            host="localhost",
            port=6333,
            collection_name="test_collection",
        )

        store = QdrantVectorStore(settings)
        mock_client = MockQdrantClient()
        store.client = mock_client

        texts = ["Test document"]
        embeddings = [[0.1, 0.2, 0.3]]
        metadata = [{"file_name": "test.pdf", "author": "John Doe"}]

        captured_points = []

        def capture_upsert(collection_name, points):
            captured_points.extend(points)

        mock_client.upsert = capture_upsert

        with patch("vector_stores.qdrant_store.PointStruct", side_effect=lambda **kwargs: kwargs):
            await store.add_documents(texts, embeddings, metadata)

            assert len(captured_points) == 1
            assert captured_points[0]["payload"]["file_name"] == "test.pdf"
            assert captured_points[0]["payload"]["author"] == "John Doe"
            assert captured_points[0]["payload"]["text"] == "Test document"

    @pytest.mark.asyncio
    async def test_add_documents_batches_large_uploads(self):
        """Test that large document uploads are batched."""
        settings = VectorSettings(
            enabled=True,
            provider="qdrant",
            host="localhost",
            port=6333,
            collection_name="test_collection",
        )

        store = QdrantVectorStore(settings)
        mock_client = MockQdrantClient()
        store.client = mock_client

        # Create more than DEFAULT_BATCH_SIZE documents
        num_docs = DEFAULT_BATCH_SIZE + 50
        texts = [f"Document {i}" for i in range(num_docs)]
        embeddings = [[0.1, 0.2, 0.3] for _ in range(num_docs)]

        upsert_call_count = 0

        def count_upserts(collection_name, points):
            nonlocal upsert_call_count
            upsert_call_count += 1

        mock_client.upsert = count_upserts

        with patch("vector_stores.qdrant_store.PointStruct", side_effect=lambda **kwargs: kwargs):
            await store.add_documents(texts, embeddings)

            # Should be called twice (100 + 50)
            assert upsert_call_count == 2

    @pytest.mark.asyncio
    async def test_add_documents_raises_if_client_not_initialized(self):
        """Test add_documents raises RuntimeError if client not initialized."""
        settings = VectorSettings(
            enabled=True,
            provider="qdrant",
            host="localhost",
            port=6333,
            collection_name="test_collection",
        )

        store = QdrantVectorStore(settings)
        # Don't initialize client
        store.client = None

        texts = ["Test"]
        embeddings = [[0.1, 0.2, 0.3]]

        with pytest.raises(RuntimeError, match="Qdrant client not initialized"):
            await store.add_documents(texts, embeddings)

    @pytest.mark.asyncio
    async def test_add_documents_without_metadata(self):
        """Test adding documents without metadata."""
        settings = VectorSettings(
            enabled=True,
            provider="qdrant",
            host="localhost",
            port=6333,
            collection_name="test_collection",
        )

        store = QdrantVectorStore(settings)
        mock_client = MockQdrantClient()
        store.client = mock_client

        texts = ["Test document"]
        embeddings = [[0.1, 0.2, 0.3]]

        captured_points = []

        def capture_upsert(collection_name, points):
            captured_points.extend(points)

        mock_client.upsert = capture_upsert

        with patch("vector_stores.qdrant_store.PointStruct", side_effect=lambda **kwargs: kwargs):
            await store.add_documents(texts, embeddings, metadata=None)

            assert len(captured_points) == 1
            assert captured_points[0]["payload"]["text"] == "Test document"


class TestQdrantVectorStoreSearch:
    """Test Qdrant vector store search functionality."""

    @pytest.mark.asyncio
    async def test_search_returns_results(self):
        """Test search returns results from Qdrant."""
        settings = VectorSettings(
            enabled=True,
            provider="qdrant",
            host="localhost",
            port=6333,
            collection_name="test_collection",
        )

        store = QdrantVectorStore(settings)
        mock_client = MockQdrantClient()
        store.client = mock_client

        query_embedding = [0.1, 0.2, 0.3]

        results = await store.search(query_embedding, limit=5)

        assert len(results) > 0
        assert mock_client.query_points_called

    @pytest.mark.asyncio
    async def test_search_filters_by_similarity_threshold(self):
        """Test search filters results by similarity threshold."""
        settings = VectorSettings(
            enabled=True,
            provider="qdrant",
            host="localhost",
            port=6333,
            collection_name="test_collection",
        )

        store = QdrantVectorStore(settings)
        mock_client = MockQdrantClient()
        store.client = mock_client

        query_embedding = [0.1, 0.2, 0.3]

        # Test with high threshold that filters out low-scoring results
        results = await store.search(query_embedding, limit=10, similarity_threshold=0.95)

        # Should have fewer results due to threshold
        assert all(doc["similarity"] >= 0.95 for doc in results)

    @pytest.mark.asyncio
    async def test_search_respects_limit(self):
        """Test search respects the limit parameter."""
        settings = VectorSettings(
            enabled=True,
            provider="qdrant",
            host="localhost",
            port=6333,
            collection_name="test_collection",
        )

        store = QdrantVectorStore(settings)
        mock_client = MockQdrantClient()
        store.client = mock_client

        query_embedding = [0.1, 0.2, 0.3]

        results = await store.search(query_embedding, limit=1)

        assert len(results) <= 1

    @pytest.mark.asyncio
    async def test_search_returns_empty_if_client_not_initialized(self):
        """Test search returns empty list if client not initialized."""
        settings = VectorSettings(
            enabled=True,
            provider="qdrant",
            host="localhost",
            port=6333,
            collection_name="test_collection",
        )

        store = QdrantVectorStore(settings)
        store.client = None

        query_embedding = [0.1, 0.2, 0.3]

        results = await store.search(query_embedding)

        assert results == []

    @pytest.mark.asyncio
    async def test_search_handles_errors_gracefully(self):
        """Test search handles errors and returns empty list."""
        settings = VectorSettings(
            enabled=True,
            provider="qdrant",
            host="localhost",
            port=6333,
            collection_name="test_collection",
        )

        store = QdrantVectorStore(settings)
        mock_client = Mock()
        mock_client.query_points = Mock(side_effect=Exception("Search failed"))
        store.client = mock_client

        query_embedding = [0.1, 0.2, 0.3]

        results = await store.search(query_embedding)

        assert results == []

    @pytest.mark.asyncio
    async def test_search_includes_metadata_in_results(self):
        """Test search includes metadata in returned results."""
        settings = VectorSettings(
            enabled=True,
            provider="qdrant",
            host="localhost",
            port=6333,
            collection_name="test_collection",
        )

        store = QdrantVectorStore(settings)
        mock_client = MockQdrantClient()
        store.client = mock_client

        query_embedding = [0.1, 0.2, 0.3]

        results = await store.search(query_embedding, limit=5)

        assert len(results) > 0
        for result in results:
            assert "content" in result
            assert "similarity" in result
            assert "metadata" in result
            assert "id" in result
            assert "namespace" in result

    @pytest.mark.asyncio
    async def test_search_sorts_by_similarity(self):
        """Test search results are sorted by similarity score."""
        settings = VectorSettings(
            enabled=True,
            provider="qdrant",
            host="localhost",
            port=6333,
            collection_name="test_collection",
        )

        store = QdrantVectorStore(settings)

        # Create custom mock client that returns unsorted results
        class CustomMockClient:
            def __init__(self):
                self.query_points_called = 0

            def query_points(
                self,
                collection_name,
                query,
                limit,
                query_filter=None,
                with_payload=True,
                with_vectors=False,
            ):
                self.query_points_called += 1

                # Return different results for namespace query vs default query
                if query_filter is not None:
                    # Namespace query - return one document
                    mock_point1 = Mock()
                    mock_point1.id = "metric-1"
                    mock_point1.score = 0.6  # Lower score
                    mock_point1.payload = {
                        "text": "Metric doc",
                        "file_name": "metric.pdf",
                        "namespace": "metric",
                    }

                    result = Mock()
                    result.points = [mock_point1]
                    return result
                else:
                    # Default query - return unsorted results
                    mock_point2 = Mock()
                    mock_point2.id = "test-id-2"
                    mock_point2.score = 0.95  # Higher score
                    mock_point2.payload = {"text": "Doc 2", "file_name": "doc2.pdf"}

                    mock_point3 = Mock()
                    mock_point3.id = "test-id-3"
                    mock_point3.score = 0.8  # Middle score
                    mock_point3.payload = {"text": "Doc 3", "file_name": "doc3.pdf"}

                    result = Mock()
                    result.points = [mock_point2, mock_point3]
                    return result

        store.client = CustomMockClient()

        query_embedding = [0.1, 0.2, 0.3]

        results = await store.search(query_embedding, limit=10)

        # Verify results are sorted by similarity (highest first)
        # Expected order after sorting: 0.95, 0.8, 0.6
        assert len(results) >= 2
        for i in range(len(results) - 1):
            assert results[i]["similarity"] >= results[i + 1]["similarity"]


class TestQdrantVectorStoreDiversification:
    """Test result diversification logic."""

    def test_diversify_results_empty(self):
        """Test diversification with empty results."""
        settings = VectorSettings(
            enabled=True,
            provider="qdrant",
            host="localhost",
            port=6333,
            collection_name="test_collection",
        )

        store = QdrantVectorStore(settings)

        diversified = store._diversify_results([], limit=5)

        assert diversified == []

    def test_diversify_results_under_limit(self):
        """Test diversification when results under limit."""
        settings = VectorSettings(
            enabled=True,
            provider="qdrant",
            host="localhost",
            port=6333,
            collection_name="test_collection",
        )

        store = QdrantVectorStore(settings)

        documents = [
            {"content": "Doc 1", "similarity": 0.9, "metadata": {"file_name": "doc1.pdf"}},
            {"content": "Doc 2", "similarity": 0.8, "metadata": {"file_name": "doc2.pdf"}},
        ]

        diversified = store._diversify_results(documents, limit=5)

        assert len(diversified) == 2

    def test_diversify_results_round_robin(self):
        """Test diversification uses round-robin from different documents."""
        settings = VectorSettings(
            enabled=True,
            provider="qdrant",
            host="localhost",
            port=6333,
            collection_name="test_collection",
        )

        store = QdrantVectorStore(settings)

        # Multiple chunks from same document
        documents = [
            {"content": "Doc1 Chunk1", "similarity": 0.95, "metadata": {"file_name": "doc1.pdf"}},
            {"content": "Doc1 Chunk2", "similarity": 0.90, "metadata": {"file_name": "doc1.pdf"}},
            {"content": "Doc1 Chunk3", "similarity": 0.85, "metadata": {"file_name": "doc1.pdf"}},
            {"content": "Doc2 Chunk1", "similarity": 0.80, "metadata": {"file_name": "doc2.pdf"}},
            {"content": "Doc2 Chunk2", "similarity": 0.75, "metadata": {"file_name": "doc2.pdf"}},
        ]

        diversified = store._diversify_results(documents, limit=4)

        # Should get 2 from each document (round-robin)
        assert len(diversified) == 4
        file_names = [doc["metadata"]["file_name"] for doc in diversified]
        assert file_names.count("doc1.pdf") == 2
        assert file_names.count("doc2.pdf") == 2

    def test_diversify_results_preserves_similarity_order_within_document(self):
        """Test diversification preserves similarity order within each document."""
        settings = VectorSettings(
            enabled=True,
            provider="qdrant",
            host="localhost",
            port=6333,
            collection_name="test_collection",
        )

        store = QdrantVectorStore(settings)

        documents = [
            {"content": "Doc1 Chunk2", "similarity": 0.7, "metadata": {"file_name": "doc1.pdf"}},
            {"content": "Doc1 Chunk1", "similarity": 0.9, "metadata": {"file_name": "doc1.pdf"}},
            {"content": "Doc1 Chunk3", "similarity": 0.5, "metadata": {"file_name": "doc1.pdf"}},
        ]

        diversified = store._diversify_results(documents, limit=3)

        # First chunk should have highest similarity
        assert diversified[0]["similarity"] == 0.9

    def test_diversify_results_handles_missing_file_name(self):
        """Test diversification handles documents without file_name."""
        settings = VectorSettings(
            enabled=True,
            provider="qdrant",
            host="localhost",
            port=6333,
            collection_name="test_collection",
        )

        store = QdrantVectorStore(settings)

        documents = [
            {"content": "Doc 1", "similarity": 0.9, "metadata": {}},
            {"content": "Doc 2", "similarity": 0.8, "metadata": {}},
        ]

        diversified = store._diversify_results(documents, limit=5)

        # Should group under "Unknown" file name
        assert len(diversified) > 0


class TestQdrantVectorStoreDeleteDocuments:
    """Test deleting documents from Qdrant."""

    @pytest.mark.asyncio
    async def test_delete_documents_single(self):
        """Test deleting a single document."""
        settings = VectorSettings(
            enabled=True,
            provider="qdrant",
            host="localhost",
            port=6333,
            collection_name="test_collection",
        )

        store = QdrantVectorStore(settings)
        mock_client = MockQdrantClient()
        store.client = mock_client

        document_ids = ["test-id-1"]

        await store.delete_documents(document_ids)

        assert mock_client.delete_called
        assert mock_client.deleted_collection == "test_collection"
        assert mock_client.deleted_points == document_ids

    @pytest.mark.asyncio
    async def test_delete_documents_multiple(self):
        """Test deleting multiple documents."""
        settings = VectorSettings(
            enabled=True,
            provider="qdrant",
            host="localhost",
            port=6333,
            collection_name="test_collection",
        )

        store = QdrantVectorStore(settings)
        mock_client = MockQdrantClient()
        store.client = mock_client

        document_ids = ["test-id-1", "test-id-2", "test-id-3"]

        await store.delete_documents(document_ids)

        assert mock_client.delete_called
        assert len(mock_client.deleted_points) == 3

    @pytest.mark.asyncio
    async def test_delete_documents_raises_if_client_not_initialized(self):
        """Test delete raises RuntimeError if client not initialized."""
        settings = VectorSettings(
            enabled=True,
            provider="qdrant",
            host="localhost",
            port=6333,
            collection_name="test_collection",
        )

        store = QdrantVectorStore(settings)
        store.client = None

        document_ids = ["test-id-1"]

        with pytest.raises(RuntimeError, match="Qdrant client not initialized"):
            await store.delete_documents(document_ids)


class TestQdrantVectorStoreClose:
    """Test closing Qdrant connection."""

    @pytest.mark.asyncio
    async def test_close_client(self):
        """Test closing the Qdrant client."""
        settings = VectorSettings(
            enabled=True,
            provider="qdrant",
            host="localhost",
            port=6333,
            collection_name="test_collection",
        )

        store = QdrantVectorStore(settings)
        mock_client = MockQdrantClient()
        store.client = mock_client

        await store.close()

        assert mock_client.close_called

    @pytest.mark.asyncio
    async def test_close_without_client(self):
        """Test close handles case when client is None."""
        settings = VectorSettings(
            enabled=True,
            provider="qdrant",
            host="localhost",
            port=6333,
            collection_name="test_collection",
        )

        store = QdrantVectorStore(settings)
        store.client = None

        # Should not raise
        await store.close()


class TestQdrantVectorStoreGetStats:
    """Test getting collection statistics."""

    @pytest.mark.asyncio
    async def test_get_stats_returns_collection_info(self):
        """Test get_stats returns collection statistics."""
        settings = VectorSettings(
            enabled=True,
            provider="qdrant",
            host="localhost",
            port=6333,
            collection_name="test_collection",
        )

        store = QdrantVectorStore(settings)
        mock_client = MockQdrantClient()
        store.client = mock_client

        stats = await store.get_stats()

        assert "total_vector_count" in stats
        assert "vectors_count" in stats
        assert "status" in stats
        assert stats["total_vector_count"] == 100
        assert stats["status"] == "green"

    @pytest.mark.asyncio
    async def test_get_stats_handles_uninitialized_client(self):
        """Test get_stats handles case when client not initialized."""
        settings = VectorSettings(
            enabled=True,
            provider="qdrant",
            host="localhost",
            port=6333,
            collection_name="test_collection",
        )

        store = QdrantVectorStore(settings)
        store.client = None

        stats = await store.get_stats()

        assert "error" in stats
        assert stats["error"] == "Client not initialized"

    @pytest.mark.asyncio
    async def test_get_stats_handles_errors(self):
        """Test get_stats handles errors gracefully."""
        settings = VectorSettings(
            enabled=True,
            provider="qdrant",
            host="localhost",
            port=6333,
            collection_name="test_collection",
        )

        store = QdrantVectorStore(settings)
        mock_client = Mock()
        mock_client.get_collection = Mock(side_effect=Exception("Connection failed"))
        store.client = mock_client

        stats = await store.get_stats()

        assert "error" in stats


class TestQdrantVectorStoreConstants:
    """Test module constants."""

    def test_default_timeout_constant(self):
        """Test DEFAULT_QDRANT_TIMEOUT is set correctly."""
        assert DEFAULT_QDRANT_TIMEOUT == 60

    def test_embedding_dimension_constant(self):
        """Test OPENAI_EMBEDDING_DIMENSION is set correctly."""
        assert OPENAI_EMBEDDING_DIMENSION == 1536

    def test_batch_size_constant(self):
        """Test DEFAULT_BATCH_SIZE is set correctly."""
        assert DEFAULT_BATCH_SIZE == 100

    def test_search_limit_constant(self):
        """Test DEFAULT_SEARCH_LIMIT is set correctly."""
        assert DEFAULT_SEARCH_LIMIT == 100
