"""
Tests for Vector Service functionality.

Tests vector store creation and management.
"""

from unittest.mock import Mock, patch

import pytest
from pydantic import SecretStr

from bot.services.vector_service import create_vector_store
from config.settings import VectorSettings


class TestCreateVectorStore:
    """Test cases for vector store factory function"""

    def test_create_pinecone_store(self):
        """Test creating Pinecone vector store"""
        settings = VectorSettings(
            provider="pinecone",
            api_key=SecretStr("test-key"),
            collection_name="test-collection",
            environment="test-env"
        )

        with patch('bot.services.vector_service.PineconeVectorStore') as mock_pinecone:
            mock_store = Mock()
            mock_pinecone.return_value = mock_store

            store = create_vector_store(settings)

            assert store == mock_store
            mock_pinecone.assert_called_once_with(settings)

    def test_create_elasticsearch_store(self):
        """Test creating Elasticsearch vector store"""
        settings = VectorSettings(
            provider="elasticsearch",
            url="http://localhost:9200",
            collection_name="test-collection"
        )

        with patch('bot.services.vector_service.ElasticsearchVectorStore') as mock_es:
            mock_store = Mock()
            mock_es.return_value = mock_store

            store = create_vector_store(settings)

            assert store == mock_store
            mock_es.assert_called_once_with(settings)

    def test_unsupported_provider(self):
        """Test creating unsupported vector store"""
        settings = VectorSettings(
            provider="unsupported",
            collection_name="test"
        )

        with pytest.raises(ValueError, match="Unsupported vector store provider"):
            create_vector_store(settings)

    def test_case_insensitive_provider(self):
        """Test provider names are case-insensitive"""
        settings = VectorSettings(
            provider="PINECONE",
            api_key=SecretStr("key"),
            collection_name="test"
        )

        with patch('bot.services.vector_service.PineconeVectorStore') as mock_pinecone:
            create_vector_store(settings)
            mock_pinecone.assert_called_once()
