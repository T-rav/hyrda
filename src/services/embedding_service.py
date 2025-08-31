"""
Embedding service for text vectorization
"""

import asyncio
import logging
from abc import ABC, abstractmethod

from langfuse.openai import AsyncOpenAI

from config.settings import EmbeddingSettings, LLMSettings

logger = logging.getLogger(__name__)


class EmbeddingProvider(ABC):
    """Abstract base class for embedding providers"""

    def __init__(self, settings: EmbeddingSettings):
        self.settings = settings
        self.model = settings.model

    @abstractmethod
    async def get_embeddings(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for a list of texts"""
        pass

    @abstractmethod
    async def get_embedding(self, text: str) -> list[float]:
        """Generate embedding for a single text"""
        pass

    @abstractmethod
    async def close(self):
        """Clean up resources"""
        pass


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
            else llm_settings.api_key.get_secret_value() if llm_settings else None
        )

        if not api_key:
            raise ValueError("OpenAI API key required for embeddings")

        self.client = AsyncOpenAI(api_key=api_key)

    async def get_embeddings(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for multiple texts"""
        try:
            logger.info(
                f"Generating embeddings for {len(texts)} texts using {self.model}"
            )

            response = await self.client.embeddings.create(
                model=self.model, input=texts
            )

            embeddings = [data.embedding for data in response.data]

            logger.info(
                f"Generated {len(embeddings)} embeddings",
                extra={
                    "model": self.model,
                    "text_count": len(texts),
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


class SentenceTransformerEmbeddingProvider(EmbeddingProvider):
    """Sentence Transformers embedding provider (local)"""

    def __init__(self, settings: EmbeddingSettings):
        super().__init__(settings)
        self.model_instance = None
        self._initialized = False

    async def _initialize(self) -> None:
        """Initialize the sentence transformer model"""
        if self._initialized:
            return

        try:
            from sentence_transformers import SentenceTransformer  # noqa: PLC0415

            # Load model in executor to avoid blocking
            self.model_instance = await asyncio.get_event_loop().run_in_executor(
                None, SentenceTransformer, self.model
            )

            self._initialized = True
            logger.info(f"Initialized SentenceTransformer model: {self.model}")

        except ImportError:
            raise ImportError(
                "sentence-transformers package not installed. "
                "Run: pip install sentence-transformers"
            ) from None
        except Exception as e:
            logger.error(f"Failed to initialize SentenceTransformer: {e}")
            raise

    async def get_embeddings(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for multiple texts"""
        await self._initialize()

        try:
            logger.info(
                f"Generating embeddings for {len(texts)} texts using {self.model}"
            )

            # Run encoding in executor to avoid blocking
            if self.model_instance is None:
                raise RuntimeError("SentenceTransformer model not initialized")

            embeddings = await asyncio.get_event_loop().run_in_executor(
                None,
                self.model_instance.encode,
                texts,
                {"convert_to_numpy": True, "show_progress_bar": False},
            )

            # Convert numpy arrays to lists
            embeddings_list = [embedding.tolist() for embedding in embeddings]

            logger.info(
                f"Generated {len(embeddings_list)} embeddings",
                extra={
                    "model": self.model,
                    "text_count": len(texts),
                    "embedding_dimensions": (
                        len(embeddings_list[0]) if embeddings_list else 0
                    ),
                    "event_type": "embeddings_success",
                },
            )

            return embeddings_list

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
        """Clean up resources"""
        self.model_instance = None
        self._initialized = False


def create_embedding_provider(
    settings: EmbeddingSettings, llm_settings: LLMSettings | None = None
) -> EmbeddingProvider:
    """Factory function to create the appropriate embedding provider"""

    provider_map = {
        "openai": lambda: OpenAIEmbeddingProvider(settings, llm_settings),
        "sentence-transformers": lambda: SentenceTransformerEmbeddingProvider(settings),
        "sentence_transformers": lambda: SentenceTransformerEmbeddingProvider(
            settings
        ),  # Alternative name
    }

    provider_factory = provider_map.get(settings.provider.lower())
    if not provider_factory:
        raise ValueError(f"Unsupported embedding provider: {settings.provider}")

    return provider_factory()


def chunk_text(
    text: str,
    chunk_size: int = 1000,
    chunk_overlap: int = 200,
    separators: list[str] | None = None,
) -> list[str]:
    """
    Split text into overlapping chunks for embedding

    Args:
        text: Text to chunk
        chunk_size: Maximum size of each chunk
        chunk_overlap: Number of characters to overlap between chunks
        separators: List of separators to try (in order of preference)

    Returns:
        List of text chunks
    """
    if separators is None:
        separators = ["\n\n", "\n", ". ", " ", ""]

    if len(text) <= chunk_size:
        return [text]

    chunks = []
    start = 0

    while start < len(text):
        end = start + chunk_size

        if end >= len(text):
            # Last chunk
            chunks.append(text[start:])
            break

        # Try to find a good break point
        best_end = end
        for separator in separators:
            if separator == "":
                break

            # Look for separator within the overlap region
            search_start = max(end - chunk_overlap, start)
            separator_pos = text.rfind(separator, search_start, end)

            if separator_pos > start:
                best_end = separator_pos + len(separator)
                break

        chunks.append(text[start:best_end])

        # Calculate next start position with overlap
        start = best_end - chunk_overlap
        start = max(start, best_end)  # Ensure we always make progress

    return [chunk.strip() for chunk in chunks if chunk.strip()]
