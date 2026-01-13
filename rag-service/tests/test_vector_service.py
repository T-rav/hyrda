"""Tests for vector service singleton pattern."""

import pytest
from unittest.mock import MagicMock, patch

from config.settings import VectorSettings
from services.vector_service import (
    create_vector_store,
    get_vector_store,
    set_vector_store,
)


class TestVectorServiceSingleton:
    """Test vector service singleton pattern."""

    def teardown_method(self):
        """Reset singleton after each test."""
        import services.vector_service

        services.vector_service._vector_store = None

    def test_create_vector_store_returns_new_instance(self):
        """Test that create_vector_store returns a new QdrantVectorStore instance."""
        settings = VectorSettings(
            enabled=True,
            provider="qdrant",
            host="localhost",
            port=6333,
            collection_name="test-collection",
        )

        vector_store = create_vector_store(settings)

        assert vector_store is not None
        # Verify it's a QdrantVectorStore (don't import to avoid circular deps)
        assert hasattr(vector_store, "initialize")
        assert hasattr(vector_store, "search")

    def test_get_vector_store_returns_none_when_not_initialized(self):
        """Test that get_vector_store returns None before initialization."""
        vector_store = get_vector_store()

        assert vector_store is None

    def test_set_and_get_vector_store_singleton(self):
        """Test that set_vector_store stores the singleton and get_vector_store retrieves it."""
        # Create a mock vector store
        mock_vector_store = MagicMock()
        mock_vector_store.collection_name = "test-collection"

        # Set the singleton
        set_vector_store(mock_vector_store)

        # Get the singleton
        retrieved = get_vector_store()

        # Verify it's the same instance
        assert retrieved is mock_vector_store
        assert retrieved.collection_name == "test-collection"

    def test_singleton_persists_across_multiple_gets(self):
        """Test that the singleton persists across multiple get_vector_store calls."""
        mock_vector_store = MagicMock()
        mock_vector_store.id = "test-id-123"

        set_vector_store(mock_vector_store)

        # Call get multiple times
        first_get = get_vector_store()
        second_get = get_vector_store()
        third_get = get_vector_store()

        # All should return the same instance
        assert first_get is mock_vector_store
        assert second_get is mock_vector_store
        assert third_get is mock_vector_store
        assert first_get is second_get is third_get

    def test_set_vector_store_overwrites_previous_singleton(self):
        """Test that set_vector_store overwrites the previous singleton."""
        first_store = MagicMock()
        first_store.name = "first"
        second_store = MagicMock()
        second_store.name = "second"

        # Set first singleton
        set_vector_store(first_store)
        assert get_vector_store() is first_store

        # Overwrite with second singleton
        set_vector_store(second_store)
        retrieved = get_vector_store()

        assert retrieved is second_store
        assert retrieved is not first_store
        assert retrieved.name == "second"

    def test_create_vector_store_does_not_affect_singleton(self):
        """Test that create_vector_store does not automatically set the singleton."""
        # Set a singleton
        mock_singleton = MagicMock()
        mock_singleton.name = "singleton"
        set_vector_store(mock_singleton)

        # Create a new vector store (should not affect singleton)
        settings = VectorSettings(
            enabled=True,
            provider="qdrant",
            host="localhost",
            port=6333,
            collection_name="new-collection",
        )
        new_store = create_vector_store(settings)

        # Singleton should still be the original
        assert get_vector_store() is mock_singleton
        assert get_vector_store() is not new_store


class TestVectorServiceIntegrationWithRAGService:
    """Test vector service integration with RAG service."""

    def teardown_method(self):
        """Reset singleton after each test."""
        import services.vector_service

        services.vector_service._vector_store = None

    @pytest.mark.asyncio
    async def test_rag_service_uses_singleton_vector_store(self):
        """Test that RAG service uses the global singleton vector store."""
        from config.settings import Settings
        from services.rag_service import RAGService

        # Create and set a mock vector store singleton
        mock_vector_store = MagicMock()
        mock_vector_store.collection_name = "test-singleton"
        set_vector_store(mock_vector_store)

        # Create RAG service
        settings = Settings()
        rag_service = RAGService(settings)

        # Verify RAG service is using the singleton
        assert rag_service.vector_store is mock_vector_store
        assert rag_service.vector_store.collection_name == "test-singleton"

    @pytest.mark.asyncio
    async def test_multiple_rag_service_instances_share_vector_store(self):
        """Test that multiple RAG service instances share the same vector store singleton."""
        from config.settings import Settings
        from services.rag_service import RAGService

        # Create and set a mock vector store singleton
        mock_vector_store = MagicMock()
        mock_vector_store.shared_id = "shared-store-123"
        set_vector_store(mock_vector_store)

        # Create multiple RAG service instances
        settings = Settings()
        rag_service1 = RAGService(settings)
        rag_service2 = RAGService(settings)

        # Both should use the same vector store singleton
        assert rag_service1.vector_store is mock_vector_store
        assert rag_service2.vector_store is mock_vector_store
        assert rag_service1.vector_store is rag_service2.vector_store


class TestVectorServiceNoneHandling:
    """Test handling of None vector store."""

    def teardown_method(self):
        """Reset singleton after each test."""
        import services.vector_service

        services.vector_service._vector_store = None

    def test_get_vector_store_returns_none_initially(self):
        """Test that get_vector_store returns None when not initialized."""
        vector_store = get_vector_store()
        assert vector_store is None

    def test_set_vector_store_accepts_none(self):
        """Test that set_vector_store can accept None (for cleanup)."""
        # Set a store first
        mock_store = MagicMock()
        set_vector_store(mock_store)
        assert get_vector_store() is not None

        # Set to None
        set_vector_store(None)
        assert get_vector_store() is None
