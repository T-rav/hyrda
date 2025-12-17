"""Comprehensive tests for QdrantVectorStore.

Tests cover:
- Initialization with various configurations
- Document operations (add, delete)
- Search functionality
- Result diversification
- Error handling
- Collection management
- Statistics retrieval
"""
# ruff: noqa: SIM117

from unittest.mock import MagicMock, patch

import pytest

from services.vector_stores.qdrant_store import QdrantVectorStore

# Mock Qdrant models before importing the store
mock_distance = MagicMock()
mock_distance.COSINE = "COSINE"

mock_qdrant_models = {
    "Distance": mock_distance,
    "VectorParams": MagicMock,
    "PointStruct": MagicMock,
    "Filter": MagicMock,
    "FieldCondition": MagicMock,
    "MatchValue": MagicMock,
}


@pytest.fixture(autouse=True)
def mock_qdrant_imports():
    """Mock Qdrant imports for all tests."""
    with patch.dict("sys.modules", {
        "qdrant_client": MagicMock(),
        "qdrant_client.models": MagicMock(**mock_qdrant_models),
    }):
        yield


class TestQdrantVectorStoreInitialization:
    """Test QdrantVectorStore initialization."""

    @pytest.fixture
    def mock_settings(self):
        """Create mock VectorSettings."""
        settings = MagicMock()
        settings.collection_name = "test_collection"
        settings.host = "localhost"
        settings.port = 6333
        settings.api_key = None
        return settings

    def test_initialization_without_api_key(self, mock_settings):
        """Test initialization without API key."""
        # Import at top level

        store = QdrantVectorStore(mock_settings)

        assert store.host == "localhost"
        assert store.port == 6333
        assert store.api_key is None
        assert store.collection_name == "test_collection"
        assert store.client is None

    def test_initialization_with_api_key(self):
        """Test initialization with API key."""
        # Import at top level

        settings = MagicMock()
        settings.collection_name = "secure_collection"
        settings.host = "cloud.qdrant.io"
        settings.port = 443
        settings.api_key = "test-api-key"

        store = QdrantVectorStore(settings)

        assert store.host == "cloud.qdrant.io"
        assert store.port == 443
        assert store.api_key == "test-api-key"
        assert store.collection_name == "secure_collection"

    def test_initialization_uses_settings_defaults(self):
        """Test that initialization uses default values from settings."""
        # Import at top level

        settings = MagicMock(spec=["collection_name"])  # Only collection_name attribute
        settings.collection_name = "test"

        store = QdrantVectorStore(settings)

        assert store.host == "localhost"
        assert store.port == 6333
        assert store.api_key is None


