"""
Tests for Vector Service functionality.

Tests vector store creation using Pinecone only.
"""

from unittest.mock import patch

from pydantic import SecretStr

from bot.services.vector_service import create_vector_store
from config.settings import VectorSettings


class TestCreateVectorStore:
    """Test vector store creation (Pinecone only)"""

    @patch("bot.services.vector_service.PineconeVectorStore")
    def test_create_pinecone_store(self, mock_pinecone_class):
        """Test creating Pinecone vector store"""
        settings = VectorSettings(
            api_key=SecretStr("test-key"),
            collection_name="test-collection",
            environment="test-env",
        )

        result = create_vector_store(settings)

        mock_pinecone_class.assert_called_once_with(settings)
        assert result == mock_pinecone_class.return_value
