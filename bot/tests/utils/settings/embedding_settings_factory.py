"""
EmbeddingSettingsFactory for test utilities
"""

from unittest.mock import MagicMock

from pydantic import SecretStr

from config.settings import (
    EmbeddingSettings,
)


class EmbeddingSettingsFactory:
    """Factory for creating embedding settings"""

    @staticmethod
    def create_openai_settings(
        model: str = "text-embedding-3-small",
        api_key: str = "test-embedding-key",
    ) -> EmbeddingSettings:
        """Create OpenAI embedding settings"""
        return EmbeddingSettings(
            provider="openai",
            model=model,
            api_key=SecretStr(api_key),
        )

    @staticmethod
    def create_sentence_transformer_settings(
        model: str = "all-MiniLM-L6-v2",
    ) -> EmbeddingSettings:
        """Create Sentence Transformers embedding settings"""
        return EmbeddingSettings(
            provider="sentence-transformers",
            model=model,
        )

    @staticmethod
    def create_mock_settings(provider: str = "openai") -> MagicMock:
        """Create embedding settings mock"""
        settings = MagicMock()
        settings.provider = provider
        settings.model = "text-embedding-3-small"
        settings.api_key = None
        settings.chunk_size = 1000
        settings.chunk_overlap = 200
        return settings