class TestQdrantVectorStoreAsyncInitialize:
    """Test async initialize method."""

    @pytest.fixture
    def mock_settings(self):
        """Create mock VectorSettings."""
        settings = MagicMock()
        settings.collection_name = "test_collection"
        settings.host = "localhost"
        settings.port = 6333
        settings.api_key = None
        return settings

    @pytest.fixture
    def store(self, mock_settings):
        """Create QdrantVectorStore instance."""
        # Import at top level

        return QdrantVectorStore(mock_settings)

    @pytest.mark.asyncio
    async def test_initialize_creates_client_without_api_key(self, store):
        """Test that initialize creates Qdrant client without API key."""
        mock_client = MagicMock()
        mock_collections = MagicMock()
        mock_collections.collections = []
        mock_client.get_collections.return_value = mock_collections

        with patch("services.vector_stores.qdrant_store.QdrantClient", return_value=mock_client):
            await store.initialize()

            assert store.client == mock_client

    @pytest.mark.asyncio
    async def test_initialize_creates_client_with_api_key(self, mock_settings):
        """Test that initialize creates Qdrant client with API key."""
        # Import at top level

        mock_settings.api_key = "test-api-key"
        store = QdrantVectorStore(mock_settings)

        mock_client = MagicMock()
        mock_collections = MagicMock()
        mock_collections.collections = []
        mock_client.get_collections.return_value = mock_collections

        with patch("services.vector_stores.qdrant_store.QdrantClient", return_value=mock_client) as mock_qdrant_class:
            await store.initialize()

            mock_qdrant_class.assert_called_once_with(
                url="http://localhost:6333",
                api_key="test-api-key",
                timeout=60,
            )

    @pytest.mark.asyncio
    async def test_initialize_creates_collection_if_missing(self, store):
        """Test that initialize creates collection if it doesn't exist."""
        mock_client = MagicMock()
        mock_collections = MagicMock()
        mock_collections.collections = []
        mock_client.get_collections.return_value = mock_collections
        mock_client.create_collection = MagicMock()

        with patch("services.vector_stores.qdrant_store.QdrantClient", return_value=mock_client):
            with patch("services.vector_stores.qdrant_store.VectorParams") as mock_vector_params:
                await store.initialize()

                mock_client.create_collection.assert_called_once()
                mock_vector_params.assert_called_once()

    @pytest.mark.asyncio
    async def test_initialize_skips_collection_creation_if_exists(self, store):
        """Test that initialize skips creating collection if it exists."""
        mock_client = MagicMock()
        mock_collection = MagicMock()
        mock_collection.name = "test_collection"
        mock_collections = MagicMock()
        mock_collections.collections = [mock_collection]
        mock_client.get_collections.return_value = mock_collections
        mock_client.create_collection = MagicMock()

        with patch("services.vector_stores.qdrant_store.QdrantClient", return_value=mock_client):
            await store.initialize()

            mock_client.create_collection.assert_not_called()

    @pytest.mark.asyncio
    async def test_initialize_raises_import_error_if_qdrant_not_installed(self, store):
        """Test that initialize raises ImportError if qdrant-client not installed."""
        with patch("services.vector_stores.qdrant_store.QdrantClient", None):
            with pytest.raises(ImportError, match="qdrant-client package not installed"):
                await store.initialize()

    @pytest.mark.asyncio
    async def test_initialize_raises_on_connection_error(self, store):
        """Test that initialize raises exception on connection error."""
        with patch("services.vector_stores.qdrant_store.QdrantClient", side_effect=ConnectionError("Connection failed")):
            with pytest.raises(ConnectionError):
                await store.initialize()


class TestQdrantVectorStoreAddDocuments:
    """Test add_documents method."""

    @pytest.fixture
    def store(self):
        """Create initialized QdrantVectorStore."""
        # Import at top level

        settings = MagicMock()
        settings.collection_name = "test_collection"
        settings.host = "localhost"
        settings.port = 6333
        settings.api_key = None

        store = QdrantVectorStore(settings)
        store.client = MagicMock()
        return store

    @pytest.mark.asyncio
    async def test_add_documents_basic(self, store):
        """Test adding documents with basic inputs."""
        texts = ["doc1", "doc2"]
        embeddings = [[0.1, 0.2], [0.3, 0.4]]

        with patch("services.vector_stores.qdrant_store.PointStruct") as mock_point_struct:
            await store.add_documents(texts, embeddings)

            assert mock_point_struct.call_count == 2
            store.client.upsert.assert_called_once()

    @pytest.mark.asyncio
    async def test_add_documents_with_metadata(self, store):
        """Test adding documents with metadata."""
        texts = ["doc1"]
        embeddings = [[0.1, 0.2]]
        metadata = [{"source": "test.txt", "author": "user1"}]

        with patch("services.vector_stores.qdrant_store.PointStruct") as mock_point_struct:
            await store.add_documents(texts, embeddings, metadata)

            call_args = mock_point_struct.call_args_list[0]
            payload = call_args[1]["payload"]
            assert payload["text"] == "doc1"
            assert payload["source"] == "test.txt"
            assert payload["author"] == "user1"

    @pytest.mark.asyncio
    async def test_add_documents_generates_deterministic_ids(self, store):
        """Test that document IDs are deterministic based on content."""
        texts = ["same_text"]
        embeddings = [[0.1, 0.2]]

        generated_ids = []

        def capture_id(*args, **kwargs):
            generated_ids.append(kwargs.get("id"))
            return MagicMock()

        with patch("services.vector_stores.qdrant_store.PointStruct", side_effect=capture_id):
            await store.add_documents(texts, embeddings)
            await store.add_documents(texts, embeddings)

            # Same text should generate same ID
            assert len(generated_ids) == 2
            assert generated_ids[0] == generated_ids[1]

    @pytest.mark.asyncio
    async def test_add_documents_batches_correctly(self, store):
        """Test that large document sets are batched."""
        texts = [f"doc{i}" for i in range(250)]
        embeddings = [[0.1, 0.2] for _ in range(250)]

        with patch("services.vector_stores.qdrant_store.PointStruct", return_value=MagicMock()):
            await store.add_documents(texts, embeddings)

            # Should batch into 3 calls: 100, 100, 50
            assert store.client.upsert.call_count == 3

    @pytest.mark.asyncio
    async def test_add_documents_without_metadata(self, store):
        """Test adding documents without metadata."""
        texts = ["doc1"]
        embeddings = [[0.1, 0.2]]

        with patch("services.vector_stores.qdrant_store.PointStruct") as mock_point_struct:
            await store.add_documents(texts, embeddings, metadata=None)

            call_args = mock_point_struct.call_args_list[0]
            payload = call_args[1]["payload"]
            assert payload["text"] == "doc1"
            assert len(payload) == 1  # Only text field

    @pytest.mark.asyncio
    async def test_add_documents_raises_if_client_not_initialized(self, store):
        """Test that add_documents raises error if client not initialized."""
        store.client = None
        texts = ["doc1"]
        embeddings = [[0.1, 0.2]]

        with pytest.raises(RuntimeError, match="Qdrant client not initialized"):
            await store.add_documents(texts, embeddings)

    @pytest.mark.asyncio
    async def test_add_documents_raises_on_upsert_error(self, store):
        """Test that add_documents raises exception on upsert error."""
        texts = ["doc1"]
        embeddings = [[0.1, 0.2]]
        store.client.upsert.side_effect = Exception("Upsert failed")

        with patch("services.vector_stores.qdrant_store.PointStruct", return_value=MagicMock()):
            with pytest.raises(Exception, match="Upsert failed"):
                await store.add_documents(texts, embeddings)


