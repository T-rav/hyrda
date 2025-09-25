"""
Tests for Vector Store implementations.

Tests actual vector store operations and behaviors for different providers.
"""

import asyncio
from unittest.mock import AsyncMock, Mock, patch

import pytest
from pydantic import SecretStr

from bot.services.vector_stores.base import VectorStore
from bot.services.vector_stores.elasticsearch_store import ElasticsearchVectorStore
from bot.services.vector_stores.pinecone_store import PineconeVectorStore
from config.settings import VectorSettings


class TestVectorStoreBase:
    """Test base VectorStore functionality"""

    def test_base_class_initialization(self):
        """Test VectorStore base class initialization"""
        settings = VectorSettings(
            provider="test", collection_name="test-collection"
        )

        # Create a concrete implementation for testing
        class TestVectorStore(VectorStore):
            async def initialize(self):
                pass

            async def add_documents(self, texts, embeddings, metadata=None):
                pass

            async def search(self, query_embedding, limit=5, similarity_threshold=0.7):
                return []

            async def delete_documents(self, document_ids):
                pass

            async def close(self):
                pass

        store = TestVectorStore(settings)
        assert store.settings == settings
        assert store.collection_name == "test-collection"

    def test_abstract_methods_required(self):
        """Test that abstract methods must be implemented"""
        settings = VectorSettings(provider="test", collection_name="test")

        # This should fail because abstract methods aren't implemented
        with pytest.raises(TypeError):
            VectorStore(settings)


class TestElasticsearchVectorStore:
    """Test Elasticsearch vector store implementation"""

    @pytest.fixture
    def elasticsearch_settings(self):
        return VectorSettings(
            provider="elasticsearch",
            url="http://localhost:9200",
            collection_name="test-index",
        )

    @pytest.fixture
    def mock_elasticsearch_client(self):
        mock_client = AsyncMock()
        mock_client.ping = AsyncMock(return_value=True)
        mock_client.indices.exists = AsyncMock(return_value=False)
        mock_client.indices.create = AsyncMock()
        mock_client.index = AsyncMock()
        mock_client.search = AsyncMock()
        mock_client.delete_by_query = AsyncMock()
        mock_client.close = AsyncMock()
        return mock_client

    @pytest.mark.asyncio
    async def test_initialization_success(self, elasticsearch_settings, mock_elasticsearch_client):
        """Test successful Elasticsearch initialization"""
        with patch("elasticsearch.AsyncElasticsearch") as mock_es:
            mock_es.return_value = mock_elasticsearch_client

            store = ElasticsearchVectorStore(elasticsearch_settings)
            await store.initialize()

            assert store.client == mock_elasticsearch_client
            assert store.index_name == "test-index"
            mock_elasticsearch_client.ping.assert_called_once()
            mock_elasticsearch_client.indices.exists.assert_called_once()
            mock_elasticsearch_client.indices.create.assert_called_once()

    @pytest.mark.asyncio
    async def test_initialization_existing_index(self, elasticsearch_settings, mock_elasticsearch_client):
        """Test initialization when index already exists"""
        mock_elasticsearch_client.indices.exists = AsyncMock(return_value=True)

        with patch("elasticsearch.AsyncElasticsearch") as mock_es:
            mock_es.return_value = mock_elasticsearch_client

            store = ElasticsearchVectorStore(elasticsearch_settings)
            await store.initialize()

            mock_elasticsearch_client.indices.create.assert_not_called()

    @pytest.mark.asyncio
    async def test_initialization_missing_package(self, elasticsearch_settings):
        """Test initialization when elasticsearch package is missing"""
        with patch("elasticsearch.AsyncElasticsearch", side_effect=ImportError):
            store = ElasticsearchVectorStore(elasticsearch_settings)

            with pytest.raises(ImportError, match="elasticsearch package not installed"):
                await store.initialize()

    @pytest.mark.asyncio
    async def test_add_documents(self, elasticsearch_settings, mock_elasticsearch_client):
        """Test adding documents to Elasticsearch"""
        with patch("elasticsearch.AsyncElasticsearch") as mock_es:
            mock_es.return_value = mock_elasticsearch_client

            store = ElasticsearchVectorStore(elasticsearch_settings)
            await store.initialize()

            texts = ["Document 1", "Document 2"]
            embeddings = [[0.1, 0.2], [0.3, 0.4]]
            metadata = [{"source": "test1"}, {"source": "test2"}]

            await store.add_documents(texts, embeddings, metadata)

            # Should call index for each document
            assert mock_elasticsearch_client.index.call_count == 2

    @pytest.mark.asyncio
    async def test_search(self, elasticsearch_settings, mock_elasticsearch_client):
        """Test searching for similar documents"""
        # Mock search response
        mock_response = {
            "hits": {
                "hits": [
                    {
                        "_score": 0.95,
                        "_source": {
                            "content": "Test document",
                            "metadata": {"source": "test"}
                        }
                    }
                ]
            }
        }
        mock_elasticsearch_client.search = AsyncMock(return_value=mock_response)

        with patch("elasticsearch.AsyncElasticsearch") as mock_es:
            mock_es.return_value = mock_elasticsearch_client

            store = ElasticsearchVectorStore(elasticsearch_settings)
            await store.initialize()

            query_embedding = [0.1, 0.2, 0.3]
            results = await store.search(query_embedding, limit=5, similarity_threshold=0.7)

            assert len(results) == 1
            assert results[0]["content"] == "Test document"
            assert results[0]["similarity"] >= 0.7
            mock_elasticsearch_client.search.assert_called_once()

    @pytest.mark.asyncio
    async def test_search_no_results(self, elasticsearch_settings, mock_elasticsearch_client):
        """Test search with no results"""
        mock_response = {"hits": {"hits": []}}
        mock_elasticsearch_client.search = AsyncMock(return_value=mock_response)

        with patch("elasticsearch.AsyncElasticsearch") as mock_es:
            mock_es.return_value = mock_elasticsearch_client

            store = ElasticsearchVectorStore(elasticsearch_settings)
            await store.initialize()

            results = await store.search([0.1, 0.2], limit=5)
            assert results == []

    @pytest.mark.asyncio
    async def test_delete_documents(self, elasticsearch_settings, mock_elasticsearch_client):
        """Test deleting documents"""
        with patch("elasticsearch.AsyncElasticsearch") as mock_es:
            mock_es.return_value = mock_elasticsearch_client

            store = ElasticsearchVectorStore(elasticsearch_settings)
            await store.initialize()

            document_ids = ["doc1", "doc2"]
            await store.delete_documents(document_ids)

            mock_elasticsearch_client.delete_by_query.assert_called_once()

    @pytest.mark.asyncio
    async def test_close(self, elasticsearch_settings, mock_elasticsearch_client):
        """Test closing Elasticsearch client"""
        with patch("elasticsearch.AsyncElasticsearch") as mock_es:
            mock_es.return_value = mock_elasticsearch_client

            store = ElasticsearchVectorStore(elasticsearch_settings)
            await store.initialize()
            await store.close()

            mock_elasticsearch_client.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_close_without_client(self, elasticsearch_settings):
        """Test closing when client is None"""
        store = ElasticsearchVectorStore(elasticsearch_settings)
        # Should not raise an exception
        await store.close()


