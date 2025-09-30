"""
ConversationCacheFactory for test utilities
"""

from unittest.mock import AsyncMock, MagicMock


class ConversationCacheFactory:
    """Factory for creating conversation cache mocks"""

    @staticmethod
    def create_enabled_cache() -> MagicMock:
        """Create enabled conversation cache mock"""
        cache = MagicMock()
        cache.is_enabled = True
        cache.get_conversation = AsyncMock(return_value=[])
        cache.add_message = AsyncMock()
        cache.clear_conversation = AsyncMock()
        return cache

    @staticmethod
    def create_disabled_cache() -> MagicMock:
        """Create disabled conversation cache mock"""
        cache = MagicMock()
        cache.is_enabled = False
        cache.get_conversation = AsyncMock(return_value=[])
        return cache

    @staticmethod
    def create_cache_with_history(messages: list[dict[str, str]]) -> MagicMock:
        """Create cache with pre-populated conversation history"""
        cache = ConversationCacheFactory.create_enabled_cache()
        cache.get_conversation = AsyncMock(return_value=messages)
        return cache