class TestQdrantVectorStoreSearch:
    """Test search method."""

    @pytest.fixture
    def store(self):
        """Create initialized QdrantVectorStore."""
        # Import at top level

        settings = MagicMock()
        settings.collection_name = "test_collection"
        settings.host = "localhost"
        settings.port = 6333
        settings.api_key = None

        store = QdrantVectorStore(settings)
        store.client = MagicMock()
        return store

    @pytest.fixture
    def mock_search_result(self):
        """Create mock search results."""
        def create_result(score, text, metadata=None, doc_id="test-id"):
            result = MagicMock()
            result.score = score
            result.id = doc_id
            result.payload = {"text": text}
            if metadata:
                result.payload.update(metadata)
            return result
        return create_result

    @pytest.mark.asyncio
    async def test_search_returns_empty_if_client_not_initialized(self):
        """Test that search returns empty list if client not initialized."""
        # Import at top level

        settings = MagicMock()
        settings.collection_name = "test"
        store = QdrantVectorStore(settings)
        store.client = None

        results = await store.search([0.1, 0.2], limit=5)

        assert results == []

    @pytest.mark.asyncio
    async def test_search_queries_metric_namespace(self, store, mock_search_result):
        """Test that search queries the metric namespace."""
        mock_response = MagicMock()
        mock_response.points = [mock_search_result(0.9, "result1")]
        store.client.query_points.return_value = mock_response

        with patch("services.vector_stores.qdrant_store.Filter"):
            with patch("services.vector_stores.qdrant_store.FieldCondition"):
                await store.search([0.1, 0.2], limit=10)

                # Should be called twice: once for metric namespace, once for default
                assert store.client.query_points.call_count == 2

    @pytest.mark.asyncio
    async def test_search_filters_by_similarity_threshold(self, store, mock_search_result):
        """Test that search filters results by similarity threshold."""
        mock_response_metric = MagicMock()
        mock_response_metric.points = [
            mock_search_result(0.9, "high_score"),
            mock_search_result(0.5, "low_score"),
        ]
        mock_response_default = MagicMock()
        mock_response_default.points = []

        store.client.query_points.side_effect = [mock_response_metric, mock_response_default]

        with patch("services.vector_stores.qdrant_store.Filter"):
            with patch("services.vector_stores.qdrant_store.FieldCondition"):
                results = await store.search([0.1, 0.2], limit=10, similarity_threshold=0.7)

                # Should only return high_score result
                assert len(results) == 1
                assert results[0]["similarity"] == 0.9

    @pytest.mark.asyncio
    async def test_search_sorts_by_similarity(self, store, mock_search_result):
        """Test that search results are sorted by similarity."""
        mock_response_metric = MagicMock()
        mock_response_metric.points = [
            mock_search_result(0.7, "medium", doc_id="id1"),
            mock_search_result(0.9, "high", doc_id="id2"),
        ]
        mock_response_default = MagicMock()
        mock_response_default.points = [
            mock_search_result(0.8, "good", doc_id="id3"),
        ]

        store.client.query_points.side_effect = [mock_response_metric, mock_response_default]

        with patch("services.vector_stores.qdrant_store.Filter"):
            with patch("services.vector_stores.qdrant_store.FieldCondition"):
                with patch.object(store, "_diversify_results", side_effect=lambda x, _: x):
                    results = await store.search([0.1, 0.2], limit=10)

                    # Should be sorted highest to lowest
                    assert results[0]["similarity"] == 0.9
                    assert results[1]["similarity"] == 0.8
                    assert results[2]["similarity"] == 0.7

    @pytest.mark.asyncio
    async def test_search_respects_limit(self, store, mock_search_result):
        """Test that search respects the limit parameter."""
        mock_response_metric = MagicMock()
        mock_response_metric.points = [
            mock_search_result(0.9, f"doc{i}", doc_id=f"id{i}")
            for i in range(10)
        ]
        mock_response_default = MagicMock()
        mock_response_default.points = []

        store.client.query_points.side_effect = [mock_response_metric, mock_response_default]

        with patch("services.vector_stores.qdrant_store.Filter"):
            with patch("services.vector_stores.qdrant_store.FieldCondition"):
                with patch.object(store, "_diversify_results", side_effect=lambda x, lim: x[:lim]):
                    results = await store.search([0.1, 0.2], limit=5)

                    assert len(results) <= 5

    @pytest.mark.asyncio
    async def test_search_includes_metadata(self, store, mock_search_result):
        """Test that search results include metadata."""
        mock_response_metric = MagicMock()
        mock_response_metric.points = [
            mock_search_result(0.9, "text", {"source": "test.txt"})
        ]
        mock_response_default = MagicMock()
        mock_response_default.points = []

        store.client.query_points.side_effect = [mock_response_metric, mock_response_default]

        with patch("services.vector_stores.qdrant_store.Filter"):
            with patch("services.vector_stores.qdrant_store.FieldCondition"):
                with patch.object(store, "_diversify_results", side_effect=lambda x, _: x):
                    results = await store.search([0.1, 0.2], limit=10)

                    assert results[0]["metadata"]["source"] == "test.txt"

    @pytest.mark.asyncio
    async def test_search_handles_exceptions(self, store):
        """Test that search handles exceptions gracefully."""
        store.client.query_points.side_effect = Exception("Search failed")

        results = await store.search([0.1, 0.2], limit=5)

        assert results == []

    @pytest.mark.asyncio
    async def test_search_excludes_default_namespace_with_namespace_field(self, store, mock_search_result):
        """Test that default namespace search excludes docs with namespace field."""
        mock_response_metric = MagicMock()
        mock_response_metric.points = []

        # Create results with and without namespace field
        result_with_ns = mock_search_result(0.9, "has_namespace", {"namespace": "metric"})
        result_without_ns = mock_search_result(0.8, "no_namespace", {})

        mock_response_default = MagicMock()
        mock_response_default.points = [result_with_ns, result_without_ns]

        store.client.query_points.side_effect = [mock_response_metric, mock_response_default]

        with patch("services.vector_stores.qdrant_store.Filter"):
            with patch("services.vector_stores.qdrant_store.FieldCondition"):
                with patch.object(store, "_diversify_results", side_effect=lambda x, _: x):
                    results = await store.search([0.1, 0.2], limit=10)

                    # Should only include result without namespace field
                    assert len(results) == 1
                    assert results[0]["content"] == "no_namespace"


