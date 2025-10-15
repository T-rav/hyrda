"""
VectorSettingsFactory for test utilities
"""

from unittest.mock import MagicMock

from config.settings import (
    VectorSettings,
)


class VectorSettingsFactory:
    """Factory for creating vector storage settings"""

    @staticmethod
    def create_qdrant_settings(
        host: str = "localhost",
        port: int = 6333,
        index_name: str = "test-index",
        api_key: str | None = None,
    ) -> VectorSettings:
        """Create Qdrant vector settings"""
        return VectorSettings(
            provider="qdrant",
            host=host,
            port=port,
            collection_name=index_name,
            api_key=api_key,
        )

    @staticmethod
    def create_disabled_settings() -> VectorSettings:
        """Create disabled vector settings"""
        return VectorSettings(
            collection_name="test",
        )

    @staticmethod
    def create_mock_settings(
        enabled: bool = False, provider: str = "qdrant"
    ) -> MagicMock:
        """Create vector settings mock"""
        settings = MagicMock()
        settings.enabled = enabled
        settings.provider = provider
        settings.host = "localhost"
        settings.port = 6333
        settings.collection_name = "test_collection"
        return settings
