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


class Settings:
    """Lightweight settings for custom agents."""

    def __init__(self):
        self.llm = LLMSettings()


def get_settings() -> Settings:
    """Get settings instance."""
    return Settings()