class TestQdrantVectorStoreDiversifyResults:
    """Test _diversify_results method."""

    @pytest.fixture
    def store(self):
        """Create QdrantVectorStore instance."""
        # Import at top level

        settings = MagicMock()
        settings.collection_name = "test"
        return QdrantVectorStore(settings)

    def test_diversify_empty_documents(self, store):
        """Test diversification with empty documents."""
        result = store._diversify_results([], 5)
        assert result == []

    def test_diversify_zero_limit(self, store):
        """Test diversification with zero limit."""
        documents = [{"similarity": 0.9, "metadata": {"file_name": "doc1"}}]
        result = store._diversify_results(documents, 0)
        assert result == []

    def test_diversify_single_document(self, store):
        """Test diversification with single document."""
        documents = [
            {"similarity": 0.9, "metadata": {"file_name": "doc1"}},
            {"similarity": 0.8, "metadata": {"file_name": "doc1"}},
        ]
        result = store._diversify_results(documents, 5)
        assert len(result) == 2

    def test_diversify_round_robin_selection(self, store):
        """Test that diversification uses round-robin across files."""
        documents = [
            {"similarity": 0.9, "metadata": {"file_name": "doc1"}, "id": "1"},
            {"similarity": 0.8, "metadata": {"file_name": "doc2"}, "id": "2"},
            {"similarity": 0.7, "metadata": {"file_name": "doc1"}, "id": "3"},
            {"similarity": 0.6, "metadata": {"file_name": "doc2"}, "id": "4"},
        ]
        result = store._diversify_results(documents, 2)

        # Should get one from each file first
        file_names = [r["metadata"]["file_name"] for r in result]
        assert "doc1" in file_names
        assert "doc2" in file_names

    def test_diversify_respects_limit(self, store):
        """Test that diversification respects limit."""
        documents = [
            {"similarity": 0.9, "metadata": {"file_name": f"doc{i}"}}
            for i in range(20)
        ]
        result = store._diversify_results(documents, 5)
        assert len(result) == 5

    def test_diversify_handles_missing_file_name(self, store):
        """Test diversification handles missing file_name in metadata."""
        documents = [
            {"similarity": 0.9, "metadata": {}},
            {"similarity": 0.8, "metadata": {"file_name": "doc1"}},
        ]
        result = store._diversify_results(documents, 5)
        assert len(result) == 2

    def test_diversify_multiple_chunks_same_file(self, store):
        """Test diversification with multiple chunks from same file."""
        documents = [
            {"similarity": 0.9, "metadata": {"file_name": "doc1"}, "chunk": 1},
            {"similarity": 0.8, "metadata": {"file_name": "doc1"}, "chunk": 2},
            {"similarity": 0.7, "metadata": {"file_name": "doc1"}, "chunk": 3},
        ]
        result = store._diversify_results(documents, 5)

        # All chunks should be included, sorted by similarity
        assert len(result) == 3
        assert result[0]["similarity"] == 0.9


