"""
Factory function for creating embedding providers
"""

from config.settings import EmbeddingSettings, LLMSettings
from services.embedding.base import EmbeddingProvider
from services.embedding.openai import OpenAIEmbeddingProvider


def create_embedding_provider(
    settings: EmbeddingSettings, llm_settings: LLMSettings | None = None
) -> EmbeddingProvider:
    """Factory function to create the appropriate embedding provider"""

    provider_map = {
        "openai": lambda: OpenAIEmbeddingProvider(settings, llm_settings),
    }

    provider_factory = provider_map.get(settings.provider.lower())
    if not provider_factory:
        raise ValueError(
            f"Unsupported embedding provider: {settings.provider}. "
            "Only 'openai' is supported. "
            "For local embeddings, install with: pip install -e '.[local-embeddings]'"
        )

    return provider_factory()
