"""
SettingsFactory for test utilities
"""

from unittest.mock import MagicMock

from pydantic import SecretStr

from config.settings import (
    EmbeddingSettings,
    LLMSettings,
    Settings,
    VectorSettings,
)


class SettingsFactory:
    """Factory for creating complete Settings objects"""

    @staticmethod
    def create_complete_rag_settings(
        embedding_provider: str = "openai",
        llm_provider: str = "openai",
        vector_provider: str = "pinecone",
    ) -> Settings:
        """Create complete RAG settings with all components"""
        return Settings(
            embedding=EmbeddingSettings(
                provider=embedding_provider,
                model="text-embedding-ada-002",
                api_key=SecretStr("test-key"),
            ),
            llm=LLMSettings(
                provider=llm_provider,
                model="gpt-4",
                api_key=SecretStr("test-key"),
            ),
            vector=VectorSettings(
                provider=vector_provider,
                api_key=SecretStr("test-key"),
                collection_name="test",
                enabled=True,
            ),
        )

    @staticmethod
    def create_vector_disabled_settings() -> Settings:
        """Create settings with vector storage disabled"""
        settings = SettingsFactory.create_complete_rag_settings()
        settings.vector.enabled = False
        return settings

    @staticmethod
    def create_basic_mock_settings() -> MagicMock:
        """Create basic settings mock with essential configuration"""
        settings = MagicMock()
        settings.slack.bot_token = "xoxb-test"
        settings.slack.app_token = "xapp-test"
        settings.llm = MagicMock()
        settings.llm.api_url = "https://api.openai.com/v1"
        settings.llm.api_key.get_secret_value.return_value = "test-key"
        return settings
