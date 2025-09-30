"""
Settings factory patterns for test configuration

Provides factories for creating various settings objects used across tests.
Consolidates duplicate factory patterns from multiple test files.
"""

import os
from unittest.mock import MagicMock, patch

from pydantic import SecretStr

from config.settings import (
    EmbeddingSettings,
    LLMSettings,
    Settings,
    SlackSettings,
    VectorSettings,
)


class EnvironmentVariableFactory:
    """Factory for creating environment variable configurations"""

    @staticmethod
    def create_slack_env_vars(
        bot_token: str = "xoxb-test-token",
        app_token: str = "xapp-test-token",
        bot_id: str = "B12345678",
    ) -> dict[str, str]:
        """Create Slack environment variables"""
        return {
            "SLACK_BOT_TOKEN": bot_token,
            "SLACK_APP_TOKEN": app_token,
            "SLACK_BOT_ID": bot_id,
        }

    @staticmethod
    def create_llm_env_vars(
        provider: str = "openai",
        api_key: str = "test-api-key",
        model: str = "test-model",
        base_url: str = "http://test-api.com",
    ) -> dict[str, str]:
        """Create LLM environment variables"""
        return {
            "LLM_PROVIDER": provider,
            "LLM_API_KEY": api_key,
            "LLM_MODEL": model,
            "LLM_BASE_URL": base_url,
        }

    @staticmethod
    def create_complete_env_vars(
        slack_token: str = "xoxb-test-token",
        slack_app_token: str = "xapp-test-token",
        llm_api_url: str = "http://test-api.com",
        llm_api_key: str = "test-api-key",
        database_url: str = "postgresql://test:test@localhost:5432/test_db",
    ) -> dict[str, str]:
        """Create complete environment variables for Settings"""
        return {
            "SLACK_BOT_TOKEN": slack_token,
            "SLACK_APP_TOKEN": slack_app_token,
            "LLM_API_URL": llm_api_url,
            "LLM_API_KEY": llm_api_key,
            "DATABASE_URL": database_url,
        }


class LLMSettingsFactory:
    """Factory for creating LLM settings with different configurations"""

    @staticmethod
    def create_openai_settings(model: str = "gpt-4o-mini") -> MagicMock:
        """Create OpenAI LLM settings mock"""
        settings = MagicMock()
        settings.llm = MagicMock()
        settings.llm.provider = "openai"
        settings.llm.api_key = MagicMock()
        settings.llm.api_key.get_secret_value.return_value = "test-api-key"
        settings.llm.model = model
        settings.llm.temperature = 0.7
        settings.llm.max_tokens = 2000
        settings.llm.base_url = None
        return settings

    @staticmethod
    def create_real_llm_settings(
        provider: str = "openai",
        api_key: str = "test-api-key",
        model: str = "gpt-4",
    ) -> LLMSettings:
        """Create real LLMSettings instance"""
        return LLMSettings(
            provider=provider,
            api_key=SecretStr(api_key),
            model=model,
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


class SlackSettingsFactory:
    """Factory for creating Slack settings"""

    @staticmethod
    def create_basic_settings(
        bot_token: str = "xoxb-test-token",
        app_token: str = "xapp-test-token",
        bot_id: str = "B12345678",
    ) -> SlackSettings:
        """Create SlackSettings with environment variables"""
        env_vars = EnvironmentVariableFactory.create_slack_env_vars(
            bot_token=bot_token, app_token=app_token, bot_id=bot_id
        )
        with patch.dict(os.environ, env_vars):
            return SlackSettings()


class RAGSettingsBuilder:
    """Builder for creating RAG-specific settings configurations"""

    @staticmethod
    def create_rag_settings(
        max_chunks: int = 5,
        similarity_threshold: float = 0.7,
        rerank_enabled: bool = False,
    ) -> MagicMock:
        """Create RAG settings mock"""
        settings = MagicMock()
        settings.max_chunks = max_chunks
        settings.similarity_threshold = similarity_threshold
        settings.rerank_enabled = rerank_enabled
        settings.include_metadata = True
        return settings


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