class TestPineconeVectorStore:
    """Test Pinecone vector store implementation"""

    @pytest.fixture
    def pinecone_settings(self):
        return VectorSettings(
            provider="pinecone",
            api_key=SecretStr("test-api-key"),
            environment="test-env",
            collection_name="test-index",
        )

    @pytest.fixture
    def mock_pinecone_client(self):
        mock_client = Mock()
        mock_index = Mock()
        mock_client.Index.return_value = mock_index
        mock_index.upsert = AsyncMock()
        mock_index.query = AsyncMock()
        mock_index.delete = AsyncMock()
        return mock_client, mock_index

    @pytest.mark.asyncio
    async def test_initialization_success(self, pinecone_settings, mock_pinecone_client):
        """Test successful Pinecone initialization"""
        mock_client, mock_index = mock_pinecone_client

        with patch("bot.services.vector_stores.pinecone_store.Pinecone") as mock_pinecone_class:
            mock_pc = Mock()
            mock_pc.Index = Mock(return_value=mock_index)
            mock_pinecone_class.return_value = mock_pc

            store = PineconeVectorStore(pinecone_settings)
            await store.initialize()

            mock_pinecone_class.assert_called_once_with(
                api_key="test-api-key"
            )
            assert store.index == mock_index

    @pytest.mark.asyncio
    async def test_initialization_missing_package(self, pinecone_settings):
        """Test initialization when pinecone package is missing"""
        # Simulate missing pinecone package by setting Pinecone to None
        with patch("bot.services.vector_stores.pinecone_store.Pinecone", None):
            store = PineconeVectorStore(pinecone_settings)

            with pytest.raises(ImportError, match="pinecone package is required"):
                await store.initialize()

    @pytest.mark.asyncio
    async def test_add_documents(self, pinecone_settings, mock_pinecone_client):
        """Test adding documents to Pinecone"""
        mock_client, mock_index = mock_pinecone_client

        with patch("bot.services.vector_stores.pinecone_store.Pinecone") as mock_pinecone_class:
            mock_pc = Mock()
            mock_pc.Index = Mock(return_value=mock_index)
            mock_pinecone_class.return_value = mock_pc

            store = PineconeVectorStore(pinecone_settings)
            await store.initialize()

            texts = ["Document 1", "Document 2"]
            embeddings = [[0.1, 0.2], [0.3, 0.4]]
            metadata = [{"source": "test1"}, {"source": "test2"}]

            await store.add_documents(texts, embeddings, metadata)

            mock_index.upsert.assert_called_once()

    @pytest.mark.asyncio
    async def test_search(self, pinecone_settings, mock_pinecone_client):
        """Test searching for similar documents"""
        mock_client, mock_index = mock_pinecone_client

        # Mock search response
        mock_response = {
            "matches": [
                {
                    "score": 0.95,
                    "metadata": {
                        "content": "Test document",
                        "source": "test"
                    }
                }
            ]
        }
        mock_index.query = AsyncMock(return_value=mock_response)

        with patch("bot.services.vector_stores.pinecone_store.Pinecone") as mock_pinecone_class:
            mock_pc = Mock()
            mock_pc.Index = Mock(return_value=mock_index)
            mock_pinecone_class.return_value = mock_pc

            store = PineconeVectorStore(pinecone_settings)
            await store.initialize()

            query_embedding = [0.1, 0.2, 0.3]
            results = await store.search(query_embedding, limit=5, similarity_threshold=0.7)

            assert len(results) == 1
            assert results[0]["content"] == "Test document"
            assert results[0]["similarity"] >= 0.7
            mock_index.query.assert_called_once()

    @pytest.mark.asyncio
    async def test_search_no_results(self, pinecone_settings, mock_pinecone_client):
        """Test search with no results"""
        mock_client, mock_index = mock_pinecone_client
        mock_response = {"matches": []}
        mock_index.query = AsyncMock(return_value=mock_response)

        with patch("bot.services.vector_stores.pinecone_store.Pinecone") as mock_pinecone_class:
            mock_pc = Mock()
            mock_pc.Index = Mock(return_value=mock_index)
            mock_pinecone_class.return_value = mock_pc

            store = PineconeVectorStore(pinecone_settings)
            await store.initialize()

            results = await store.search([0.1, 0.2], limit=5)
            assert results == []

    @pytest.mark.asyncio
    async def test_delete_documents(self, pinecone_settings, mock_pinecone_client):
        """Test deleting documents"""
        mock_client, mock_index = mock_pinecone_client

        with patch("bot.services.vector_stores.pinecone_store.Pinecone") as mock_pinecone_class:
            mock_pc = Mock()
            mock_pc.Index = Mock(return_value=mock_index)
            mock_pinecone_class.return_value = mock_pc

            store = PineconeVectorStore(pinecone_settings)
            await store.initialize()

            document_ids = ["doc1", "doc2"]
            await store.delete_documents(document_ids)

            mock_index.delete.assert_called_once_with(ids=document_ids)

    @pytest.mark.asyncio
    async def test_close(self, pinecone_settings, mock_pinecone_client):
        """Test closing Pinecone client"""
        mock_client, mock_index = mock_pinecone_client

        with patch("bot.services.vector_stores.pinecone_store.Pinecone") as mock_pinecone_class:
            mock_pc = Mock()
            mock_pc.Index = Mock(return_value=mock_index)
            mock_pinecone_class.return_value = mock_pc

            store = PineconeVectorStore(pinecone_settings)
            await store.initialize()
            # Should not raise an exception
            await store.close()