class TestQdrantVectorStoreDeleteDocuments:
    """Test delete_documents method."""

    @pytest.fixture
    def store(self):
        """Create initialized QdrantVectorStore."""
        # Import at top level

        settings = MagicMock()
        settings.collection_name = "test_collection"
        store = QdrantVectorStore(settings)
        store.client = MagicMock()
        return store

    @pytest.mark.asyncio
    async def test_delete_documents_basic(self, store):
        """Test deleting documents."""
        document_ids = ["id1", "id2", "id3"]

        await store.delete_documents(document_ids)

        store.client.delete.assert_called_once_with(
            collection_name="test_collection",
            points_selector=document_ids,
        )

    @pytest.mark.asyncio
    async def test_delete_documents_raises_if_client_not_initialized(self, store):
        """Test that delete raises error if client not initialized."""
        store.client = None

        with pytest.raises(RuntimeError, match="Qdrant client not initialized"):
            await store.delete_documents(["id1"])

    @pytest.mark.asyncio
    async def test_delete_documents_raises_on_error(self, store):
        """Test that delete raises exception on error."""
        store.client.delete.side_effect = Exception("Delete failed")

        with pytest.raises(Exception, match="Delete failed"):
            await store.delete_documents(["id1"])

    @pytest.mark.asyncio
    async def test_delete_documents_empty_list(self, store):
        """Test deleting with empty list."""
        await store.delete_documents([])

        store.client.delete.assert_called_once_with(
            collection_name="test_collection",
            points_selector=[],
        )


