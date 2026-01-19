"""Lightweight settings service for custom agents.

Reads configuration from environment variables without depending on bot/config.
"""

import logging
import os

logger = logging.getLogger(__name__)


class LLMSettings:
    """LLM configuration from environment."""

    def __init__(self):
        self.provider = os.getenv("LLM_PROVIDER", "openai")
        self.model = os.getenv("LLM_MODEL", "gpt-4o-mini")
        self.api_key = os.getenv("LLM_API_KEY", "")
        self.api_url = os.getenv("LLM_API_URL", "")


class SearchSettings:
    """Search configuration from environment."""

    def __init__(self):
        self.search_provider = os.getenv("SEARCH_PROVIDER", "tavily")
        self.tavily_api_key = os.getenv("TAVILY_API_KEY", "")
        self.perplexity_enabled = os.getenv("PERPLEXITY_ENABLED", "false").lower() == "true"
        self.perplexity_api_key = os.getenv("PERPLEXITY_API_KEY", "")


class GeminiSettings:
    """Gemini configuration from environment."""

    def __init__(self):
        self.enabled = os.getenv("GEMINI_ENABLED", "false").lower() == "true"
        self.api_key = os.getenv("GEMINI_API_KEY", "")
        self.model = os.getenv("GEMINI_MODEL", "gemini-pro")


class Settings:
    """Lightweight settings for custom agents."""

    def __init__(self):
        self.llm = LLMSettings()
        self.search = SearchSettings()
        self.gemini = GeminiSettings()


def get_settings() -> Settings:
    """Get settings instance."""
    return Settings()
