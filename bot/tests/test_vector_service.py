"""
Tests for Vector Service functionality.

Tests vector store creation using Qdrant.
"""

from unittest.mock import patch

from bot.services.vector_service import create_vector_store
from config.settings import VectorSettings


class TestCreateVectorStore:
    """Test vector store creation (Qdrant only)"""

    @patch("bot.services.vector_service.QdrantVectorStore")
    def test_create_qdrant_store(self, mock_qdrant_class):
        """Test creating Qdrant vector store"""
        settings = VectorSettings(
            provider="qdrant",
            host="localhost",
            port=6333,
            collection_name="test-collection",
        )

        result = create_vector_store(settings)

        mock_qdrant_class.assert_called_once_with(settings)
        assert result == mock_qdrant_class.return_value

    @patch("bot.services.vector_service.QdrantVectorStore")
    def test_create_vector_store_disabled(self, mock_qdrant_class):
        """Test that vector store returns None when disabled"""
        settings = VectorSettings(
            enabled=False,
            provider="qdrant",
            host="localhost",
            port=6333,
            collection_name="test-collection",
        )

        result = create_vector_store(settings)

        # Should not instantiate QdrantVectorStore when disabled
        mock_qdrant_class.assert_not_called()
        assert result is None
