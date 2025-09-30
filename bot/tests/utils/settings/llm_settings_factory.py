"""
LLMSettingsFactory for test utilities
"""

from unittest.mock import MagicMock

from pydantic import SecretStr

from config.settings import (
    LLMSettings,
)


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