class TestQdrantVectorStoreClose:
    """Test close method."""

    @pytest.fixture
    def store(self):
        """Create initialized QdrantVectorStore."""
        # Import at top level

        settings = MagicMock()
        settings.collection_name = "test"
        store = QdrantVectorStore(settings)
        store.client = MagicMock()
        return store

    @pytest.mark.asyncio
    async def test_close_closes_client(self, store):
        """Test that close calls client.close()."""
        await store.close()

        store.client.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_close_handles_no_client(self):
        """Test that close handles missing client gracefully."""
        # Import at top level

        settings = MagicMock()
        settings.collection_name = "test"
        store = QdrantVectorStore(settings)
        store.client = None

        # Should not raise
        await store.close()


class TestQdrantVectorStoreGetStats:
    """Test get_stats method."""

    @pytest.fixture
    def store(self):
        """Create initialized QdrantVectorStore."""
        # Import at top level

        settings = MagicMock()
        settings.collection_name = "test_collection"
        store = QdrantVectorStore(settings)
        store.client = MagicMock()
        return store

    @pytest.mark.asyncio
    async def test_get_stats_returns_collection_info(self, store):
        """Test that get_stats returns collection information."""
        mock_collection_info = MagicMock()
        mock_collection_info.points_count = 1000
        mock_collection_info.vectors_count = 1000
        mock_collection_info.status = "green"

        store.client.get_collection.return_value = mock_collection_info

        stats = await store.get_stats()

        assert stats["total_vector_count"] == 1000
        assert stats["vectors_count"] == 1000
        assert stats["status"] == "green"

    @pytest.mark.asyncio
    async def test_get_stats_returns_error_if_client_not_initialized(self):
        """Test that get_stats returns error if client not initialized."""
        # Import at top level

        settings = MagicMock()
        settings.collection_name = "test"
        store = QdrantVectorStore(settings)
        store.client = None

        stats = await store.get_stats()

        assert "error" in stats
        assert stats["error"] == "Client not initialized"

    @pytest.mark.asyncio
    async def test_get_stats_handles_exceptions(self, store):
        """Test that get_stats handles exceptions gracefully."""
        store.client.get_collection.side_effect = Exception("Connection lost")

        stats = await store.get_stats()

        assert "error" in stats
        assert "Connection lost" in stats["error"]


class TestQdrantVectorStoreEdgeCases:
    """Test edge cases and error scenarios."""

    @pytest.fixture
    def store(self):
        """Create initialized QdrantVectorStore."""
        # Import at top level

        settings = MagicMock()
        settings.collection_name = "test_collection"
        store = QdrantVectorStore(settings)
        store.client = MagicMock()
        return store

    @pytest.mark.asyncio
    async def test_add_documents_with_empty_lists(self, store):
        """Test adding empty document lists."""
        with patch("services.vector_stores.qdrant_store.PointStruct"):
            await store.add_documents([], [])

            # Should not call upsert with empty data
            store.client.upsert.assert_not_called()

    @pytest.mark.asyncio
    async def test_search_with_empty_embedding(self, store):
        """Test search with empty embedding vector."""
        mock_response = MagicMock()
        mock_response.points = []
        store.client.query_points.return_value = mock_response

        with patch("services.vector_stores.qdrant_store.Filter"):
            with patch("services.vector_stores.qdrant_store.FieldCondition"):
                results = await store.search([], limit=5)

                # Should handle gracefully
                assert isinstance(results, list)

    def test_diversify_preserves_order_within_file(self, store):
        """Test that diversification preserves similarity order within files."""
        documents = [
            {"similarity": 0.95, "metadata": {"file_name": "doc1"}, "id": "1"},
            {"similarity": 0.90, "metadata": {"file_name": "doc1"}, "id": "2"},
            {"similarity": 0.85, "metadata": {"file_name": "doc1"}, "id": "3"},
        ]
        result = store._diversify_results(documents, 10)

        # Should maintain similarity order
        assert result[0]["id"] == "1"
        assert result[1]["id"] == "2"
        assert result[2]["id"] == "3"

    @pytest.mark.asyncio
    async def test_initialize_with_connection_timeout(self, store):
        """Test initialization handles timeout errors."""
        with patch("services.vector_stores.qdrant_store.QdrantClient", side_effect=TimeoutError("Timeout")):
            with pytest.raises(TimeoutError):
                await store.initialize()
