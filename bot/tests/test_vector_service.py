"""
Tests for Vector Service functionality.

Tests vector store creation and management using factory patterns.
"""

from unittest.mock import Mock, patch

import pytest
from pydantic import SecretStr

from bot.services.vector_service import create_vector_store
from config.settings import VectorSettings


# TDD Factory Patterns for Vector Service Testing
class VectorSettingsFactory:
    """Factory for creating VectorSettings with different configurations"""

    @staticmethod
    def create_pinecone_settings(
        api_key: str = "test-key",
        collection_name: str = "test-collection",
        environment: str = "test-env",
    ) -> VectorSettings:
        """Create Pinecone vector settings"""
        return VectorSettings(
            provider="pinecone",
            api_key=SecretStr(api_key),
            collection_name=collection_name,
            environment=environment,
        )

    @staticmethod
    def create_elasticsearch_settings(
        url: str = "http://localhost:9200",
        collection_name: str = "test-collection",
    ) -> VectorSettings:
        """Create Elasticsearch vector settings"""
        return VectorSettings(
            provider="elasticsearch",
            url=url,
            collection_name=collection_name,
        )

    @staticmethod
    def create_chroma_settings(
        url: str = "./test_chroma",
        collection_name: str = "test-collection",
    ) -> VectorSettings:
        """Create ChromaDB vector settings"""
        return VectorSettings(
            provider="chroma",
            url=url,
            collection_name=collection_name,
        )

    @staticmethod
    def create_invalid_settings(
        provider: str = "unsupported",
        collection_name: str = "test",
    ) -> VectorSettings:
        """Create invalid vector settings for error testing"""
        return VectorSettings(
            provider=provider,
            collection_name=collection_name,
        )

    @staticmethod
    def create_case_insensitive_settings(
        provider: str = "PINECONE",
        api_key: str = "key",
        collection_name: str = "test",
    ) -> VectorSettings:
        """Create settings with case-insensitive provider names"""
        return VectorSettings(
            provider=provider,
            api_key=SecretStr(api_key),
            collection_name=collection_name,
        )


class MockVectorStoreFactory:
    """Factory for creating mock vector store instances"""

    @staticmethod
    def create_basic_mock() -> Mock:
        """Create basic mock vector store"""
        return Mock()

    @staticmethod
    def create_pinecone_mock() -> Mock:
        """Create mock Pinecone vector store"""
        mock_store = MockVectorStoreFactory.create_basic_mock()
        mock_store.__class__.__name__ = "PineconeVectorStore"
        return mock_store

    @staticmethod
    def create_elasticsearch_mock() -> Mock:
        """Create mock Elasticsearch vector store"""
        mock_store = MockVectorStoreFactory.create_basic_mock()
        mock_store.__class__.__name__ = "ElasticsearchVectorStore"
        return mock_store

    @staticmethod
    def create_chroma_mock() -> Mock:
        """Create mock ChromaDB vector store"""
        mock_store = MockVectorStoreFactory.create_basic_mock()
        mock_store.__class__.__name__ = "ChromaVectorStore"
        return mock_store


class TestCreateVectorStore:
    """Test cases for vector store factory function using factory patterns"""

    def test_create_pinecone_store(self):
        """Test creating Pinecone vector store"""
        settings = VectorSettingsFactory.create_pinecone_settings()

        with patch("bot.services.vector_service.PineconeVectorStore") as mock_pinecone:
            mock_store = MockVectorStoreFactory.create_pinecone_mock()
            mock_pinecone.return_value = mock_store

            store = create_vector_store(settings)

            assert store == mock_store
            mock_pinecone.assert_called_once_with(settings)

    def test_create_elasticsearch_store(self):
        """Test creating Elasticsearch vector store"""
        settings = VectorSettingsFactory.create_elasticsearch_settings()

        with patch("bot.services.vector_service.ElasticsearchVectorStore") as mock_es:
            mock_store = MockVectorStoreFactory.create_elasticsearch_mock()
            mock_es.return_value = mock_store

            store = create_vector_store(settings)

            assert store == mock_store
            mock_es.assert_called_once_with(settings)

    def test_unsupported_provider(self):
        """Test creating unsupported vector store"""
        settings = VectorSettingsFactory.create_invalid_settings()

        with pytest.raises(ValueError, match="Unsupported vector store provider"):
            create_vector_store(settings)

    def test_case_insensitive_provider(self):
        """Test provider names are case-insensitive"""
        settings = VectorSettingsFactory.create_case_insensitive_settings()

        with patch("bot.services.vector_service.PineconeVectorStore") as mock_pinecone:
            mock_store = MockVectorStoreFactory.create_pinecone_mock()
            mock_pinecone.return_value = mock_store

            store = create_vector_store(settings)

            assert store == mock_store
            mock_pinecone.assert_called_once()