class TestVectorStoreIntegration:
    """Integration tests for vector store operations"""

    @pytest.mark.asyncio
    async def test_full_document_lifecycle_elasticsearch(self):
        """Test complete document lifecycle with Elasticsearch store"""
        settings = VectorSettings(
            provider="elasticsearch",
            url="http://localhost:9200",
            collection_name="test-lifecycle",
        )

        mock_client = AsyncMock()
        mock_client.ping = AsyncMock(return_value=True)
        mock_client.indices.exists = AsyncMock(return_value=False)
        mock_client.indices.create = AsyncMock()
        mock_client.index = AsyncMock()
        mock_client.search = AsyncMock(return_value={
            "hits": {
                "hits": [
                    {
                        "_score": 0.95,
                        "_source": {
                            "content": "Test document",
                            "metadata": {"source": "lifecycle-test"}
                        }
                    }
                ]
            }
        })
        mock_client.delete_by_query = AsyncMock()
        mock_client.close = AsyncMock()

        with patch("elasticsearch.AsyncElasticsearch") as mock_es:
            mock_es.return_value = mock_client

            store = ElasticsearchVectorStore(settings)

            # Initialize
            await store.initialize()

            # Add documents
            texts = ["Test document"]
            embeddings = [[0.1, 0.2, 0.3]]
            metadata = [{"source": "lifecycle-test"}]

            await store.add_documents(texts, embeddings, metadata)

            # Search
            results = await store.search([0.1, 0.2, 0.3], limit=1)
            assert len(results) == 1
            assert results[0]["content"] == "Test document"

            # Delete
            await store.delete_documents(["test-doc-id"])

            # Close
            await store.close()

            # Verify all operations were called
            mock_client.ping.assert_called_once()
            mock_client.index.assert_called_once()
            mock_client.search.assert_called_once()
            mock_client.delete_by_query.assert_called_once()
            mock_client.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_error_handling(self):
        """Test error handling in vector store operations"""
        settings = VectorSettings(
            provider="elasticsearch",
            url="http://localhost:9200",
            collection_name="test-errors",
        )

        mock_client = AsyncMock()
        mock_client.ping = AsyncMock(side_effect=Exception("Connection failed"))

        with patch("elasticsearch.AsyncElasticsearch") as mock_es:
            mock_es.return_value = mock_client

            store = ElasticsearchVectorStore(settings)

            # Should handle connection errors gracefully
            with pytest.raises(Exception, match="Connection failed"):
                await store.initialize()