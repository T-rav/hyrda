"""
VectorSettingsFactory for test utilities
"""

from unittest.mock import MagicMock

from pydantic import SecretStr

from config.settings import (
    VectorSettings,
)


class VectorSettingsFactory:
    """Factory for creating vector storage settings"""

    @staticmethod
    def create_pinecone_settings(
        api_key: str = "test-pinecone-key",
        environment: str = "us-east-1-aws",
        index_name: str = "test-index",
    ) -> VectorSettings:
        """Create Pinecone vector settings"""
        return VectorSettings(
            provider="pinecone",
            api_key=SecretStr(api_key),
            environment=environment,
            collection_name=index_name,
            enabled=True,
        )

    @staticmethod
    def create_disabled_settings() -> VectorSettings:
        """Create disabled vector settings"""
        return VectorSettings(
            provider="chroma",
            collection_name="test",
            enabled=False,
        )

    @staticmethod
    def create_mock_settings(
        enabled: bool = False, provider: str = "chroma"
    ) -> MagicMock:
        """Create vector settings mock"""
        settings = MagicMock()
        settings.enabled = enabled
        settings.provider = provider
        settings.url = "./test_chroma"
        settings.collection_name = "test_collection"
        return settings
