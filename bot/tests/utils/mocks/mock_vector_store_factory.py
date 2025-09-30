"""
MockVectorStoreFactory for test utilities
"""

from typing import Any
from unittest.mock import AsyncMock, MagicMock


class MockVectorStoreFactory:
    """Factory for creating mock vector store objects"""

    @staticmethod
    def create_basic_store() -> MagicMock:
        """Create basic mock vector store"""
        store = MagicMock()
        store.search = AsyncMock(return_value=[])
        store.add_documents = AsyncMock(return_value=True)
        store.delete_documents = AsyncMock(return_value=True)
        store.initialize = AsyncMock()
        store.close = AsyncMock()
        return store

    @staticmethod
    def create_store_with_results(results: list[dict[str, Any]]) -> MagicMock:
        """Create vector store that returns specific results"""
        store = MockVectorStoreFactory.create_basic_store()
        store.search = AsyncMock(return_value=results)
        return store

    @staticmethod
    def create_store_with_error(error: Exception) -> MagicMock:
        """Create vector store that raises errors"""
        store = MockVectorStoreFactory.create_basic_store()
        store.search = AsyncMock(side_effect=error)
        return store
