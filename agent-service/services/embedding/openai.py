"""
OpenAI embedding provider implementation
"""

import logging

try:
    from langfuse.openai import AsyncOpenAI  # type: ignore[reportMissingImports]
except ImportError:
    from openai import AsyncOpenAI

from config.settings import EmbeddingSettings, LLMSettings
from services.embedding.base import EmbeddingProvider
from services.embedding.utils import chunk_text

logger = logging.getLogger(__name__)


class OpenAIEmbeddingProvider(EmbeddingProvider):
    """OpenAI embedding provider"""

    def __init__(
        self, settings: EmbeddingSettings, llm_settings: LLMSettings | None = None
    ):
        super().__init__(settings)

        # Use embedding API key if provided, otherwise fallback to LLM API key
        api_key = (
            settings.api_key.get_secret_value()
            if settings.api_key
            else llm_settings.api_key.get_secret_value()
            if llm_settings
            else None
        )

        if not api_key:
            raise ValueError("OpenAI API key required for embeddings")

        self.client = AsyncOpenAI(api_key=api_key)

    async def get_embeddings(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for multiple texts with token limit safety check"""
        try:
            # Safety check: ensure no text exceeds token limits
            safe_texts = []
            for i, text in enumerate(texts):
                # Conservative limit: 6000 chars ≈ 1500 tokens (well under 8192 limit)
                if len(text) > 6000:
                    logger.warning(
                        f"Text {i} is {len(text)} chars, chunking for token safety"
                    )
                    chunks = chunk_text(text, chunk_size=6000, chunk_overlap=200)
                    safe_texts.extend(chunks)
                else:
                    safe_texts.append(text)

            if len(safe_texts) != len(texts):
                logger.info(
                    f"Chunked {len(texts)} texts into {len(safe_texts)} safe chunks"
                )

            logger.info(
                f"Generating embeddings for {len(safe_texts)} texts using {self.model}"
            )

            response = await self.client.embeddings.create(
                model=self.model, input=safe_texts
            )

            embeddings = [data.embedding for data in response.data]

            logger.info(
                f"Generated {len(embeddings)} embeddings",
                extra={
                    "model": self.model,
                    "text_count": len(safe_texts),
                    "embedding_dimensions": len(embeddings[0]) if embeddings else 0,
                    "event_type": "embeddings_success",
                },
            )

            return embeddings

        except Exception as e:
            logger.error(
                f"Failed to generate embeddings: {e}",
                extra={
                    "model": self.model,
                    "text_count": len(texts),
                    "error": str(e),
                    "event_type": "embeddings_error",
                },
            )
            raise

    async def get_embedding(self, text: str) -> list[float]:
        """Generate embedding for a single text"""
        embeddings = await self.get_embeddings([text])
        return embeddings[0]

    async def close(self):
        """Close OpenAI client"""
        if hasattr(self.client, "_client"):
            await self.client.close()
